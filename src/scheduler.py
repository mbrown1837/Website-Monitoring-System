import schedule
import time
from datetime import datetime, timezone
import signal # For graceful shutdown
import threading # For graceful shutdown
import os # For reading previous snapshot files
# Import manager CLASSES
from src.website_manager_sqlite import WebsiteManager
from src.history_manager_sqlite import HistoryManager
from src.config_loader import get_config
from src.logger_setup import setup_logging
from src.image_processor import create_visual_diff_report # Import the new function

# Import newly relevant modules
import src.content_retriever as content_retriever
import src.snapshot_tool as snapshot_tool
import src.comparators as comparators
import src.alerter as alerter
from bs4 import BeautifulSoup

# Import crawler module
from src.crawler_module import CrawlerModule
from src.comparators import compare_screenshots, compare_html_text_content
from src.snapshot_tool import save_visual_snapshot, save_html_snapshot
from src.history_manager import HistoryManager

logger = setup_logging()
config = get_config()

# Global variables for scheduler managers
_website_manager = None
_history_manager = None
_crawler_module = None
_scheduler_config = None

# Global concurrency control for site-level checks - STRICT SINGLE-SITE PROCESSING
_max_concurrent_site_checks = 1  # Force single-site processing for reliability
_site_check_semaphore = threading.Semaphore(_max_concurrent_site_checks)
_processing_lock = threading.Lock()  # Additional lock to ensure only one site processes at a time
_current_processing_site = None  # Track which site is currently being processed

def get_scheduler_managers(config_path=None, website_manager=None, history_manager=None, crawler_module=None):
    """Get or create scheduler managers with proper configuration."""
    global _website_manager, _history_manager, _crawler_module, _scheduler_config
    
    # Allow passing in existing manager instances (useful for testing)
    if website_manager:
        _website_manager = website_manager
    if history_manager:
        _history_manager = history_manager
    if crawler_module:
        _crawler_module = crawler_module
    
    # Load configuration with proper path
    if config_path and _scheduler_config is None:
        _scheduler_config = get_config(config_path=config_path)
        logger.info(f"SCHEDULER: Loaded configuration from {config_path}")
    elif _scheduler_config is None:
        _scheduler_config = get_config()
        logger.info("SCHEDULER: Loaded default configuration")
    
    # Initialize managers with proper configuration
    if _website_manager is None:
        from src.website_manager_sqlite import WebsiteManagerSQLite
        _website_manager = WebsiteManagerSQLite(config_path=config_path)
        logger.info("SCHEDULER: Initialized website manager")
    
    if _history_manager is None:
        _history_manager = HistoryManager(config_path=config_path)
        logger.info("SCHEDULER: Initialized history manager")
    
    if _crawler_module is None:
        _crawler_module = CrawlerModule()
        logger.info("SCHEDULER: Initialized crawler module")
    
    return _website_manager, _history_manager, _crawler_module, _scheduler_config

# Initialize managers with default config for backward compatibility
website_manager, history_manager, crawler_module, config = get_scheduler_managers()

# Event to signal shutdown
_shutdown_event = threading.Event()

def _signal_handler(signum, frame):
    logger.info(f"SCHEDULER: Signal {signal.Signals(signum).name} received. Initiating graceful shutdown...")
    _shutdown_event.set()

# Register signal handlers for SIGINT (Ctrl+C) and SIGTERM
signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)

def make_json_serializable(obj):
    """
    Recursively convert a Python object to make it JSON serializable.
    Handles sets, custom objects, and other non-serializable types.
    
    Args:
        obj: The Python object to convert
        
    Returns:
        A JSON serializable version of the object
    """
    import PIL.Image
    
    if isinstance(obj, dict):
        return {k: make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_json_serializable(i) for i in obj]
    elif isinstance(obj, tuple):
        return [make_json_serializable(i) for i in obj]
    elif isinstance(obj, set):
        return [make_json_serializable(i) for i in obj]
    elif isinstance(obj, PIL.Image.Image):
        # Handle PIL Image objects - convert to path string if possible or just return None
        return None
    elif hasattr(obj, '__dict__'):
        # For custom objects
        return make_json_serializable(obj.__dict__)
    elif hasattr(obj, 'isoformat'):
        # For datetime objects
        return obj.isoformat()
    else:
        # Handle other non-serializable types as needed
        try:
            # Check if it's a basic type that JSON can handle
            import json
            json.dumps(obj)
            return obj
        except TypeError:
            # If it can't be serialized, convert to string
            return str(obj)

