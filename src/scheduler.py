import schedule
import time
from datetime import datetime, timezone
import signal # For graceful shutdown
import threading # For graceful shutdown
# Import manager CLASSES
from src.website_manager import WebsiteManager
from src.history_manager import HistoryManager
from src.config_loader import get_config
from src.logger_setup import setup_logging

# Import newly relevant modules
import src.content_retriever as content_retriever
import src.snapshot_tool as snapshot_tool
import src.comparators as comparators
import src.alerter as alerter
import os # For reading previous snapshot files
from bs4 import BeautifulSoup

# Import crawler module
from src.crawler_module import CrawlerModule

logger = setup_logging()
config = get_config()

# Instantiate managers for the scheduler's own use
# These will use the default application configuration
website_manager = WebsiteManager() 
history_manager = HistoryManager()
crawler_module = CrawlerModule()  # Initialize the crawler module

# Event to signal shutdown
_shutdown_event = threading.Event()

def _signal_handler(signum, frame):
    logger.info(f"SCHEDULER: Signal {signal.Signals(signum).name} received. Initiating graceful shutdown...")
    _shutdown_event.set()

# Register signal handlers for SIGINT (Ctrl+C) and SIGTERM
signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)

def determine_significance(results: dict, site_config: dict) -> bool:
    """Determines if detected changes are significant based on thresholds."""
    # Get general thresholds from global config
    content_sim_threshold = config.get('content_change_threshold', 0.95) # Expects similarity score
    structure_sim_threshold = config.get('structure_change_threshold', 0.98) # Expects similarity score
    visual_diff_threshold = config.get('visual_difference_threshold', 0.05) # Expects difference score (0-1) MSE
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

    # Visual Difference Check (MSE)
    visual_diff_score = results.get('visual_diff_score') # This is MSE
    if visual_diff_score is not None:
        if visual_diff_score > visual_diff_threshold: # MSE: higher means more different
            reason = f"Visual difference (MSE) {visual_diff_score:.4f} > threshold {visual_diff_threshold:.4f}"
            logger.info(f"SIGNIFICANCE: {reason}")
            significant_changes_found.append(reason)
    else:
        logger.debug("SIGNIFICANCE: Visual diff score (MSE) not available, cannot determine visual significance.")

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
    
    if significant_changes_found:
        logger.info(f"SIGNIFICANCE: Overall, significant changes detected. Reasons: {'; '.join(significant_changes_found)}")
        return True
    else:
        logger.info("SIGNIFICANCE: No significant changes detected based on current thresholds and checks.")
        return False

# Main monitoring function, significantly enhanced
def perform_website_check(site_id: str, crawler_options: dict = None):
    """
    Manually perform a check on a website.
    
    Args:
        site_id (str): ID of website to check
        crawler_options (dict, optional): Dictionary of crawler options
        
    Returns:
        dict: Results of the check
    """
    # Get configuration
    config = get_config()
    logger = setup_logging()
    
    # Get website data
    website_manager = WebsiteManager()
    site = website_manager.get_website(site_id)
    
    if not site:
        logger.error(f"MONITOR_TASK: Website with ID {site_id} not found for manual check")
        return {"status": "error", "message": f"Website with ID {site_id} not found"}
    
    # Default crawler options
    if crawler_options is None:
        crawler_options = {}
    
    # Check if the website is configured as crawl-only
    website_is_crawl_only = site.get('crawl_only', False)
    
    # If website is set to crawl-only, override options to ensure we don't do visual checks
    if website_is_crawl_only:
        logger.info(f"MONITOR_TASK: Website {site['url']} is configured as crawl-only. Enforcing crawl-only mode")
        crawler_options['crawl_only'] = True
        crawler_options['visual_check_only'] = False
        crawler_options['create_baseline'] = False
    
    return _perform_check(site_id, site, crawler_options)

def schedule_website_monitoring_tasks():
    """Loads websites and schedules monitoring tasks for active ones."""
    logger.info("SCHEDULER: Loading websites and setting up monitoring schedules...")
    schedule.clear() # Clear any existing schedules before setting new ones

    try:
        # Use the instantiated manager
        all_websites_map = website_manager.list_websites() # Get all to check active status internally
        active_websites = [site for site_id, site in all_websites_map.items() if site.get('is_active', True)]
    except Exception as e:
        logger.error(f"SCHEDULER: Failed to load website list: {e}", exc_info=True)
        active_websites = []

    if not active_websites:
        logger.warning("SCHEDULER: No active websites found to schedule.")
        return

    default_interval = config.get('default_monitoring_interval_hours', 24)
    successful_schedules = 0

    for site in active_websites:
        site_id = site.get('id')
        site_name = site.get('name', site.get('url'))
        interval = site.get('interval', default_interval)

        if not site_id:
            logger.error(f"SCHEDULER: Skipping site due to missing ID: {site_name}")
            continue
        
        if not isinstance(interval, (int, float)) or interval <= 0:
            logger.warning(f"SCHEDULER: Invalid monitoring interval ({interval} hours) for {site_name} (ID: {site_id}). Using default: {default_interval} hours.")
            interval = default_interval

        try:
            logger.info(f"SCHEDULER: Scheduling check for {site_name} (ID: {site_id}) every {interval} hours.")
            # The `schedule` library uses a fluent API.
            schedule.every(interval).hours.do(perform_website_check, site_id=site_id)
            successful_schedules += 1
        except Exception as e:
            logger.error(f"SCHEDULER: Error scheduling task for {site_name} (ID: {site_id}): {e}", exc_info=True)
    
    logger.info(f"SCHEDULER: Successfully scheduled tasks for {successful_schedules}/{len(active_websites)} active websites.")
    if successful_schedules > 0:
        logger.info(f"SCHEDULER: Next run for scheduled tasks: {schedule.next_run()}")

