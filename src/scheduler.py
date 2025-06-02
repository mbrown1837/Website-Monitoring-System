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

logger = setup_logging()
config = get_config()

# Instantiate managers for the scheduler's own use
# These will use the default application configuration
website_manager = WebsiteManager() 
history_manager = HistoryManager()

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
def perform_website_check(site_id: str):
    """Performs a full check for a given website ID."""
    logger.info(f"MONITOR_TASK: Initiating check for site_id: {site_id}")
    # Use the instantiated manager
    site_details = website_manager.get_website(site_id) 
    if not site_details:
        logger.error(f"MONITOR_TASK: Site ID {site_id} not found. Cannot perform check.")
        return {
            "site_id": site_id,
            "status": "error",
            "error_message": f"Site ID {site_id} not found.",
            "significant_change_detected": False # Ensure this key exists
        }

    url = site_details['url']
    current_ts = datetime.now(timezone.utc)
    # Result dictionary for this check
    check_outcome = {
        "site_id": site_id, 
        "url": url,
        "timestamp_utc": current_ts.isoformat(),
        "status": "pending", # Initial status
        "changes_detected": False,
        "error_message": None
    }


    # Use the instantiated manager
    old_check_record = history_manager.get_latest_check_for_site(site_id)

    # Determine if we are using a baseline or the last check for comparison
    use_baseline_for_comparison = False
    old_html_content_for_comparison = ""
    old_visual_path_for_comparison = None
    comparison_source_log = ""
    old_html_content_source_for_log = "None (no baseline or prior history eligible for comparison)"

    if site_details.get('baseline_html_path') and os.path.exists(site_details['baseline_html_path']):
        logger.info(f"MONITOR_TASK [{url}]: Found baseline HTML at {site_details['baseline_html_path']}. Attempting to use it for comparison.")
        try:
            with open(site_details['baseline_html_path'], 'r', encoding='utf-8') as f:
                old_html_content_for_comparison = f.read()
            # We can still note the last check ID if available, even if comparing against baseline content
            if old_check_record:
                 check_outcome['compared_with_check_id'] = old_check_record.get('check_id') # Or a new field like 'based_on_last_check_id'
                 check_outcome['compared_against_baseline_html_hash'] = site_details.get('baseline_html_hash')
            use_baseline_for_comparison = True
            comparison_source_log = "baseline HTML"
            old_html_content_source_for_log = f"Baseline HTML: {site_details['baseline_html_path']}"
        except Exception as e:
            logger.error(f"MONITOR_TASK [{url}]: Error reading baseline HTML snapshot {site_details['baseline_html_path']}: {e}. Falling back to last check if available.")
            old_html_content_for_comparison = "" # Reset on error
            old_html_content_source_for_log = "Error reading baseline, attempting fallback."
    
    if site_details.get('baseline_visual_path') and os.path.exists(site_details['baseline_visual_path']):
        logger.info(f"MONITOR_TASK [{url}]: Found baseline visual snapshot at {site_details['baseline_visual_path']}. Using it for visual comparison.")
        old_visual_path_for_comparison = site_details['baseline_visual_path']
        use_baseline_for_comparison = True # If either HTML or visual baseline is used
        comparison_source_log += (" and baseline visual" if comparison_source_log else "baseline visual")
    
    # Fallback to last check if baseline content wasn't loaded or if only visual baseline was found (need HTML too)
    if not old_html_content_for_comparison:
        valid_comparison_statuses = ["initial_check_completed", "completed_no_changes", "completed_with_changes", "baseline_captured"]
        if old_check_record and old_check_record.get('status') in valid_comparison_statuses and old_check_record.get('html_snapshot_path'):
            old_html_path_from_history = old_check_record.get('html_snapshot_path')
            if old_html_path_from_history and os.path.exists(old_html_path_from_history):
                logger.info(f"MONITOR_TASK [{url}]: Using HTML from last check ID: {old_check_record['check_id']} (Status: {old_check_record.get('status')}) at path {old_html_path_from_history}")
                try:
                    with open(old_html_path_from_history, 'r', encoding='utf-8') as f:
                        old_html_content_for_comparison = f.read()
                    check_outcome['compared_with_check_id'] = old_check_record['check_id']
                    comparison_source_log = "last check's HTML"
                    old_html_content_source_for_log = f"Last check's HTML: {old_html_path_from_history} (Check ID: {old_check_record['check_id']})"
                except Exception as e:
                    logger.error(f"MONITOR_TASK [{url}]: Error reading old HTML snapshot {old_html_path_from_history} from history: {e}")
                    old_html_content_source_for_log = f"Error reading last check's HTML: {old_html_path_from_history}"
            else:
                logger.warning(f"MONITOR_TASK [{url}]: Last check's HTML snapshot not found or path missing: {old_html_path_from_history}")
                old_html_content_source_for_log = f"Last check's HTML path missing/invalid: {old_html_path_from_history}"
        else:
            logger.info(f"MONITOR_TASK [{url}]: No suitable baseline or previous check HTML found for comparison (Old check record: {bool(old_check_record)}, Status: {old_check_record.get('status') if old_check_record else 'N/A'}).")
            old_html_content_source_for_log = "No valid baseline or previous history HTML found."
    
    # Visual comparison: use baseline visual if available, otherwise fallback to last check's visual if HTML also came from last check
    if not old_visual_path_for_comparison: # If baseline visual was not used
        if old_check_record and old_check_record.get('visual_snapshot_path') and check_outcome.get('compared_with_check_id') == old_check_record.get('check_id'):
            # Only use last check's visual if we are also using its HTML
            old_visual_path_from_history = old_check_record.get('visual_snapshot_path')
            if old_visual_path_from_history and os.path.exists(old_visual_path_from_history):
                logger.info(f"MONITOR_TASK [{url}]: Using visual snapshot from last check ID: {old_check_record['check_id']}")
                old_visual_path_for_comparison = old_visual_path_from_history
                comparison_source_log += (" and last check's visual" if comparison_source_log else "last check's visual")
            else:
                logger.warning(f"MONITOR_TASK [{url}]: Last check's visual snapshot not found or path missing: {old_visual_path_from_history}")
        else:
            logger.info(f"MONITOR_TASK [{url}]: No suitable baseline or previous check visual found for comparison.")


    # 1. Retrieve Content
    logger.info(f"MONITOR_TASK [{url}]: Fetching content...")
    status_code, content_type, new_html_content, fetch_error = content_retriever.fetch_website_content(url)
    
    if fetch_error or not new_html_content:
        logger.error(f"MONITOR_TASK [{url}]: Failed to fetch content. Error: {fetch_error}")
        check_outcome.update({"status": "failed_fetch", "error_message": fetch_error})
        history_manager.add_check_record(
            site_id=site_id, 
            status="failed_fetch", 
            errors=fetch_error,
            url=url # Add url to history for context
        )
        website_manager.update_website(site_id, {"last_checked_utc": current_ts.isoformat(), "last_status": "Failed Fetch"})
        return check_outcome # Return the outcome for app.py

    check_outcome["fetch_status_code"] = status_code

    # 2. Create Snapshots of Current Content
    logger.info(f"MONITOR_TASK [{url}]: Saving HTML snapshot...")
    html_snapshot_path, html_content_hash = snapshot_tool.save_html_snapshot(site_id, url, new_html_content, current_ts)
    check_outcome["html_snapshot_path"] = html_snapshot_path
    check_outcome["html_content_hash"] = html_content_hash
    if not html_snapshot_path:
        logger.warning(f"MONITOR_TASK [{url}]: Failed to save HTML snapshot.")
        # Continue if possible, but log this as an issue.

    logger.info(f"MONITOR_TASK [{url}]: Saving visual snapshot...")
    visual_snapshot_path = snapshot_tool.save_visual_snapshot(site_id, url, current_ts)
    check_outcome["visual_snapshot_path"] = visual_snapshot_path
    if not visual_snapshot_path:
        logger.warning(f"MONITOR_TASK [{url}]: Failed to save visual snapshot.")

    # 3. Comparisons (if there is a previous check or baseline to compare against)
    if old_html_content_for_comparison:
        logger.info(f"MONITOR_TASK [{url}]: Comparing current content with {comparison_source_log}. Source of old HTML for comparison: {old_html_content_source_for_log}")
        comparison_results_dict = {} 

        # HTML content based comparisons
        comparison_results_dict['content_diff_score'], comparison_results_dict['content_diff_details'] = comparators.compare_html_text_content(old_html_content_for_comparison, new_html_content)
        old_text_for_semantic = comparators.extract_text_from_html(old_html_content_for_comparison)
        new_text_for_semantic = comparators.extract_text_from_html(new_html_content)
        if old_text_for_semantic or new_text_for_semantic: # Proceed if at least one has text
            semantic_sim_score, semantic_diffs = comparators.compare_text_semantic(old_text_for_semantic, new_text_for_semantic)
            comparison_results_dict['semantic_diff_score'] = semantic_sim_score
            # Convert semantic_diffs to a JSON-serializable format (list of lists)
            comparison_results_dict['semantic_diff_details'] = [[op, text] for op, text in semantic_diffs]
        else:
            logger.debug(f"MONITOR_TASK [{url}]: Both old and new HTML yielded no text for semantic comparison.")
            comparison_results_dict['semantic_diff_score'] = 1.0 # No text means no change in text
            comparison_results_dict['semantic_diff_details'] = []

        comparison_results_dict['structure_diff_score'], comparison_results_dict['structure_diff_details'] = comparators.compare_html_structure(old_html_content_for_comparison, new_html_content)
        comparison_results_dict['meta_changes'] = comparators.compare_meta_tags(old_html_content_for_comparison, new_html_content, config.get('meta_tags_to_check', ['description', 'keywords']))
        
        # Convert sets to lists for link_changes
        link_changes_raw = comparators.compare_links(old_html_content_for_comparison, new_html_content)
        comparison_results_dict['link_changes'] = {
            k: list(v) if isinstance(v, set) else v 
            for k, v in link_changes_raw.items()
        }

        # Convert sets to lists for image_src_changes
        image_src_changes_raw = comparators.compare_image_sources(old_html_content_for_comparison, new_html_content)
        comparison_results_dict['image_src_changes'] = {
            k: list(v) if isinstance(v, set) else v
            for k, v in image_src_changes_raw.items()
        }
        
        comparison_results_dict['canonical_url_change'] = comparators.compare_canonical_urls(old_html_content_for_comparison, new_html_content)
        
        # Visual comparison using selected old_visual_path_for_comparison
        if old_visual_path_for_comparison and os.path.exists(old_visual_path_for_comparison) and visual_snapshot_path and os.path.exists(visual_snapshot_path):
            diff_img_save_dir = os.path.join(snapshot_tool.get_snapshot_directory(), site_id, "diffs")
            os.makedirs(diff_img_save_dir, exist_ok=True)
            diff_img_filename = f"diff_{current_ts.strftime('%Y%m%d_%H%M%S_%f')}.png"
            diff_img_full_path = os.path.join(diff_img_save_dir, diff_img_filename)

            # Get ignore regions from config
            ignore_regions_global = config.get('visual_comparison_ignore_regions', [])
            # TODO: Implement per-site ignore regions and merge with global if needed
            # current_site_config_ignore_regions = site_details.get('config', {}).get('visual_ignore_regions', [])
            # effective_ignore_regions = ignore_regions_global + current_site_config_ignore_regions
            effective_ignore_regions = ignore_regions_global
            
            # MSE based comparison
            mse_score, _ = comparators.compare_screenshots(
                old_visual_path_for_comparison, 
                visual_snapshot_path, 
                diff_image_path=diff_img_full_path,
                ignore_regions=effective_ignore_regions
            )
            comparison_results_dict['visual_diff_score'] = float(mse_score) if mse_score is not None else None # visual_diff_score is MSE
            if mse_score is not None and mse_score > 0:
                 comparison_results_dict['visual_diff_image_path'] = diff_img_full_path
            
            # Perform SSIM comparison if libraries are available
            if comparators.OPENCV_SKIMAGE_AVAILABLE:
                ssim_val = comparators.compare_screenshots_ssim(
                    old_visual_path_for_comparison, 
                    visual_snapshot_path, 
                    ignore_regions=effective_ignore_regions
                )
                if ssim_val is not None:
                    comparison_results_dict['ssim_score'] = float(ssim_val)
                    logger.info(f"MONITOR_TASK [{url}]: SSIM comparison score: {ssim_val:.4f}")
                else:
                    logger.warning(f"MONITOR_TASK [{url}]: SSIM comparison returned None.")
            else:
                logger.debug(f"MONITOR_TASK [{url}]: OpenCV/scikit-image not available. Skipping SSIM comparison.")

        elif not old_visual_path_for_comparison:
             logger.warning(f"MONITOR_TASK [{url}]: Current visual snapshot not taken, cannot compare visuals.")

        # Determine significance based on the collected comparison results
        is_significant = determine_significance(comparison_results_dict, site_details)
        check_outcome['significant_change_detected'] = is_significant
        check_outcome['status'] = "completed_with_changes" if is_significant else "completed_no_changes"
        
        # Update check_outcome with all comparison results for history logging
        check_outcome.update(comparison_results_dict)

    else: # This is the first successful check AND no baseline was found for comparison
        logger.info(f"MONITOR_TASK [{url}]: This is the initial successful check. No comparison performed because no valid old HTML content was available. Source evaluated for old HTML: {old_html_content_source_for_log}")
        check_outcome['status'] = "initial_check_completed"
        check_outcome['significant_change_detected'] = config.get('alert_on_initial_check', False)

    # 4. Log Check Record
    # The history_manager.add_check_record will take care of most details
    # We need to pass all relevant pieces from `check_outcome` and `snapshot_results`
    history_add_payload = {
        "site_id": site_id,
        "url": url,
        "status": check_outcome['status'],
        "html_snapshot_path": check_outcome.get("html_snapshot_path"),
        "html_content_hash": check_outcome.get("html_content_hash"),
        "visual_snapshot_path": check_outcome.get("visual_snapshot_path"),
        "fetch_status_code": check_outcome.get('fetch_status_code'),
        "content_diff_score": check_outcome.get('content_diff_score'),
        "content_diff_details": check_outcome.get('content_diff_details'),
        "structure_diff_score": check_outcome.get('structure_diff_score'),
        "structure_diff_details": check_outcome.get('structure_diff_details'),
        "semantic_diff_score": check_outcome.get('semantic_diff_score'),
        "semantic_diff_details": check_outcome.get('semantic_diff_details'),
        "visual_diff_score": check_outcome.get('visual_diff_score'), # MSE
        "visual_diff_image_path": check_outcome.get('visual_diff_image_path'),
        "ssim_score": check_outcome.get('ssim_score'),
        "meta_changes": check_outcome.get('meta_changes'),
        "link_changes": check_outcome.get('link_changes'),
        "image_src_changes": check_outcome.get('image_src_changes'),
        "canonical_url_change": check_outcome.get('canonical_url_change'),
        "significant_change_detected": check_outcome['significant_change_detected'],
        "errors": check_outcome.get('error_message'),
        "compared_with_check_id": check_outcome.get('compared_with_check_id'),
        "compared_against_baseline_html_hash": check_outcome.get('compared_against_baseline_html_hash')
    }
    # Remove None values to keep history clean
    history_add_payload = {k: v for k, v in history_add_payload.items() if v is not None}

    final_check_record = history_manager.add_check_record(**history_add_payload)
    logger.info(f"MONITOR_TASK [{url}]: Check record {final_check_record['check_id']} saved with status: {check_outcome['status']}")
    check_outcome['check_id'] = final_check_record['check_id'] # Add check_id to outcome

    # 5. Update Website's Last Checked Info
    website_manager.update_website(site_id, {"last_checked_utc": current_ts.isoformat(), "last_status": check_outcome['status']})

    # 6. Send Alert for all checks, regardless of whether changes were detected
    logger.info(f"MONITOR_TASK [{url}]: Preparing notification for site check.")
    site_notification_emails = site_details.get('notification_emails', [])
    
    # Create appropriate subject
    if check_outcome['significant_change_detected']:
        subject_prefix = "Alert: Change Detected"
    else:
        subject_prefix = "Website Check Report"
        
    alert_subject, alert_html_body, alert_text_body = alerter.format_alert_message(
        site_url=url,
        site_name=site_details.get('name', url),
        check_record=final_check_record
    )
    
    # Override the subject to include the appropriate prefix
    alert_subject = f"{subject_prefix} - {site_details.get('name', url)}"
    
    # Send the email notification
    alerter.send_email_alert(
        alert_subject, 
        alert_html_body, 
        alert_text_body, 
        recipient_emails=site_notification_emails
    )
    
    logger.info(f"MONITOR_TASK: Check completed for site_id: {site_id}, URL: {url}")

    return check_outcome

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