def determine_significance(results: dict, site_config: dict) -> list:
    """Determines if detected changes are significant based on thresholds."""
    # Get general thresholds from global config
    content_sim_threshold = config.get('content_change_threshold', 0.95) # Expects similarity score
    structure_sim_threshold = config.get('structure_change_threshold', 0.98) # Expects similarity score
    visual_change_percent_threshold = config.get('visual_change_alert_threshold_percent', 1.0) # Default to 1%
    semantic_sim_threshold = config.get('semantic_similarity_threshold', 0.90) # Expects similarity score
    ssim_sim_threshold = config.get('ssim_similarity_threshold', 0.95) # Expects similarity score (SSIM)
    # TODO: Site-specific thresholds could override general ones (e.g., site_config.get('thresholds', {}).get('content_change_threshold'))

    significant_changes_found = [] # List to store reasons for significance

    # Content Similarity Check (difflib)
    content_diff_score = results.get('content_diff_score')
    if content_diff_score is not None:
        if content_diff_score < content_sim_threshold:
            reason = f"Content similarity (difflib) {content_diff_score:.4f} < threshold {content_sim_threshold:.4f}"
            logger.info(f"SIGNIFICANCE: {reason}")
            significant_changes_found.append(reason)
    else:
        logger.debug("SIGNIFICANCE: Content diff score (difflib) not available, cannot determine content significance.")

    # Semantic Content Similarity Check (diff-match-patch)
    semantic_diff_score = results.get('semantic_diff_score')
    if semantic_diff_score is not None:
        if semantic_diff_score < semantic_sim_threshold:
            reason = f"Semantic content similarity {semantic_diff_score:.4f} < threshold {semantic_sim_threshold:.4f}"
            logger.info(f"SIGNIFICANCE: {reason}")
            significant_changes_found.append(reason)
    else:
        logger.debug("SIGNIFICANCE: Semantic diff score not available, cannot determine semantic significance.")

    # Structure Similarity Check
    structure_diff_score = results.get('structure_diff_score')
    if structure_diff_score is not None:
        if structure_diff_score < structure_sim_threshold:
            reason = f"Structure similarity {structure_diff_score:.4f} < threshold {structure_sim_threshold:.4f}"
            logger.info(f"SIGNIFICANCE: {reason}")
            significant_changes_found.append(reason)
    else:
        logger.debug("SIGNIFICANCE: Structure diff score not available, cannot determine structure significance.")

    # Visual Difference Check (Percentage)
    visual_diff_percent = results.get('visual_diff_percent') # This is our new percentage diff
    if visual_diff_percent is not None:
        if visual_diff_percent > visual_change_percent_threshold:
            reason = f"Visual difference ({visual_diff_percent:.4f}%) > threshold ({visual_change_percent_threshold:.4f}%)"
            logger.info(f"SIGNIFICANCE: {reason}")
            significant_changes_found.append(reason)
    else:
        logger.debug("SIGNIFICANCE: Visual diff percentage not available, cannot determine visual significance.")

    # SSIM (Structural Similarity Index) Check
    ssim_score = results.get('ssim_score')
    if ssim_score is not None: # SSIM: 1 is identical, lower means more different
        if ssim_score < ssim_sim_threshold:
            reason = f"SSIM score {ssim_score:.4f} < threshold {ssim_sim_threshold:.4f}"
            logger.info(f"SIGNIFICANCE: {reason}")
            significant_changes_found.append(reason)
    elif comparators.OPENCV_SKIMAGE_AVAILABLE: # Log only if libraries were expected and score is missing
        logger.debug("SIGNIFICANCE: SSIM score not available (though libraries are present), cannot determine SSIM-based visual significance.")
    else: # Libraries not available, so SSIM wasn't attempted
        logger.debug("SIGNIFICANCE: OpenCV/scikit-image not available, SSIM check skipped.")

    # Meta Tags Check
    meta_changes = results.get('meta_changes')
    if meta_changes: # This implies changes were found if the key exists and is non-empty/True
        reason = f"Meta tags changed: {meta_changes}"
        logger.info(f"SIGNIFICANCE: {reason}")
        significant_changes_found.append(reason)

    # Link Changes Check
    link_changes = results.get('link_changes')
    if link_changes and (link_changes.get('added') or link_changes.get('removed')):
        reason = f"Links changed: Added {len(link_changes.get('added', []))}, Removed {len(link_changes.get('removed', []))}"
        logger.info(f"SIGNIFICANCE: {reason}")
        significant_changes_found.append(reason)

    # Image Source Changes Check
    image_src_changes = results.get('image_src_changes')
    if image_src_changes and (image_src_changes.get('added_images') or image_src_changes.get('removed_images')):
        reason = f"Image sources changed: Added {len(image_src_changes.get('added_images', []))}, Removed {len(image_src_changes.get('removed_images', []))}"
        logger.info(f"SIGNIFICANCE: {reason}")
        significant_changes_found.append(reason)

    # Canonical URL Change Check
    canonical_url_change = results.get('canonical_url_change')
    if canonical_url_change and (canonical_url_change.get('old') or canonical_url_change.get('new')): # Ensure there was a change
        reason = f"Canonical URL changed from '{canonical_url_change.get('old')}' to '{canonical_url_change.get('new')}'"
        logger.info(f"SIGNIFICANCE: {reason}")
        significant_changes_found.append(reason)
    
    if results.get('crawler_results', {}).get('total_broken_links', 0) > 0:
        reason = f"Broken links found: {results.get('crawler_results', {}).get('total_broken_links', 0)}"
        logger.info(f"SIGNIFICANCE: {reason}")
        significant_changes_found.append(reason)
    
    if significant_changes_found:
        logger.info(f"SIGNIFICANCE: Overall, significant changes detected. Reasons: {'; '.join(significant_changes_found)}")
    else:
        logger.info("SIGNIFICANCE: No significant changes detected based on current thresholds and checks.")

    return significant_changes_found