def run_scheduler():
    """Runs the main scheduling loop. Handles graceful shutdown."""
    logger.info("SCHEDULER: Initializing and scheduling tasks...")
    # Ensure managers are ready (already instantiated at module level)
    if not website_manager or not history_manager:
        logger.error("SCHEDULER: WebsiteManager or HistoryManager not initialized. Cannot start scheduler.")
        return

    schedule_website_monitoring_tasks() # Initial setup of schedules
    
    logger.info("SCHEDULER: Starting main scheduling loop. Waiting for scheduled tasks or shutdown signal.")
    
    next_run_time = schedule.next_run()
    if next_run_time:
        logger.info(f"SCHEDULER: Next scheduled run at: {next_run_time}")
    else:
        logger.info("SCHEDULER: No tasks scheduled initially.")

    while not _shutdown_event.is_set():
        try:
            # schedule.run_pending() is non-blocking
            schedule.run_pending()
            
            # Wait for a short interval or until shutdown event is set
            # This makes the loop responsive to the shutdown signal
            # Check more frequently if the next job is soon, but at most every 60s
            idle_seconds = schedule.idle_seconds()
            if idle_seconds is None: # No jobs scheduled
                wait_time = 60 
            elif idle_seconds <= 0: # A job is due
                wait_time = 0.1 # Short wait, then run_pending will execute
            else:
                wait_time = min(idle_seconds, 60) # Wait up to 60s or until next job
            
            # The actual wait with shutdown check
            if _shutdown_event.wait(timeout=wait_time):
                break # Shutdown event was set

        except Exception as e:
            logger.error(f"SCHEDULER: An error occurred in the main scheduling loop: {e}", exc_info=True)
            # Avoid busy-looping on persistent errors
            if _shutdown_event.wait(timeout=60): # Wait 60s or until shutdown
                break

    logger.info("SCHEDULER: Shutdown signal received or no more tasks. Exiting scheduler loop.")
    schedule.clear() # Clear all schedules
    logger.info("SCHEDULER: All scheduled tasks cleared. Scheduler stopped.")