def perform_website_check(site_id: str, crawler_options_override: dict = None, config_path: str = None, 
                          website_manager_instance=None, history_manager_instance=None, crawler_module_instance=None):
    """
    Performs a comprehensive check for a single website.
    """
    # Use provided manager instances if available (from main app), otherwise get from scheduler managers
    if website_manager_instance is not None:
        website_manager = website_manager_instance
        history_manager = history_manager_instance  
        crawler_module = crawler_module_instance
        config = get_config(config_path=config_path)
    else:
        # Get properly configured managers
        website_manager, history_manager, crawler_module, config = get_scheduler_managers(config_path)
        
        # During tests, the managers might be pre-configured mocks.
        # If not, we initialize them as usual.
        if website_manager is None:
            from src.website_manager_sqlite import WebsiteManagerSQLite
            website_manager = WebsiteManagerSQLite(config_path=config_path)
        if history_manager is None:
            history_manager = HistoryManager(config_path=config_path)
        if crawler_module is None:
            crawler_module = CrawlerModule(config_path=config_path)

    # Get database manager for logging
    from .scheduler_db import get_scheduler_db_manager
    db_manager = get_scheduler_db_manager(config_path)
    
    website = website_manager.get_website(site_id)
    if not website:
        logger.error(f"check_website_task: Website with ID {site_id} not found.")
        db_manager.log_scheduler_event("ERROR", f"Website with ID {site_id} not found", site_id, None)
        return {"status": "error", "message": "Website not found"}

    # Determine if this is a scheduled check or manual check
    is_scheduled = not crawler_options_override or crawler_options_override.get('is_scheduled', True)
    
    # Use appropriate check configuration based on whether this is scheduled or manual
    if is_scheduled:
        # For scheduled checks, use automated configuration
        check_config = website_manager.get_automated_check_config(site_id)
    else:
        # For manual checks, use the provided check configuration
        check_config = crawler_options_override.get('check_config', website_manager.get_automated_check_config(site_id))
    
    final_crawler_options = {
        'create_baseline': False, 
        'capture_subpages': website.get('capture_subpages', True),
        'max_depth': website.get('max_crawl_depth', 2),
        'check_config': check_config,
        'is_scheduled': is_scheduled
    }
    
    # Override with any provided options
    if crawler_options_override: 
        # For manual checks, respect the check_config provided by the app (if any)
        # This allows manual checks to override with specific configurations
        manual_check_config = crawler_options_override.get('check_config')
        final_crawler_options.update(crawler_options_override)
        
        # If manual check provided a specific config, use it; otherwise keep automated config
        if not is_scheduled and manual_check_config:
            final_crawler_options['check_config'] = manual_check_config
            logger.info(f"Using manual check configuration override for {website.get('name')}: {manual_check_config}")
        elif not is_scheduled:
            # Keep the automated config for consistency
            logger.info(f"Using automated configuration for manual check of {website.get('name')}: {check_config}")

    logger.info(f"Performing check for '{website.get('name')}' (ID: {site_id}) with options: {final_crawler_options}")
    check_result = {
        "site_id": site_id, "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "pending", "url": website.get('url'), "significant_change_detected": False,
    }

    # STRICT SINGLE-SITE PROCESSING: Ensure only one site processes at a time
    global _current_processing_site
    site_name = website.get('name', 'Unknown')
    
    with _processing_lock:
        if _current_processing_site is not None:
            logger.info(f"⏳ Waiting for {_current_processing_site} to finish before processing {site_name}")
            while _current_processing_site is not None:
                time.sleep(1)  # Wait 1 second before checking again
        _current_processing_site = site_name
        logger.info(f"🚀 Starting single-site processing for: {site_name}")
    
    # Concurrency gate: limit number of concurrent site checks
    logger.debug(f"Awaiting site check slot (max {_max_concurrent_site_checks} concurrent)...")
    _site_check_semaphore.acquire()
    try:
        all_results = crawler_module.crawl_website(
            website_id=site_id, 
            url=website.get('url'), 
            check_config=final_crawler_options.get('check_config'),
            is_scheduled=final_crawler_options.get('is_scheduled'),
            max_depth=final_crawler_options.get('max_depth'),
            crawl_only=final_crawler_options.get('crawl_only'),
            visual_check_only=final_crawler_options.get('visual_check_only'),
            create_baseline=final_crawler_options.get('create_baseline')
        )
        check_result.update(all_results)
        
        if final_crawler_options.get('create_baseline'):
            check_result['status'] = 'Baseline Created'
            logger.info(f"Baseline created for {website.get('name')}. No comparison will be performed.")
            serializable_result = make_json_serializable(check_result)
            history_manager.add_check_record(**serializable_result)
            # Don't return early - let the finally block execute to release the lock
        else:
            # Only run significance checks and additional processing for non-baseline checks
            significant_changes = determine_significance(check_result, website)
            if significant_changes:
                check_result.update({
                    'significant_change_detected': True, 
                    'status': 'Change Detected',
                    'reasons': significant_changes
                })
                logger.info(f"Significant changes detected for {website.get('name')}, preparing to send alert.")
                
                alerter.send_report(website, check_result)
            else:
                check_result['status'] = 'No significant change'
                logger.info(f"No significant changes detected for {website.get('name')}.")

            serializable_result = make_json_serializable(check_result)
            history_manager.add_check_record(**serializable_result)

        logger.info(f"Check for '{website.get('name')}' completed. Status: {check_result['status']}")
        db_manager.log_scheduler_event("INFO", f"Check completed: {check_result['status']}", site_id, check_result.get('check_id'))
        return serializable_result

    except Exception as e:
        logger.error(f"An unexpected error occurred during check for site {site_id}: {e}", exc_info=True)
        check_result['status'] = 'Error'
        check_result['error_message'] = str(e)
        serializable_result = make_json_serializable(check_result)
        history_manager.add_check_record(**serializable_result)
        return serializable_result
    finally:
        _site_check_semaphore.release()
        # Clear the current processing site to allow next site to start
        with _processing_lock:
            _current_processing_site = None
        logger.info(f"✅ Completed single-site processing for: {site_name}")

def schedule_website_monitoring_tasks(config_path=None):
    """Loads websites and schedules monitoring tasks for active ones."""
    logger.info("SCHEDULER: Loading websites and setting up monitoring schedules...")
    schedule.clear() # Clear any existing schedules before setting new ones

    # Get properly configured managers with production config
    if config_path is None:
        from src.config_loader import get_config_path_for_environment
        config_path = get_config_path_for_environment()
        logger.info(f"SCHEDULER: Using config path: {config_path}")
    
    website_manager, history_manager, crawler_module, config = get_scheduler_managers(config_path)
    
    # Force reload websites from database
    logger.info("SCHEDULER: Forcing website reload from database...")
    website_manager._load_websites(force_reload=True)

    try:
        all_websites_map = website_manager.list_websites()
        logger.info(f"SCHEDULER: Loaded {len(all_websites_map)} total websites from database")
        active_websites = [site for site in all_websites_map.values() if site.get('is_active', True)]
        logger.info(f"SCHEDULER: Found {len(active_websites)} active websites")
        for site in active_websites:
            logger.info(f"SCHEDULER: Active site: {site.get('name')} (ID: {site.get('id')}) - Interval: {site.get('check_interval_minutes')} minutes")
    except Exception as e:
        logger.error(f"SCHEDULER: Failed to load website list: {e}", exc_info=True)
        active_websites = []

    if not active_websites:
        logger.warning("SCHEDULER: No active websites found to schedule.")
        return

    default_interval_minutes = config.get('default_monitoring_interval_minutes', 60)
    for site in active_websites:
        site_id = site.get('id')
        interval_minutes = site.get('check_interval_minutes', default_interval_minutes)
        if not site_id:
            logger.error(f"SCHEDULER: Skipping site due to missing ID: {site.get('name')}")
            continue
        
        if not isinstance(interval_minutes, (int, float)) or interval_minutes <= 0:
            logger.warning(f"SCHEDULER: Invalid monitoring interval for {site.get('name')}. Using default of {default_interval_minutes} minutes.")
            interval_minutes = default_interval_minutes

        try:
            logger.info(f"SCHEDULER: Scheduling check for {site.get('name')} every {interval_minutes} minutes.")
            schedule.every(interval_minutes).minutes.do(perform_website_check, site_id=site_id, config_path=config_path)
        except Exception as e:
            logger.error(f"SCHEDULER: Error scheduling task for {site.get('name')}: {e}", exc_info=True)
    
    logger.info(f"SCHEDULER: Successfully scheduled tasks for {len(active_websites)} active websites.")
    if schedule.jobs:
        logger.info(f"SCHEDULER: Next run for scheduled tasks: {schedule.next_run()}")