def _perform_check(site_id, site, crawler_options=None):
    """
    Perform the actual check of a website, including crawling and comparison.
    
    Args:
        site_id (str): ID of website to check
        site (dict): Website data
        crawler_options (dict): Crawler options
        
    Returns:
        dict: Results of the check
    """
    logger.info(f"MONITOR_TASK: Initiating check for site_id: {site_id}")
    
    if not site:
        logger.error(f"MONITOR_TASK: Site data is missing for ID {site_id}")
        return {"status": "error", "message": "Site data missing"}
    
    url = site.get('url')
    if not url:
        logger.error(f"MONITOR_TASK: URL missing for site ID {site_id}")
        return {"status": "error", "message": "URL missing"}
    
    # Check if this is a crawl-only website
    website_is_crawl_only = site.get('crawl_only', False)
    
    # Set default crawler options if needed
    if crawler_options is None:
        crawler_options = {}
        
    # If site is crawl-only, enforce crawl_only=True regardless of what was passed
    if website_is_crawl_only:
        crawler_options['crawl_only'] = True
        crawler_options['visual_check_only'] = False
        crawler_options['create_baseline'] = False
    
    # Perform crawler operations
    try:
        # Configure crawler options
        max_depth = crawler_options.get('max_depth', 2)
        crawl_only = crawler_options.get('crawl_only', website_is_crawl_only)
        visual_check_only = crawler_options.get('visual_check_only', False)
        create_baseline = crawler_options.get('create_baseline', False)
        
        # Ensure we're not doing visual checks for crawl-only sites
        if website_is_crawl_only:
            visual_check_only = False
            create_baseline = False
            
        logger.info(f"MONITOR_TASK [{url}]: Starting crawler with options: max_depth={max_depth}, crawl_only={crawl_only}, visual_check_only={visual_check_only}, create_baseline={create_baseline}")
        
        # Use the crawler module
        crawler = CrawlerModule()
        
        # If create_baseline is true, ensure we capture a snapshot
        if create_baseline and not website_is_crawl_only:
            logger.info(f"MONITOR_TASK [{url}]: Creating new baseline")
            website_manager = WebsiteManager()
            baseline_success = website_manager.capture_baseline_for_site(site_id)
            if not baseline_success:
                logger.warning(f"MONITOR_TASK [{url}]: Failed to create baseline")
        
        # Execute crawler
        crawler_results = crawler.crawl_website(
            site_id, 
            url,
            max_depth=max_depth,
            respect_robots=True,
            check_external_links=True,
            crawl_only=crawl_only,
            visual_check_only=visual_check_only,
            create_baseline=create_baseline and not website_is_crawl_only
        )
        
        # Log crawler results
        if crawler_results:
            logger.info(f"MONITOR_TASK [{url}]: Crawler completed. Found {len(crawler_results.get('broken_links', []))} broken links, {len(crawler_results.get('missing_meta_tags', []))} missing meta tags, and {len(crawler_results.get('all_pages', []))} total pages.")
        else:
            logger.warning(f"MONITOR_TASK [{url}]: Crawler returned no results")
            
        # Create results object with crawler data
        results = {
            "status": "success",
            "url": url,
            "crawl_data": crawler_results,
            "broken_links": len(crawler_results.get('broken_links', [])),
            "missing_meta_tags": len(crawler_results.get('missing_meta_tags', [])),
            "total_pages": len(crawler_results.get('all_pages', [])),
            "timestamp": datetime.now().isoformat()
        }
        
        # Update website's last_checked timestamp
        website_manager = WebsiteManager()
        website_manager.update_website(site_id, {"last_checked_utc": datetime.now(timezone.utc).isoformat()})
        
        # Save results to history - using the correct method add_check_record
        history_manager = HistoryManager()
        history_manager.add_check_record(
            site_id=site_id,
            status="success",
            html_snapshot_path=None,  # We're not capturing snapshots here
            html_content_hash=None,
            visual_snapshot_path=None,
            check_type="crawl_only" if website_is_crawl_only else "full",
            crawl_results={
                "broken_links": len(crawler_results.get('broken_links', [])),
                "missing_meta_tags": len(crawler_results.get('missing_meta_tags', [])),
                "total_pages": len(crawler_results.get('all_pages', []))
            }
        )
        
        # Send notification if needed
        if (len(crawler_results.get('broken_links', [])) > 0 or len(crawler_results.get('missing_meta_tags', [])) > 0) and site.get('notification_emails'):
            try:
                notification_emails = site.get('notification_emails', [])
                if notification_emails:
                    logger.info(f"MONITOR_TASK [{url}]: Sending notification to {', '.join(notification_emails)}")
                    alerter.send_email_alert(
                        site, 
                        f"Website Monitor Alert: Issues Found on {site.get('name', url)}",
                        f"The following issues were found on your website {url}:\n\n" +
                        f"- {len(crawler_results.get('broken_links', []))} broken links\n" +
                        f"- {len(crawler_results.get('missing_meta_tags', []))} missing meta tags\n\n" +
                        f"Please check the dashboard for more details."
                    )
            except Exception as e:
                logger.error(f"MONITOR_TASK [{url}]: Failed to send notification: {e}")
        
        return results
    except Exception as e:
        logger.error(f"MONITOR_TASK [{url}]: Error performing check: {e}", exc_info=True)
        
        # Save error to history - using the correct method add_check_record
        history_manager = HistoryManager()
        history_manager.add_check_record(
            site_id=site_id,
            status="error",
            html_snapshot_path=None,
            html_content_hash=None,
            visual_snapshot_path=None,
            check_type="crawl_only" if website_is_crawl_only else "full",
            error_message=str(e)
        )
        
        return {
            "status": "failed_fetch",
            "error_message": str(e),
            "url": url
        }

if __name__ == '__main__':
    logger.info("----- Scheduler Service Starting -----")
    
    # Ensure necessary config for testing 'perform_website_check'
    # e.g. meta_tags_to_check, content_change_threshold etc.
    if 'meta_tags_to_check' not in config:
        config['meta_tags_to_check'] = ['description', 'keywords'] # default for demo
    if 'content_change_threshold' not in config:
        config['content_change_threshold'] = 0.95
    if 'structure_change_threshold' not in config:
        config['structure_change_threshold'] = 0.98
    if 'visual_difference_threshold' not in config:
        config['visual_difference_threshold'] = 0.05

    if not website_manager.list_websites():
        logger.info("Scheduler Demo: No websites found. Adding some test websites for full check demo.")
        # Using a very short interval for testing the full check cycle.
        # Make sure example.com is accessible and renders.
        site_to_check = website_manager.add_website("https://example.com", "Example Domain Check", monitoring_interval_hours=0.002, tags=["full_check_test"])
        # Add another one to ensure scheduling loop works for multiple
        website_manager.add_website("https://www.google.com", "Google Check", monitoring_interval_hours=0.004, is_active=True)
        if site_to_check:
             logger.info(f"Added https://example.com with ID {site_to_check['id']} for quick testing.")
        else:
            logger.error("Failed to add test site for demo.")
    
    run_scheduler()
    logger.info("----- Scheduler Service Terminated -----") 