def run_scheduler():
    """Runs the main scheduling loop. Handles graceful shutdown."""
    logger.info("SCHEDULER: Initializing and scheduling tasks...")
    schedule_website_monitoring_tasks()
    logger.info("SCHEDULER: Starting main scheduling loop.")
    
    if schedule.jobs: logger.info(f"SCHEDULER: Next scheduled run at: {schedule.next_run()}")
    else: logger.info("SCHEDULER: No tasks scheduled initially.")

    while not _shutdown_event.is_set():
        try:
            schedule.run_pending()
            wait_time = min(schedule.idle_seconds() or 60, 60)
            if _shutdown_event.wait(timeout=wait_time):
                break
        except Exception as e:
            logger.error(f"SCHEDULER: An error occurred in the main scheduling loop: {e}", exc_info=True)
            if _shutdown_event.wait(timeout=60):
                break

    logger.info("SCHEDULER: Shutdown signal received. Exiting scheduler loop.")
    schedule.clear()
    logger.info("SCHEDULER: All scheduled tasks cleared. Scheduler stopped.")

if __name__ == '__main__':
    logger.info("----- Scheduler Service Starting -----")
    if not website_manager.list_websites():
        logger.info("Scheduler Demo: No websites found. Adding test websites.")
        website_manager.add_website({"url": "https://example.com", "name": "Example Domain Check", "check_interval_minutes": 1})
        website_manager.add_website({"url": "https://www.google.com", "name": "Google Check", "check_interval_minutes": 2})
    run_scheduler()
    logger.info("----- Scheduler Service Terminated -----") 