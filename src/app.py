import os
import sys
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
from datetime import datetime, timezone
import threading
from urllib.parse import urlparse
import uuid # For task IDs
import humanize
from pathlib import Path

# Ensure src directory is in Python path
try:
    from .path_utils import get_project_root
except ImportError:
    # Fallback for direct execution
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.path_utils import get_project_root
project_root = get_project_root()
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.config_loader import get_config, save_config
from src.logger_setup import setup_logging
# Import managers
try:
    from .website_manager_sqlite import WebsiteManager
    from .history_manager_sqlite import HistoryManager
    from .crawler_module import CrawlerModule
except ImportError:
    # Fallback for direct execution
    from src.website_manager_sqlite import WebsiteManager
    from src.history_manager_sqlite import HistoryManager
    from src.crawler_module import CrawlerModule
from src.scheduler import perform_website_check, make_json_serializable
try:
    from .scheduler_integration import start_scheduler, stop_scheduler, get_scheduler_status, reschedule_tasks
except ImportError:
    # Fallback for direct execution
    from src.scheduler_integration import start_scheduler, stop_scheduler, get_scheduler_status, reschedule_tasks
from src.crawler_module import CrawlerModule # Import the crawler module
# from src.alerter import send_email_alert # For testing alerts

app = Flask(__name__, 
           template_folder=os.path.join(project_root, 'templates'),
           static_folder=os.path.join(project_root, 'static'))
app.secret_key = os.urandom(24) # For flash messages

logger = setup_logging(config_path='config/config.yaml') # Explicitly point to config for app
config = get_config(config_path='config/config.yaml')

# Initialize managers
website_manager = WebsiteManager(config_path='config/config.yaml')
history_manager = HistoryManager(config_path='config/config.yaml')
crawler_module = CrawlerModule(config_path='config/config.yaml')

# --- Task Management ---
tasks = {}

def run_background_task(task_id, target_func, *args, **kwargs):
    """Wrapper to run a function in a background thread and update task status."""
    logger.info(f"Starting background task: {task_id}")
    try:
        result = target_func(*args, **kwargs)
        tasks[task_id]['status'] = 'completed'
        tasks[task_id]['result'] = make_json_serializable(result)
        logger.info(f"Background task {task_id} completed successfully.")
    except Exception as e:
        logger.error(f"Background task {task_id} failed: {e}", exc_info=True)
        tasks[task_id]['status'] = 'failed'
        tasks[task_id]['error'] = str(e)

# --- Helper Functions ---
def get_app_config():
    # Reload config to ensure it's fresh, especially after edits
    return get_config(config_path='config/config.yaml')

def make_path_web_accessible(path_from_project_root):
    """
    Converts a relative path from the project root (e.g., 'data/snapshots/foo.png')
    to a path usable by the data_files endpoint (e.g., 'snapshots/foo.png').
    """
    try:
        from .path_utils import get_web_accessible_path
    except ImportError:
        # Fallback for direct execution
        from src.path_utils import get_web_accessible_path
    
    if not path_from_project_root or not isinstance(path_from_project_root, str):
        return None
    
    # Use the centralized path utility for web-accessible path conversion
    return get_web_accessible_path(path_from_project_root)

# --- Custom Jinja2 Filter ---
def humanize_timestamp(dt_str):
    """Humanize an ISO format datetime string."""
    if not dt_str:
        return "N/A"
    try:
        dt_utc = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        
        # If timezone-naive, assume it's UTC
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=timezone.utc)
        
        now = datetime.now(timezone.utc)
        time_diff = now - dt_utc
        
        return humanize.naturaltime(time_diff)
    except (ValueError, TypeError):
        return dt_str # Return original string if parsing fails

@app.template_filter('humanize_datetime')
def humanize_datetime_filter(dt_str, convert_to_local=True):
    """Humanize an ISO format datetime string."""
    return humanize_timestamp(dt_str)

# Make the function available in templates
app.jinja_env.globals['humanize_timestamp'] = humanize_timestamp

# --- Routes ---
@app.route('/')
def index():
    current_config = get_app_config()
    websites = website_manager.list_websites()
    
    # Initialize crawler module
    crawler = CrawlerModule(config_path='config/config.yaml')
    
    # Get crawler stats
    crawler_stats = {}
    active_sites = 0
    websites_with_issues = 0
    
    # Count active sites
    for site_id, site_data in websites.items():
        if site_data.get('is_active'):
            active_sites += 1
    
    # Get crawler stats for each website and mark sites with issues
    for site_id, site_data in websites.items():
        site_stats = crawler.get_latest_crawl_stats(site_id)
        crawler_stats[site_id] = {
            'broken_links_count': site_stats.get('total_broken_links', 0),
            'missing_meta_tags_count': site_stats.get('total_missing_meta_tags', 0),
            'total_pages_crawled': site_stats.get('pages_crawled', 0)
        }
        
        # Mark websites with issues
        has_issues = (crawler_stats[site_id]['broken_links_count'] > 0 or 
                      crawler_stats[site_id]['missing_meta_tags_count'] > 0)
        
        if has_issues:
            websites_with_issues += 1
            websites[site_id]['crawler_issues'] = True
    
    # Get blur detection statistics for websites that have it enabled
    blur_detection_stats = {}
    # BlurDetector import restored - syntax errors have been fixed
    from src.blur_detector import BlurDetector
    blur_detector = BlurDetector()
    
    for site_id, site_data in websites.items():
        if site_data.get('enable_blur_detection', False):
            try:
                blur_stats = blur_detector.get_blur_stats_for_website(site_id)
                blur_detection_stats[site_id] = blur_stats
            except Exception as e:
                logger.error(f"Error getting blur stats for website {site_id}: {e}")
                blur_detection_stats[site_id] = {
                    'total_images': 0,
                    'blurry_images': 0,
                    'avg_laplacian_score': 0,
                    'avg_blur_percentage': 0
                }
    
    return render_template('index.html', 
                           websites=websites, 
                           config=current_config, 
                           crawler_stats=crawler_stats,
                           blur_detection_stats=blur_detection_stats,
                           active_sites=active_sites,
                           websites_with_issues=websites_with_issues)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    current_config = get_app_config()
    if request.method == 'POST':
        try:
            # Update general settings
            current_config['log_level'] = request.form.get('log_level', current_config['log_level'])
            current_config['default_monitoring_interval_minutes'] = int(request.form.get('default_monitoring_interval_minutes', current_config.get('default_monitoring_interval_minutes', 60)))

            # Update Snapshot/Playwright settings
            current_config['snapshot_directory'] = request.form.get('snapshot_directory', current_config['snapshot_directory'])
            current_config['playwright_browser_type'] = request.form.get('playwright_browser_type', current_config['playwright_browser_type'])
            current_config['playwright_headless_mode'] = request.form.get('playwright_headless_mode') == 'True'
            current_config['playwright_user_agent'] = request.form.get('playwright_user_agent', current_config['playwright_user_agent'])
            current_config['playwright_render_delay_ms'] = int(request.form.get('playwright_render_delay_ms', current_config['playwright_render_delay_ms']))
            current_config['playwright_navigation_timeout_ms'] = int(request.form.get('playwright_navigation_timeout_ms', current_config['playwright_navigation_timeout_ms']))
            
            # New Percentage-based Threshold
            current_config['visual_change_alert_threshold_percent'] = float(request.form.get('visual_change_alert_threshold_percent', current_config.get('visual_change_alert_threshold_percent', 1.0)))
            
            # Update Notification (SMTP) settings
            current_config['notification_email_from'] = request.form.get('notification_email_from', current_config['notification_email_from'])
            current_config['notification_email_to'] = request.form.get('notification_email_to', current_config['notification_email_to'])
            current_config['smtp_server'] = request.form.get('smtp_server', current_config.get('smtp_server'))
            current_config['smtp_port'] = int(request.form.get('smtp_port', current_config.get('smtp_port', 587)))
            current_config['smtp_username'] = request.form.get('smtp_username', current_config.get('smtp_username'))
            current_config['smtp_password'] = request.form.get('smtp_password', current_config.get('smtp_password'))
            current_config['smtp_use_tls'] = request.form.get('smtp_use_tls') == 'True'

            # Update Comparison Thresholds
            # Convert percentage input from form (0-100) to decimal (0-1) for storage
            content_threshold_percent = float(request.form.get('content_change_threshold', current_config['content_change_threshold'] * 100))
            current_config['content_change_threshold'] = content_threshold_percent / 100.0
            
            structure_threshold_percent = float(request.form.get('structure_change_threshold', current_config['structure_change_threshold'] * 100))
            current_config['structure_change_threshold'] = structure_threshold_percent / 100.0
            
            current_config['visual_difference_threshold'] = float(request.form.get('visual_difference_threshold', current_config.get('visual_difference_threshold', 5.0)))
            current_config['meta_tags_to_check'] = [tag.strip() for tag in request.form.get('meta_tags_to_check', '').split(',') if tag.strip()]
            
            # Update Crawler settings
            current_config['crawler_max_depth'] = int(request.form.get('crawler_max_depth', current_config.get('crawler_max_depth', 2)))
            current_config['crawler_respect_robots'] = request.form.get('crawler_respect_robots') == 'True'
            current_config['crawler_check_external_links'] = request.form.get('crawler_check_external_links') == 'True'
            current_config['crawler_user_agent'] = request.form.get('crawler_user_agent', current_config.get('crawler_user_agent', 'SiteMonitor Bot'))

            # Update Performance Monitoring settings
            current_config['google_pagespeed_api_key'] = request.form.get('google_pagespeed_api_key', current_config.get('google_pagespeed_api_key', ''))

            save_config(current_config, config_path='config/config.yaml')
            flash('Settings updated successfully!', 'success')
            # Re-initialize logger and other services if settings affecting them changed
            global logger, website_manager, history_manager, config
            logger = setup_logging(config_path='config/config.yaml')
            config = get_config(config_path='config/config.yaml') # update global config
            website_manager = WebsiteManager(config_path='config/config.yaml') # Re-init with new config if needed
            history_manager = HistoryManager(config_path='config/config.yaml')

            return redirect(url_for('settings'))
        except Exception as e:
            logger.error(f"Error updating settings: {e}", exc_info=True)
            flash(f'Error updating settings: {str(e)}', 'danger')
            
    return render_template('settings.html', config=current_config)

@app.route('/admin/clear_scheduler_tasks', methods=['POST'])
def clear_scheduler_tasks():
    """Admin route to clear all scheduled tasks."""
    try:
        from src.scheduler_integration import clear_all_scheduler_tasks
        success = clear_all_scheduler_tasks()
        
        if success:
            flash('All scheduler tasks cleared successfully!', 'success')
            logger.info("Admin action: All scheduler tasks cleared")
        else:
            flash('Failed to clear scheduler tasks. Check logs for details.', 'warning')
            logger.warning("Admin action: Failed to clear scheduler tasks")
            
    except Exception as e:
        logger.error(f"Error clearing scheduler tasks: {e}", exc_info=True)
        flash(f'Error clearing scheduler tasks: {str(e)}', 'danger')
    
    return redirect(url_for('settings'))

@app.route('/website/add', methods=['GET', 'POST'])
def add_website():
    current_config = get_app_config()
    if request.method == 'POST':
        try:
            # Basic fields
            name = request.form['name']
            url = request.form['url']
            check_interval_minutes = int(request.form.get('check_interval_minutes', current_config.get('default_monitoring_interval_minutes', 60)))
            tags_str = request.form.get('tags', '')
            tags = [tag.strip() for tag in tags_str.split(',') if tag.strip()]
            notification_emails_str = request.form.get('notification_emails', '')
            notification_emails = [email.strip() for email in notification_emails_str.split(',') if email.strip()]
            exclude_pages_keywords_str = request.form.get('exclude_pages_keywords', '')
            exclude_pages_keywords = [keyword.strip() for keyword in exclude_pages_keywords_str.split(',') if keyword.strip()]
            
            # Advanced settings
            render_delay = int(request.form.get('render_delay', 6))
            max_crawl_depth = int(request.form.get('max_crawl_depth', 2))
            visual_diff_threshold = int(request.form.get('visual_diff_threshold', 5))
            
            # Legacy blur detection settings (removed from form, now controlled by automated monitoring)
            enable_blur_detection = False  # Now controlled by auto_blur_enabled
            blur_detection_scheduled = False  # Now controlled by auto_blur_enabled  
            blur_detection_manual = True  # Default to true for manual checks
            
            # Initial setup choice (only for new websites)
            initial_setup = request.form.get('initial_setup', 'baseline')
            
            # Automated monitoring preferences
            auto_crawl_enabled = request.form.get('auto_crawl_enabled') == 'on'
            auto_visual_enabled = request.form.get('auto_visual_enabled') == 'on'
            auto_blur_enabled = request.form.get('auto_blur_enabled') == 'on'
            auto_performance_enabled = request.form.get('auto_performance_enabled') == 'on'
            auto_full_check_enabled = request.form.get('auto_full_check_enabled') == 'on'
            
            # Handle Full Check option - when enabled, it enables all other monitoring types
            if auto_full_check_enabled:
                auto_crawl_enabled = True
                auto_visual_enabled = True
                auto_blur_enabled = True
                auto_performance_enabled = True
            
            if not name or not url:
                flash('Name and URL are required.', 'danger')
            else:
                # Clean and normalize URL to prevent data corruption
                url = url.strip()
                
                website_data = {
                    "url": url,
                    "name": name,
                    "check_interval_minutes": check_interval_minutes,
                    "is_active": True,
                    "tags": tags,
                    "notification_emails": notification_emails,
                    "exclude_pages_keywords": exclude_pages_keywords,
                        'render_delay': render_delay,
                        'max_crawl_depth': max_crawl_depth,
                        'visual_diff_threshold': visual_diff_threshold,
                    'enable_blur_detection': enable_blur_detection,
                    'blur_detection_scheduled': blur_detection_scheduled,
                    'blur_detection_manual': blur_detection_manual,
                    'auto_crawl_enabled': auto_crawl_enabled,
                    'auto_visual_enabled': auto_visual_enabled,
                    'auto_blur_enabled': auto_blur_enabled,
                    'auto_performance_enabled': auto_performance_enabled,
                    'auto_full_check_enabled': auto_full_check_enabled,
                    'capture_subpages': True
                }
                
                website = website_manager.add_website(website_data)
                
                if website:
                    reschedule_tasks()
                    
                    # Handle initial setup based on user choice
                    if initial_setup == 'none':
                        # Just add the website, no initial checks
                        flash(f'Website "{name}" added successfully. No initial checks were run.', 'success')
                        return redirect(url_for('index'))
                    elif initial_setup == 'baseline':
                        # Create baseline + run enabled automated checks for comparison data
                        task_id = str(uuid.uuid4())
                        tasks[task_id] = {
                            'status': 'pending',
                            'description': f'Creating baseline for {name}'
                        }
                        
                        logger.info(f"Creating baseline for new website ID: {website['id']} (Task ID: {task_id})")
                        
                        # Get the automated check configuration for this website
                        automated_check_config = website_manager.get_automated_check_config(website['id'])
                        
                        # For baseline creation, always enable crawl and visual, then add enabled automated checks
                        baseline_check_config = {
                            'crawl_enabled': True,  # Always needed for baseline
                            'visual_enabled': True,  # Always needed for visual baseline
                            'blur_enabled': automated_check_config.get('blur_enabled', False),
                            'performance_enabled': automated_check_config.get('performance_enabled', False)
                        }
                        
                        thread_args = (
                            website['id'],
                            {
                                'create_baseline': True,
                                'capture_subpages': True,
                                'check_config': baseline_check_config,
                                'is_scheduled': False  # This is a manual baseline creation, not a scheduled check
                            }
                        )
                        
                        # Add manager instances to args to fix database consistency (site_id, options, config_path, managers)
                        full_args = thread_args + ('config/config.yaml', website_manager, history_manager, crawler_module)
                        thread = threading.Thread(
                            target=run_background_task,
                            args=(task_id, perform_website_check) + full_args
                        )
                        thread.daemon = True
                        thread.start()
                        
                        flash(f'Website "{name}" added. Baseline creation started in the background.', 'success')
                        return redirect(url_for('index'))
                    elif initial_setup == 'full':
                        # Run full check with ALL monitoring types regardless of automation settings
                        task_id = str(uuid.uuid4())
                        tasks[task_id] = {
                            'status': 'pending',
                            'description': f'Full initial check for {name}'
                        }
                        
                        logger.info(f"Running full initial check for new website ID: {website['id']} (Task ID: {task_id})")
                        
                        # Force ALL checks regardless of user's automation settings (as per requirement)
                        check_config = {
                            'crawl_enabled': True,
                            'visual_enabled': True,
                            'blur_enabled': True,
                            'performance_enabled': True
                        }
                        logger.info(f"Using forced Full Check configuration for initial setup: {check_config}")
                        
                        thread_args = (
                            website['id'],
                            {
                                'create_baseline': not website.get('baseline_visual_path'),  # Create baseline if none exists
                                'capture_subpages': True,
                                'check_config': check_config,
                                'is_scheduled': False
                            }
                        )
                        
                        # Add manager instances to args to fix database consistency (site_id, options, config_path, managers)
                        full_args = thread_args + ('config/config.yaml', website_manager, history_manager, crawler_module)
                        thread = threading.Thread(
                            target=run_background_task,
                            args=(task_id, perform_website_check) + full_args
                        )
                        thread.daemon = True
                        thread.start()
                        
                        flash(f'Website "{name}" added. Full initial check started in the background.', 'success')
                        return redirect(url_for('index'))
        except Exception as e:
            logger.error(f"Error adding website: {e}", exc_info=True)
            flash(f'Error adding website: {str(e)}', 'danger')
    return render_template('website_form.html', website=None, config=current_config, form_action=url_for('add_website'))

@app.route('/website/edit/<site_id>', methods=['GET', 'POST'])
def edit_website(site_id):
    current_config = get_app_config()
    website = website_manager.get_website(site_id)
    if not website:
        flash(f'Website with ID "{site_id}" not found.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            # Parse basic fields
            notification_emails = [email.strip() for email in request.form.get('notification_emails', '').split(',') if email.strip()]
            exclude_pages_keywords = [keyword.strip() for keyword in request.form.get('exclude_pages_keywords', '').split(',') if keyword.strip()]
            
            # Parse advanced settings
            render_delay = int(request.form.get('render_delay', 6))
            max_crawl_depth = int(request.form.get('max_crawl_depth', 2))
            visual_diff_threshold = int(request.form.get('visual_diff_threshold', 5))
            
            # Legacy blur detection settings (removed from form, now controlled by automated monitoring)
            enable_blur_detection = False  # Now controlled by auto_blur_enabled
            blur_detection_scheduled = False  # Now controlled by auto_blur_enabled  
            blur_detection_manual = True  # Default to true for manual checks
            
            # Automated monitoring preferences
            auto_crawl_enabled = request.form.get('auto_crawl_enabled') == 'on'
            auto_visual_enabled = request.form.get('auto_visual_enabled') == 'on'
            auto_blur_enabled = request.form.get('auto_blur_enabled') == 'on'
            auto_performance_enabled = request.form.get('auto_performance_enabled') == 'on'
            auto_full_check_enabled = request.form.get('auto_full_check_enabled') == 'on'
            
            # Handle Full Check option - when enabled, it enables all other monitoring types
            if auto_full_check_enabled:
                auto_crawl_enabled = True
                auto_visual_enabled = True
                auto_blur_enabled = True
                auto_performance_enabled = True
            
            # Create update data
            updated_data = {
                'name': request.form['name'],
                'url': request.form['url'].strip(),  # Clean URL to prevent data corruption
                'check_interval_minutes': int(request.form.get('check_interval_minutes', website.get('check_interval_minutes'))),
                'tags': [tag.strip() for tag in request.form.get('tags', '').split(',') if tag.strip()],
                'notification_emails': notification_emails,
                'exclude_pages_keywords': exclude_pages_keywords,
                'is_active': request.form.get('is_active') == 'on',
                'render_delay': render_delay,
                'max_crawl_depth': max_crawl_depth,
                'visual_diff_threshold': visual_diff_threshold,
                'enable_blur_detection': enable_blur_detection,
                'blur_detection_scheduled': blur_detection_scheduled,
                'blur_detection_manual': blur_detection_manual,
                # Automated monitoring preferences
                'auto_crawl_enabled': auto_crawl_enabled,
                'auto_visual_enabled': auto_visual_enabled,
                'auto_blur_enabled': auto_blur_enabled,
                'auto_performance_enabled': auto_performance_enabled,
                'auto_full_check_enabled': auto_full_check_enabled
            }
            
            if not updated_data['name'] or not updated_data['url']:
                 flash('Name and URL are required.', 'danger')
            else:
                website_manager.update_website(site_id, updated_data)
                reschedule_tasks()
                flash(f'Website "{updated_data["name"]}" updated successfully!', 'success')
                return redirect(url_for('index'))
        except Exception as e:
            logger.error(f"Error updating website {site_id}: {e}", exc_info=True)
            flash(f'Error updating website: {str(e)}', 'danger')
    
    # Ensure tags are a string for the form
    website_form_data = website.copy()
    website_form_data['tags'] = ', '.join(website.get('tags', []))
    return render_template('website_form.html', website=website_form_data, config=current_config, form_action=url_for('edit_website', site_id=site_id))

@app.route('/website/remove/<site_id>', methods=['POST']) # Should be POST for destructive action
def remove_website(site_id):
    try:
        website = website_manager.get_website(site_id)
        if website:
            # Remove the website (this will also clean up the scheduler task)
            website_manager.remove_website(site_id)
            flash(f'Website "{website.get("name", site_id)}" and its scheduler task removed successfully!', 'success')
        else:
            flash(f'Website with ID "{site_id}" not found.', 'danger')
    except Exception as e:
        logger.error(f"Error removing website {site_id}: {e}", exc_info=True)
        flash(f'Error removing website: {str(e)}', 'danger')
    return redirect(url_for('index'))

@app.route('/website/history/<site_id>')
def website_history(site_id):
    """Displays the detailed history and baseline information for a single website."""
    current_config = get_app_config()
    website = website_manager.get_website(site_id)
    if not website:
        flash(f'Website with ID "{site_id}" not found.', 'danger')
        return redirect(url_for('index'))

    # PERMANENT FIX: Check for baseline files in filesystem if baseline_visual_path is missing
    if not website.get('baseline_visual_path'):
        import os
        from pathlib import Path
        
        # Try to find existing baseline files by scanning the snapshots directory
        snapshots_dir = Path('data/snapshots')
        website_id = site_id
        
        # Get all possible website directory names from the snapshots folder
        if snapshots_dir.exists():
            for website_dir in snapshots_dir.iterdir():
                if website_dir.is_dir():
                    # Check if this directory contains our website_id
                    website_id_dir = website_dir / website_id
                    if website_id_dir.exists() and website_id_dir.is_dir():
                        baseline_dir = website_id_dir / 'baseline'
                        if baseline_dir.exists():
                            # Look for baseline files
                            baseline_files = ['baseline_home.png', 'baseline.png', 'baseline_index.png']
                            for baseline_file in baseline_files:
                                baseline_path = baseline_dir / baseline_file
                                if baseline_path.exists():
                                    relative_path = str(baseline_path).replace('\\', '/')
                                    logger.info(f"PERMANENT FIX: Found existing baseline file for {website.get('name')}: {relative_path}")
                                    website['baseline_visual_path'] = relative_path
                                    # Update the database with the found baseline
                                    website_manager.update_website(site_id, {'baseline_visual_path': relative_path})
                                    break
                            if website.get('baseline_visual_path'):
                                break

    # Process main baseline information
    if website.get('baseline_visual_path'):
        website['baseline_visual_path_web'] = make_path_web_accessible(website['baseline_visual_path'])

    # Process subpage baselines
    subpage_baselines = []
    all_baselines = website.get('all_baselines', {})
    for url, baseline_data in all_baselines.items():
        # Skip the main URL, as it's handled separately
        if url == website.get('url'):
            continue
        
        processed_baseline = {
            'url': url,
            'path_web': make_path_web_accessible(baseline_data.get('path')),
            'timestamp': baseline_data.get('timestamp')
        }
        subpage_baselines.append(processed_baseline)
    
    # Sort subpages alphabetically by URL for consistent order
    subpage_baselines.sort(key=lambda x: x['url'])
    
    # Get and process history
    history = history_manager.get_history_for_site(site_id)
    processed_history = []
    for entry in history:
        # Make snapshot paths web-accessible
        if entry.get('latest_visual_snapshot_path'):
            entry['latest_visual_snapshot_path_web'] = make_path_web_accessible(entry['latest_visual_snapshot_path'])
        if entry.get('visual_diff_image_path'):
            entry['visual_diff_image_path_web'] = make_path_web_accessible(entry['visual_diff_image_path'])
        processed_history.append(entry)

    return render_template('history.html', 
                           website=website, 
                           history=processed_history,
                           subpage_baselines=subpage_baselines,
                           config=current_config)

@app.route('/website/<site_id>/manual_check', methods=['POST'])
def manual_check_website(site_id):
    """
    Manually trigger a check for a specific website using the queue system.
    Returns queue ID and status for real-time updates.
    """
    from src.queue_processor import get_queue_processor
    
    website = website_manager.get_website(site_id)
    if not website:
        return jsonify({'status': 'error', 'message': f'Website with ID "{site_id}" not found.'}), 404

    if not website.get('is_active', True):
        return jsonify({'status': 'error', 'message': f'Cannot check inactive website: {website.get("name")}. Please activate it first.'}), 400
        
    # Get check type from form or JSON
    if request.is_json:
        data = request.get_json()
        check_type = data.get('check_type', 'full')
        create_baseline = data.get('create_baseline', False)
    else:
        check_type = request.form.get('check_type', 'full')
        create_baseline = request.form.get('create_baseline') == 'true'
    
    # For baseline creation, use special check type
    if create_baseline:
        check_type = 'baseline'
    
    try:
        # Add check to queue
        queue_processor = get_queue_processor()
        queue_id = queue_processor.add_manual_check(site_id, check_type)
        
        # Get queue status
        queue_status = queue_processor.get_queue_status(queue_id=queue_id)
        
        if queue_status:
            status_info = queue_status[0]
            return jsonify({
                'status': 'success',
                'message': f'{check_type.title()} check queued for {website.get("name")}',
                'queue_id': queue_id,
                'queue_status': status_info['status'],
                'position': len(queue_processor.get_queue_status()) - 1,
                'estimated_time': 'Calculating...'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to add check to queue'
            }), 500
            
    except Exception as e:
        logger.error(f"Error adding manual check to queue: {e}")
    return jsonify({
            'status': 'error',
            'message': f'Failed to queue check: {str(e)}'
        }), 500

def perform_website_check_background(site_id, crawler_options):
    """DEPRECATED: This function is replaced by the new task management system."""
    logger.warning("perform_website_check_background is deprecated and should no longer be used.")
    pass

@app.route('/task/status/<task_id>')
def task_status(task_id):
    """Endpoint to check the status of a background task."""
    task = tasks.get(task_id)
    if not task:
        return jsonify({'status': 'not_found'}), 404
    
    response = {
        'status': task.get('status'),
        'description': task.get('description')
    }
    if task.get('status') == 'completed':
        response['result'] = task.get('result')
    elif task.get('status') == 'failed':
        response['error'] = task.get('error')
        
    return jsonify(response)

@app.route('/test_email')
def test_email():
    current_config = get_app_config()
    
    # Get SMTP configuration
    smtp_server = current_config.get('smtp_server')
    smtp_port = int(current_config.get('smtp_port', 587))
    smtp_username = current_config.get('smtp_username')
    smtp_password = current_config.get('smtp_password')
    smtp_use_tls = current_config.get('smtp_use_tls', True)
    smtp_use_ssl = current_config.get('smtp_use_ssl', False)
    
    # Get email addresses
    sender_email = current_config.get('notification_email_from')
    recipient_email = current_config.get('notification_email_to')
    
    # Validate basic requirements
    if not smtp_server or not sender_email or not recipient_email:
        flash('Missing SMTP configuration. Please fill in all required fields.', 'danger')
        return redirect(url_for('settings'))
    
    # Create message
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = 'Website Monitoring - Test Email'
    
    body = f"""
    <html>
    <body>
    <h2>Test Email from Website Monitoring System</h2>
    <p>This is a test email to verify that your SMTP configuration is working correctly.</p>
    <p>If you received this email, your SMTP settings are configured properly!</p>
    <hr>
    <p><strong>Configuration Details:</strong></p>
    <ul>
        <li>SMTP Server: {smtp_server}</li>
        <li>SMTP Port: {smtp_port}</li>
        <li>Using TLS: {smtp_use_tls}</li>
        <li>From: {sender_email}</li>
        <li>To: {recipient_email}</li>
    </ul>
    <p>You can now receive alerts when your monitored websites change.</p>
    </body>
    </html>
    """
    
    msg.attach(MIMEText(body, 'html'))
    
    try:
        # Connect to SMTP server - use SSL for port 465, regular SMTP for other ports
        if smtp_use_ssl:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
        server.ehlo()
        
        # Use TLS if configured
        if smtp_use_tls:
            server.starttls()
            server.ehlo()
            
        # Login if credentials provided
        if smtp_username and smtp_password:
            server.login(smtp_username, smtp_password)
            
        # Send email
        server.send_message(msg)
        server.quit()
        
        logger.info(f"Test email sent successfully to {recipient_email}")
        flash(f'Test email sent successfully to {recipient_email}. Please check your inbox.', 'success')
    except Exception as e:
        logger.error(f"Failed to send test email: {e}", exc_info=True)
        flash(f'Failed to send test email: {str(e)}', 'danger')
    
    return redirect(url_for('settings'))

@app.route('/website/<site_id>/crawler')
def website_crawler(site_id):
    current_config = get_app_config()
    website = website_manager.get_website(site_id)
    if not website:
        flash(f'Website with ID "{site_id}" not found.', 'danger')
        return redirect(url_for('index'))
    
    # Initialize the crawler module
    crawler = CrawlerModule(config_path='config/config.yaml')
    
    # Get the latest crawler results
    crawler_results = crawler.get_latest_crawl_results(site_id)
    
    # If no results found, run a crawl-only check automatically
    if not crawler_results:
        try:
            logger.info(f"No crawler results found for {website.get('name')} - running automatic crawl")
            
            # Determine appropriate max depth (start with more reasonable 2)
            max_depth = 2
            
            # Show message to user
            flash(f'Running initial crawl for "{website.get("name")}". This may take a moment...', 'info')
            
            # Check if this is a crawl_only website
            website_is_crawl_only = website.get('crawl_only', False)
            
            # Run the crawl with standard options
            crawler_results = crawler.crawl_website(
                site_id, 
                website.get('url'),
                max_depth=max_depth,
                respect_robots=True,
                check_external_links=True,
                crawl_only=True,  # Always set to True for initial crawl
                visual_check_only=False,  # Never do visual checks in initial crawl
                create_baseline=False  # Never create baseline in initial crawl
            )
            
            if crawler_results:
                total_pages = len(crawler_results.get("all_pages", []))
                flash(f'Initial crawl completed for "{website.get("name")}". Found {total_pages} pages with {len(crawler_results.get("broken_links", []))} broken links.', 'success')
            else:
                flash(f'No crawler results found for website "{website.get("name")}". Try running a manual check.', 'warning')
                return redirect(url_for('website_history', site_id=site_id))
                
        except Exception as e:
            logger.error(f"Error during automatic crawl: {e}", exc_info=True)
            flash(f'Error during automatic crawl: {str(e)}', 'danger')
            return redirect(url_for('website_history', site_id=site_id))
    
    # Get the crawl_id from the results
    crawl_id = crawler_results.get('crawl_id')
    
    # Extract broken links and missing meta tags
    broken_links = crawler_results.get('broken_links', [])
    missing_tags = crawler_results.get('missing_meta_tags', [])
    timestamp = crawler_results.get('timestamp', 'Unknown')
    
    # Get status code counts for the crawl
    status_counts = crawler.get_status_code_counts(crawl_id)
    
    # Apply filters if provided
    status_code_filter = request.args.get('status_code')
    search_url = request.args.get('search_url')
    link_type_filter = request.args.get('link_type')  # 'internal' or 'external'
    
    # Get all pages, filtered if needed
    all_pages_unfiltered = crawler.get_pages_by_status_code(crawl_id)
    
    # Calculate unfiltered counts for display in stats blocks
    total_pages_count = len(all_pages_unfiltered)
    internal_pages_count_total = len([p for p in all_pages_unfiltered if p.get('is_internal', True)])
    external_pages_count_total = len([p for p in all_pages_unfiltered if not p.get('is_internal', True)])
    broken_links_count_total = len(crawler_results.get('broken_links', []))
    missing_tags_count_total = len(crawler_results.get('missing_meta_tags', []))
    
    # Get blur detection statistics if enabled (check both old and new blur flags)
    blur_stats = None
    blur_enabled = (website.get('enable_blur_detection', False) or 
                   website.get('auto_blur_enabled', False))
    if blur_enabled:
        try:
            from src.blur_detector import BlurDetector
            blur_detector = BlurDetector()
            blur_stats = blur_detector.get_blur_stats_for_website(site_id)
        except Exception as e:
            logger.error(f"Error getting blur stats for website {site_id}: {e}")
            blur_stats = None
    
    # Apply filters for the displayed pages
    filtered_pages = all_pages_unfiltered
    
    if status_code_filter:
        try:
            status_code_filter = int(status_code_filter)
            filtered_pages = [page for page in filtered_pages if page.get('status_code') == status_code_filter]
        except ValueError:
            pass
    
    # Filter by URL if search query provided
    if search_url:
        filtered_pages = [page for page in filtered_pages if search_url.lower() in page.get('url', '').lower()]
        broken_links = [link for link in broken_links if search_url.lower() in link.get('url', '').lower()]
        missing_tags = [tag for tag in missing_tags if search_url.lower() in tag.get('url', '').lower()]
    
    # Filter by internal/external link type if specified
    if link_type_filter:
        if link_type_filter == 'internal':
            filtered_pages = [page for page in filtered_pages if page.get('is_internal', True)]
            broken_links = [link for link in broken_links if 
                           any(page.get('url') == link.get('url') and page.get('is_internal', True) 
                               for page in crawler_results.get('all_pages', []))]
        elif link_type_filter == 'external':
            filtered_pages = [page for page in filtered_pages if not page.get('is_internal', True)]
            broken_links = [link for link in broken_links if 
                           any(page.get('url') == link.get('url') and not page.get('is_internal', True) 
                               for page in crawler_results.get('all_pages', []))]
    
    # Calculate filtered counts
    filtered_internal_count = len([p for p in filtered_pages if p.get('is_internal', True)])
    filtered_external_count = len([p for p in filtered_pages if not p.get('is_internal', True)])
    
    return render_template('crawler_results.html',
                         website_name=website.get('name'),
                         website_url=website.get('url'),
                         website_id=site_id,
                         crawler_results=crawler_results,
                         status_counts=status_counts,
                         all_pages=filtered_pages,
                         filtered_pages_count=len(filtered_pages),
                         broken_links=broken_links,
                         missing_tags=missing_tags,
                         timestamp=timestamp,
                         internal_pages_count=filtered_internal_count,
                         external_pages_count=filtered_external_count,
                         total_pages_count=total_pages_count,
                         internal_pages_count_total=internal_pages_count_total,
                         external_pages_count_total=external_pages_count_total,
                         broken_links_count_total=broken_links_count_total,
                         missing_tags_count_total=missing_tags_count_total,
                         current_link_type=link_type_filter,
                         blur_stats=blur_stats)

@app.route('/website/<site_id>/broken-links')
def website_broken_links(site_id):
    current_config = get_app_config()
    website = website_manager.get_website(site_id)
    if not website:
        flash(f'Website with ID "{site_id}" not found.', 'danger')
        return redirect(url_for('index'))
    
    # Initialize the crawler module
    crawler = CrawlerModule(config_path='config/config.yaml')
    
    # Get the latest crawler results
    crawler_results = crawler.get_latest_crawl_results(site_id)
    
    if not crawler_results:
        # No crawler results found, show appropriate message
        flash(f'No crawler results found for website "{website.get("name")}". Try running a manual check.', 'warning')
        return redirect(url_for('website_history', site_id=site_id))
    
    # Extract broken links
    broken_links = crawler_results.get('broken_links', [])
    timestamp = crawler_results.get('timestamp', 'Unknown')
    
    # Apply filters if provided
    status_code_filter = request.args.get('status_code')
    search_url = request.args.get('search_url')
    
    if status_code_filter:
        try:
            status_code_filter = int(status_code_filter)
            broken_links = [link for link in broken_links if link.get('status_code') == status_code_filter]
        except ValueError:
            pass
    
    if search_url:
        broken_links = [link for link in broken_links if search_url.lower() in link.get('url', '').lower()]
    
    return render_template('broken_links.html',
                         website_name=website.get('name'),
                         website_url=website.get('url'),
                         website_id=site_id,
                         broken_links=broken_links,
                         timestamp=timestamp)

@app.route('/website/<site_id>/missing-meta-tags')
def website_missing_meta_tags(site_id):
    current_config = get_app_config()
    website = website_manager.get_website(site_id)
    if not website:
        flash(f'Website with ID "{site_id}" not found.', 'danger')
        return redirect(url_for('index'))
    
    # Initialize the crawler module
    crawler = CrawlerModule(config_path='config/config.yaml')
    
    # Get the latest crawler results
    crawler_results = crawler.get_latest_crawl_results(site_id)
    
    if not crawler_results:
        # No crawler results found, show appropriate message
        flash(f'No crawler results found for website "{website.get("name")}". Try running a manual check.', 'warning')
        return redirect(url_for('website_history', site_id=site_id))
    
    # Extract missing meta tags
    missing_tags = crawler_results.get('missing_meta_tags', [])
    timestamp = crawler_results.get('timestamp', 'Unknown')
    
    # Apply filters if provided
    tag_type_filter = request.args.get('tag_type')
    search_url = request.args.get('search_url')
    
    # Get unique tag types for the dropdown
    unique_tag_types = set()
    for tag in missing_tags:
        if 'tag_type' in tag:
            unique_tag_types.add(tag['tag_type'])
    
    # Apply tag type filter if provided
    if tag_type_filter:
        missing_tags = [tag for tag in missing_tags if tag.get('tag_type', '').lower() == tag_type_filter.lower()]
    
    # Apply URL search filter if provided
    if search_url:
        missing_tags = [tag for tag in missing_tags if search_url.lower() in tag.get('url', '').lower()]
    
    # Group issues by page for easier analysis and remove duplicates
    issues_by_page = {}
    unique_missing_tags = []
    
    # Track which URLs and tag types we've already seen
    seen_url_tag_types = set()
    
    for tag in missing_tags:
        url = tag.get('url', '')
        tag_type = tag.get('tag_type', '')
        
        # Create a unique identifier for this URL and tag type
        url_tag_key = f"{url}:{tag_type}"
        
        # Only add this tag if we haven't seen this URL and tag type combination before
        if url_tag_key not in seen_url_tag_types:
            seen_url_tag_types.add(url_tag_key)
            unique_missing_tags.append(tag)
            
            # Add to issues_by_page for the "By Page" view
            if url not in issues_by_page:
                issues_by_page[url] = []
            issues_by_page[url].append(tag)
    
    return render_template('missing_meta_tags.html',
                         website_name=website.get('name'),
                         website_url=website.get('url'),
                         website_id=site_id,
                         missing_tags=unique_missing_tags,
                         issues_by_page=issues_by_page,
                         unique_tag_types=sorted(unique_tag_types),
                         timestamp=timestamp)

@app.route('/website/<site_id>/summary')
def website_summary(site_id):
    """Display comprehensive summary of all website metrics and statistics."""
    current_config = get_app_config()
    website = website_manager.get_website(site_id)
    if not website:
        flash(f'Website with ID "{site_id}" not found.', 'danger')
        return redirect(url_for('index'))

    # Initialize modules
    crawler = CrawlerModule(config_path='config/config.yaml')
    
    # Get latest crawler results
    crawler_results = crawler.get_latest_crawl_results(site_id)
    
    # Get crawler statistics
    crawler_stats = crawler.get_latest_crawl_stats(site_id)
    
    # Get blur detection statistics if enabled (check both old and new blur flags)
    blur_stats = None
    blur_enabled = (website.get('enable_blur_detection', False) or 
                   website.get('auto_blur_enabled', False))
    if blur_enabled:
        try:
            from src.blur_detector import BlurDetector
            blur_detector = BlurDetector()
            blur_stats = blur_detector.get_blur_stats_for_website(site_id)
        except Exception as e:
            logger.error(f"Error getting blur stats for website {site_id}: {e}")
            blur_stats = None
    
    # Get website history summary
    history_summary = {
        'total_checks': 0,
        'last_check': None,
        'avg_response_time': 0,
        'uptime_percentage': 100,
        'visual_changes_detected': 0,
        'avg_visual_diff': 0,
        'max_visual_diff': 0
    }
    
    try:
        history = history_manager.get_history_for_site(site_id, limit=10)
        if history:
            history_summary['total_checks'] = len(history)
            history_summary['last_check'] = history[0].get('timestamp')
            
            # Calculate basic uptime (successful checks)
            successful_checks = sum(1 for h in history if h.get('status') == 'success')
            if len(history) > 0:
                history_summary['uptime_percentage'] = round((successful_checks / len(history)) * 100, 1)
            
            # Calculate visual change metrics
            visual_changes = [h for h in history if h.get('visual_diff_percent') is not None and h.get('visual_diff_percent', 0) > 0]
            history_summary['visual_changes_detected'] = len(visual_changes)
            
            if visual_changes:
                visual_diffs = [h.get('visual_diff_percent', 0) for h in visual_changes]
                history_summary['avg_visual_diff'] = round(sum(visual_diffs) / len(visual_diffs), 2)
                history_summary['max_visual_diff'] = round(max(visual_diffs), 2)
    except Exception as e:
        logger.error(f"Error getting history summary for website {site_id}: {e}")
    
    # Prepare summary data
    summary_data = {
        'website': website,
        'crawler_stats': crawler_stats,
        'crawler_results': crawler_results,
        'blur_stats': blur_stats,
        'history_summary': history_summary,
        'has_recent_data': crawler_results is not None
    }
    
    return render_template('website_summary.html', **summary_data)

@app.route('/website/<site_id>/blur-detection')
def website_blur_detection(site_id):
    """Display blur detection results for a specific website."""
    current_config = get_app_config()
    website = website_manager.get_website(site_id)
    if not website:
        flash(f'Website with ID "{site_id}" not found.', 'danger')
        return redirect(url_for('index'))

    # Check if blur detection is enabled (either old or new system)
    blur_enabled = (website.get('enable_blur_detection', False) or 
                   website.get('auto_blur_enabled', False))
    
    if not blur_enabled:
        flash(f'Blur detection is not enabled for website "{website.get("name")}". Enable blur detection in website settings first.', 'info')
        return redirect(url_for('website_history', site_id=site_id))

    # Get blur detection results
    from src.blur_detector import BlurDetector
    blur_detector = BlurDetector()
    
    # Find the latest crawl that has blur detection results
    crawler = CrawlerModule(config_path='config/config.yaml')
    
    # Get the latest crawl with blur detection results
    conn = blur_detector._get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT crawl_id FROM blur_detection_results 
            WHERE website_id = ? 
            ORDER BY crawl_id DESC 
            LIMIT 1
        ''', (site_id,))
        
        result = cursor.fetchone()
        if not result:
            flash(f'No blur detection results found for website "{website.get("name")}". Run a blur detection check first.', 'info')
            return redirect(url_for('website_history', site_id=site_id))
        
        crawl_id = result[0]
        
        # Get the crawl results for this crawl_id
        latest_results = crawler.get_crawl_results_by_id(crawl_id)
        if not latest_results:
            flash(f'Crawl results not found for blur detection data', 'info')
            return redirect(url_for('website_history', site_id=site_id))
            
    except Exception as e:
        flash(f'Error finding blur detection results: {str(e)}', 'danger')
        return redirect(url_for('website_history', site_id=site_id))
    finally:
        conn.close()
        
    # Get blur detection results for this crawl
    blur_results = blur_detector.get_blur_results_for_crawl(crawl_id)
    blur_stats = blur_detector.get_blur_stats_for_website(site_id)
    
    return render_template('blur_detection_results.html', 
                           website=website, 
                           blur_results=blur_results,
                           blur_stats=blur_stats,
                           latest_results=latest_results,
                           config=current_config)

@app.route('/website/<site_id>/performance')
def website_performance(site_id):
    """Display performance check results for a specific website."""
    
    def _get_performance_grade(score):
        """Convert numeric score to letter grade."""
        if score >= 90:
            return 'A'
        elif score >= 50:
            return 'B'
        else:
            return 'C'
    
    current_config = get_app_config()
    website = website_manager.get_website(site_id)
    if not website:
        flash(f'Website with ID "{site_id}" not found.', 'danger')
        return redirect(url_for('index'))

    # Get the latest performance results for each page and device type
    import sqlite3
    conn = sqlite3.connect('data/website_monitor.db')
    cursor = conn.cursor()
    
    # Get unique URLs for this website
    cursor.execute('''
        SELECT DISTINCT url, page_title 
        FROM performance_results 
        WHERE website_id = ? 
        ORDER BY url
    ''', (site_id,))
    urls = cursor.fetchall()
    
    # Create the data structure that the template expects
    performance_history = []
    
    if urls:
        # Get the latest timestamp for this website
        cursor.execute('''
            SELECT MAX(timestamp) 
            FROM performance_results 
            WHERE website_id = ?
        ''', (site_id,))
        latest_timestamp = cursor.fetchone()[0]
        
        # Create the structure the template expects
        latest_check = {
            'timestamp': latest_timestamp,
            'crawl_id': f'perf_{site_id}_{latest_timestamp}',
            'pages': []
        }
        
        for url, page_title in urls:
            # Get latest mobile and desktop results for this URL
            cursor.execute('''
                SELECT device_type, performance_score, fcp_display, lcp_display, cls_display, 
                       fid_display, speed_index_display, timestamp, fcp_score, lcp_score, 
                       cls_score, fid_score, speed_index, total_blocking_time
                FROM performance_results 
                WHERE website_id = ? AND url = ? 
                ORDER BY timestamp DESC
            ''', (site_id, url))
            results = cursor.fetchall()
            
            # Create page object with mobile and desktop data
            page_data = {
                'url': url,
                'page_title': page_title or url,
                    'mobile': None,
                    'desktop': None
                }
            
            # Group results by device type
            for result in results:
                device_type = result[0]
                device_data = {
                    'device_type': device_type,
                    'performance_score': result[1],
                    'performance_grade': _get_performance_grade(result[1]),
                    'fcp_display': result[2],
                    'fcp_score': result[8],
                    'lcp_display': result[3],
                    'lcp_score': result[9],
                    'cls_display': result[4],
                    'cls_score': result[10],
                    'fid_display': result[5],
                    'fid_score': result[11],
                    'speed_index_display': result[6],
                    'speed_index_score': result[12],
                    'tbt_display': f"{result[13]}ms" if result[13] else 'N/A',
                    'tbt_score': result[13] or 0
                }
                
                if device_type == 'mobile':
                    page_data['mobile'] = device_data
                elif device_type == 'desktop':
                    page_data['desktop'] = device_data
            
            # Add this page to the latest check
            latest_check['pages'].append(page_data)
        
        performance_history.append(latest_check)
    
    conn.close()
    
    # Check if performance monitoring is enabled for this website
    performance_enabled = website.get('auto_performance_enabled', True)
    
    return render_template('performance_results.html', 
                           website=website, 
                           performance_history=performance_history,
                         current_config=current_config,
                         performance_enabled=performance_enabled)

# --- API Endpoints (Optional, for AJAX or other integrations) ---
@app.route('/api/websites', methods=['GET'])
def api_list_websites():
    websites = website_manager.list_websites()
    return jsonify(websites)

@app.route('/api/website/<site_id>/history', methods=['GET'])
def api_website_history(site_id):
    limit = request.args.get('limit', default=get_app_config().get('dashboard_api_history_limit', 100), type=int)
    history_records = history_manager.get_history_for_site(site_id, limit=limit)
    if not history_records and not website_manager.get_website(site_id):
        return jsonify({"error": "Website not found"}), 404
    return jsonify(history_records)

@app.route('/health/dashboard')
def health_dashboard():
    """Health check dashboard page."""
    return render_template('health_dashboard.html')

@app.route('/env/config')
def env_config_dashboard():
    """Environment configuration dashboard page."""
    return render_template('env_config_dashboard.html')

@app.route('/api/scheduler/status', methods=['GET'])
def api_scheduler_status():
    """Get the current status of the scheduler."""
    status = get_scheduler_status()
    return jsonify(status)

@app.route('/api/scheduler/reload', methods=['POST'])
def api_scheduler_reload():
    """Reload scheduler configuration."""
    from src.scheduler_integration import reload_scheduler_config
    
    config_path = request.json.get('config_path', 'config/config.yaml') if request.is_json else 'config/config.yaml'
    success = reload_scheduler_config(config_path)
    
    if success:
        return jsonify({"status": "success", "message": f"Configuration reloaded from {config_path}"})
    else:
        return jsonify({"status": "error", "message": "Failed to reload configuration"}), 500

@app.route('/api/scheduler/logs', methods=['GET'])
def api_scheduler_logs():
    """Get recent scheduler logs."""
    from src.scheduler_db import get_scheduler_db_manager
    
    limit = request.args.get('limit', default=100, type=int)
    db_manager = get_scheduler_db_manager()
    logs = db_manager.get_recent_logs(limit=limit)
    
    return jsonify(logs)

@app.route('/api/scheduler/status/history', methods=['GET'])
def api_scheduler_status_history():
    """Get scheduler status history."""
    from .scheduler_db import get_scheduler_db_manager
    
    limit = request.args.get('limit', default=50, type=int)
    db_manager = get_scheduler_db_manager()
    history = db_manager.get_scheduler_status_history(limit=limit)
    
    return jsonify(history)

@app.route('/api/scheduler/database/test', methods=['GET'])
def api_scheduler_database_test():
    """Test scheduler database connection."""
    from .scheduler_db import test_scheduler_database
    
    success = test_scheduler_database()
    return jsonify({"database_connected": success})

# Health Check Endpoints
@app.route('/health', methods=['GET'])
def health_check():
    """Basic health check endpoint."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "Website Monitoring System"
    })

@app.route('/health/detailed', methods=['GET'])
def detailed_health_check():
    """Detailed health check with component status."""
    try:
        from .scheduler_integration import get_scheduler_status
        from .scheduler_db import test_scheduler_database
    except ImportError:
        # Fallback for direct execution
        from src.scheduler_integration import get_scheduler_status
        from src.scheduler_db import test_scheduler_database
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "Website Monitoring System",
        "components": {}
    }
    
    # Check database connectivity
    try:
        from .path_utils import get_data_directory, get_database_path
        data_dir = get_data_directory()
        db_path = get_database_path()
        
        data_dir_exists = data_dir.exists()
        import os
        db_dir_exists = os.path.dirname(db_path).exists()
        
        health_status["components"]["database"] = {
            "status": "healthy" if db_connected else "unhealthy",
            "connected": db_connected
        }
    except Exception as e:
        health_status["components"]["database"] = {
            "status": "error",
            "error": str(e)
        }
    
    # Check scheduler status
    try:
        scheduler_status = get_scheduler_status()
        health_status["components"]["scheduler"] = {
            "status": "healthy" if scheduler_status.get("running", False) else "stopped",
            "enabled": scheduler_status.get("enabled", False),
            "running": scheduler_status.get("running", False),
            "thread_alive": scheduler_status.get("thread_alive", False)
        }
    except Exception as e:
        health_status["components"]["scheduler"] = {
            "status": "error",
            "error": str(e)
        }
    
    # Check file system access
    try:
        from .path_utils import get_data_directory, clean_path_for_logging
        data_dir = get_data_directory()
        db_path = get_database_path()
        
        data_dir_exists = data_dir.exists()
        db_dir_exists = os.path.dirname(db_path).exists()
        
        health_status["components"]["filesystem"] = {
            "status": "healthy" if data_dir_exists and db_dir_exists else "warning",
            "data_directory": str(data_dir),
            "data_directory_exists": data_dir_exists,
            "database_directory_exists": db_dir_exists
        }
    except Exception as e:
        health_status["components"]["filesystem"] = {
            "status": "error",
            "error": str(e)
        }
    
    # Check configuration
    try:
        config = get_app_config()
        health_status["components"]["configuration"] = {
            "status": "healthy",
            "config_loaded": config is not None,
            "environment": config.get("environment", "unknown")
        }
    except Exception as e:
        health_status["components"]["configuration"] = {
            "status": "error",
            "error": str(e)
        }
    
    # Determine overall status
    overall_status = "healthy"
    for component, status in health_status["components"].items():
        if status.get("status") == "error":
            overall_status = "unhealthy"
            break
        elif status.get("status") == "warning":
            overall_status = "degraded"
    
    health_status["status"] = overall_status
    
    return jsonify(health_status)

@app.route('/health/ready', methods=['GET'])
def readiness_check():
    """Readiness check for Kubernetes/Docker orchestration."""
    try:
        from .scheduler_integration import get_scheduler_status
        from .scheduler_db import test_scheduler_database
    except ImportError:
        # Fallback for direct execution
        from src.scheduler_integration import get_scheduler_status
        from src.scheduler_db import test_scheduler_database
    
    # Check critical components
    checks = {
        "database": test_scheduler_database(),
        "scheduler": get_scheduler_status().get("running", False),
        "configuration": get_app_config() is not None
    }
    
    all_ready = all(checks.values())
    status_code = 200 if all_ready else 503
    
    return jsonify({
        "ready": all_ready,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }), status_code

@app.route('/health/live', methods=['GET'])
def liveness_check():
    """Liveness check for Kubernetes/Docker orchestration."""
    return jsonify({
        "alive": True,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

# Environment Configuration Endpoints
@app.route('/api/env/variables', methods=['GET'])
def api_env_variables():
    """API endpoint to list environment variables."""
    try:
        from .env_config import list_environment_variables
    except ImportError:
        # Fallback for direct execution
        from src.env_config import list_environment_variables
    
    env_vars = list_environment_variables()
    return jsonify(env_vars)

@app.route('/api/env/validate', methods=['GET'])
def api_env_validate():
    """Validate environment variable configuration."""
    try:
        from .env_config import validate_environment_config
    except ImportError:
        # Fallback for direct execution
        from src.env_config import validate_environment_config
    
    validation = validate_environment_config()
    return jsonify(validation)

@app.route('/api/env/overrides', methods=['GET'])
def api_env_overrides():
    """Get current environment variable overrides."""
    try:
        from .env_config import get_environment_overrides
    except ImportError:
        # Fallback for direct execution
        from src.env_config import get_environment_overrides
    
    overrides = get_environment_overrides()
    return jsonify(overrides)

# --- Dashboard Routes (Consolidated from dashboard_app.py) ---

@app.route('/site/<site_id>')
def site_details(site_id):
    """Site details page - consolidated from dashboard_app.py"""
    site = website_manager.get_website(site_id)
    if not site:
        return render_template('404.html', message=f"Site with ID {site_id} not found."), 404
    
    history_limit = config.get('dashboard_history_limit', 20)
    history_records = history_manager.get_history_for_site(site_id, limit=history_limit)
    
    return render_template('site_details.html', site=site, history=history_records)

@app.route('/site/<site_id>/run_check', methods=['POST'])
def run_manual_check_from_ui(site_id):
    """Manual check trigger from UI - consolidated from dashboard_app.py"""
    site = website_manager.get_website(site_id)
    if not site:
        flash(f'Website with ID "{site_id}" not found.', 'danger')
        return redirect(url_for('index'))

    if not site.get('is_active', True):
        flash(f'Website "{site.get("name")}" is marked as inactive. Activate it first to perform a manual check.', 'warning')
        return redirect(url_for('site_details', site_id=site_id))

    try:
        site_name = site.get("name", site.get("url"))
        logger.info(f"DASHBOARD: Manually triggering check for {site_name} ({site_id}) from UI.")
        flash(f'Initiating manual check for "{site_name}". Please wait a moment for results to update...', 'info')
        
        # Use queue system for manual checks to ensure emails are sent
        from src.queue_processor import QueueProcessor
        queue_processor = QueueProcessor()
        
        # Add full check to queue (this will send emails for all check types)
        queue_id = website_manager.add_to_queue(site_id, 'full')
        logger.info(f"DASHBOARD: Added full check for {site_name} to queue (ID: {queue_id})")
        
        # Return success immediately - the queue processor will handle the rest
        check_outcome = {
            'status': 'queued',
            'check_id': queue_id,
            'message': 'Check added to queue for processing'
        }
        
        status = check_outcome.get('status')
        check_id_val = check_outcome.get('check_id', 'N/A')

        if status == "queued":
            flash(f'Manual check for "{site_name}" (Queue ID: {check_id_val}) has been added to the processing queue. You will receive an email notification when the check completes.', 'success')
        elif status == "completed_with_changes":
            flash(f'Manual check for "{site_name}" (Check ID: {check_id_val}) completed. Significant changes detected!', 'warning')
        else:
            flash(f'Manual check for "{site_name}" (Check ID: {check_id_val}) run. Outcome: {status or "Unknown"}', 'info')

    except Exception as e:
        logger.error(f"Error during manual check route for {site_id} from UI: {e}", exc_info=True)
        site_name = site.get("name", "Unknown") if site else "Unknown"
        flash(f'Unable to start manual check for "{site_name}". Please try again or contact support if the issue persists.', 'danger')
    
    return redirect(url_for('site_details', site_id=site_id))

@app.route('/site/<site_id>/compare_snapshots/<check_id_current>/<check_id_previous>')
def compare_snapshots_visual(site_id, check_id_current, check_id_previous):
    """Compare snapshots visually - consolidated from dashboard_app.py"""
    site = website_manager.get_website(site_id)
    if not site:
        return render_template('404.html', message=f"Site with ID {site_id} not found."), 404

    current_check = history_manager.get_check_by_id(check_id_current)
    previous_check = history_manager.get_check_by_id(check_id_previous)

    if not current_check or not previous_check:
        msg = ""
        if not current_check: msg += f"Current check record {check_id_current} not found. "
        if not previous_check: msg += f"Previous check record {check_id_previous} not found."
        return render_template('404.html', message=msg.strip()), 404
    
    if not current_check.get('visual_snapshot_path') or not previous_check.get('visual_snapshot_path'):
        return render_template('404.html', message="One or both checks do not have visual snapshots."), 404

    visual_diff_score = current_check.get('visual_diff_score')
    visual_diff_image_path = current_check.get('visual_diff_image_path')

    return render_template('compare_visual.html', 
                           site=site, 
                           current_check=current_check,
                           previous_check=previous_check,
                           visual_diff_score=visual_diff_score,
                           visual_diff_image_path=visual_diff_image_path)

@app.route('/api/sites')
def api_sites():
    """API endpoint for sites - consolidated from dashboard_app.py"""
    sites = website_manager.list_websites()
    return jsonify(sites)

@app.route('/api/queue/status')
def api_queue_status():
    """API endpoint for queue status."""
    from src.queue_processor import get_queue_processor
    try:
        queue_processor = get_queue_processor()
        queue_data = queue_processor.get_queue_status()
        return jsonify({
            'status': 'success',
            'queue': queue_data,
            'total_items': len(queue_data)
        })
    except Exception as e:
        logger.error(f"Error getting queue status: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Unable to retrieve queue status. Please try again or contact support if the issue persists.'
        }), 500

@app.route('/api/queue/status/<queue_id>')
def api_queue_item_status(queue_id):
    """API endpoint for specific queue item status."""
    from src.queue_processor import get_queue_processor
    try:
        queue_processor = get_queue_processor()
        queue_data = queue_processor.get_queue_status(queue_id=queue_id)
        if queue_data:
            return jsonify({
                'status': 'success',
                'item': queue_data[0]
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'The requested queue item was not found. It may have been completed or removed.'
            }), 404
    except Exception as e:
        logger.error(f"Error getting queue item status: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Unable to retrieve queue item status. Please try again or contact support if the issue persists.'
        }), 500

@app.route('/queue')
def queue_page():
    """Developer queue management page."""
    return render_template('queue.html')

@app.route('/api/queue/reset', methods=['POST'])
def api_queue_reset():
    """API endpoint to reset the queue."""
    from src.queue_processor import get_queue_processor
    try:
        queue_processor = get_queue_processor()
        # Clear all pending and processing items
        cleared_count = queue_processor.clear_all_pending_items()
        return jsonify({
            'status': 'success',
            'message': f'Queue reset successfully. Cleared {cleared_count} items.',
            'cleared_count': cleared_count
        })
    except Exception as e:
        logger.error(f"Error resetting queue: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/site/<site_id>/history')
def api_site_history(site_id):
    """API endpoint for site history - consolidated from dashboard_app.py"""
    history_limit = config.get('dashboard_api_history_limit', 100)
    history = history_manager.get_history_for_site(site_id, limit=history_limit)
    if not history and not website_manager.get_website(site_id):
        return jsonify({"error": "Site not found"}), 404
    return jsonify(history)

@app.route('/snapshots/<site_id>/<type>/<filename>')
def serve_snapshot(site_id, type, filename):
    """Serve snapshot files with enhanced security and error handling - consolidated from dashboard_app.py"""
    try:
        from .path_utils import validate_path_safety, clean_path_for_logging
    except ImportError:
        # Fallback for direct execution
        from src.path_utils import validate_path_safety, clean_path_for_logging
    
    allowed_types = ["html", "visual", "diff"]
    if type not in allowed_types:
        return render_template('404.html', message="Invalid snapshot type."), 404
    
    # Security check: Ensure the filename doesn't contain directory traversal attempts
    if '..' in filename or filename.startswith('/'):
        logger.warning(f"Potential directory traversal attempt detected: {filename}")
        return render_template('404.html', message="Invalid filename."), 404
    
    # Normalize the filename for consistency
    filename = os.path.normpath(filename).replace('\\', '/')
    
    # Use the centralized snapshot directory from config
    snapshot_dir = config.get('snapshot_directory', 'data/snapshots')
    directory = os.path.join(snapshot_dir, site_id, type)
    
    # Security check: Ensure the resolved path is within the snapshot directory
    if not validate_path_safety(directory, snapshot_dir):
        logger.warning(f"Path security check failed for: {directory}")
        return render_template('404.html', message="Invalid path."), 404
    
    logger.debug(f"Attempting to serve: {filename} from directory: {clean_path_for_logging(directory)}")
    
    file_path = os.path.join(directory, filename)
    if not os.path.exists(file_path):
        logger.warning(f"Snapshot file not found: {clean_path_for_logging(file_path)}")
        return render_template('404.html', message=f"Snapshot file {filename} not found."), 404

    try:
        return send_from_directory(directory, filename)
    except Exception as e:
        logger.error(f"Error serving snapshot file {filename}: {e}")
        return render_template('404.html', message="Error serving file."), 404

# Route to serve files from the data directory (e.g., snapshots)
try:
    from .path_utils import get_data_directory, clean_path_for_logging
except ImportError:
    # Fallback for direct execution
    from src.path_utils import get_data_directory, clean_path_for_logging

DATA_DIRECTORY = get_data_directory()

@app.route('/data_files/<path:filepath>')
def data_files(filepath):
    """Serve files from the data directory with enhanced security and error handling."""
    try:
        from .path_utils import validate_path_safety, get_web_accessible_path
    except ImportError:
        # Fallback for direct execution
        from src.path_utils import validate_path_safety, get_web_accessible_path
    
    # Ensure the path is secure and within the intended directory
    logger.debug(f"Attempting to serve file from data directory: {filepath}")
    
    # Security check: Ensure the filepath doesn't contain directory traversal attempts
    if '..' in filepath or filepath.startswith('/'):
        logger.warning(f"Potential directory traversal attempt detected: {filepath}")
        return redirect(url_for('static', filename='img/placeholder.png'))
    
    # Normalize the filepath for consistency
    filepath = os.path.normpath(filepath).replace('\\', '/')
    
    # Check if the file exists at the primary path
    full_path = os.path.join(DATA_DIRECTORY, filepath)
    
    # Security check: Ensure the resolved path is within the data directory
    if not validate_path_safety(full_path, DATA_DIRECTORY):
        logger.warning(f"Path security check failed for: {filepath}")
        return redirect(url_for('static', filename='img/placeholder.png'))
    
    if os.path.isfile(full_path):
        try:
            return send_from_directory(DATA_DIRECTORY, filepath, as_attachment=False)
        except Exception as e:
            logger.error(f"Error serving file {filepath}: {e}")
            return redirect(url_for('static', filename='img/placeholder.png'))
    
    # File not found at primary path, try fallback strategies
    logger.warning(f"File not found at primary path: {clean_path_for_logging(full_path)}")
    
    # Strategy 1: Try prepending 'snapshots/' if not already present
    if not filepath.startswith('snapshots/'):
        potential_path = os.path.join('snapshots', filepath)
        potential_full_path = os.path.join(DATA_DIRECTORY, potential_path)
        
        if validate_path_safety(potential_full_path, DATA_DIRECTORY) and os.path.isfile(potential_full_path):
            logger.info(f"Found file by prepending 'snapshots/': {potential_path}")
            try:
                return send_from_directory(DATA_DIRECTORY, potential_path, as_attachment=False)
            except Exception as e:
                logger.error(f"Error serving file {potential_path}: {e}")
    
    # Strategy 2: Try baseline path variations
        if 'baseline' in filepath:
            variations = [
                filepath,
                filepath.replace('/baseline_', '/baseline/baseline_'),
                filepath.replace('/baseline/', '/'),
                filepath.replace('baseline.png', 'home.png'),
            filepath.replace('baseline.png', 'homepage.png'),
            filepath.replace('baseline.jpg', 'home.jpg'),
            filepath.replace('baseline.jpg', 'homepage.jpg')
            ]
            
            for var_path in variations:
                var_full_path = os.path.join(DATA_DIRECTORY, var_path)
                if validate_path_safety(var_full_path, DATA_DIRECTORY) and os.path.isfile(var_full_path):
                    logger.info(f"Found file at alternative path: {var_path}")
                    try:
                        return send_from_directory(DATA_DIRECTORY, var_path, as_attachment=False)
                    except Exception as e:
                        logger.error(f"Error serving file {var_path}: {e}")
                        continue
    
    # Strategy 3: Try common image extensions
    base_name, ext = os.path.splitext(filepath)
    if ext.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.webp']:
        for alt_ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']:
            if alt_ext != ext:
                alt_path = base_name + alt_ext
                alt_full_path = os.path.join(DATA_DIRECTORY, alt_path)
                if validate_path_safety(alt_full_path, DATA_DIRECTORY) and os.path.isfile(alt_full_path):
                    logger.info(f"Found file with alternative extension: {alt_path}")
                    try:
                        return send_from_directory(DATA_DIRECTORY, alt_path, as_attachment=False)
                    except Exception as e:
                        logger.error(f"Error serving file {alt_path}: {e}")
    
    # All strategies failed
            logger.error(f"Could not find any matching file for {filepath}")
            return redirect(url_for('static', filename='img/placeholder.png'))
    
def _auto_setup_website(website):
    """Automatically create baseline and run full check for newly imported website."""
    try:
        site_id = website['id']
        site_name = website.get('name', 'Unknown')
        
        # Step 1: Create baseline task
        baseline_task_id = str(uuid.uuid4())
        tasks[baseline_task_id] = {
            'status': 'pending',
            'description': f'Auto-creating baseline for {site_name}'
        }
        
        baseline_options = {
            'create_baseline': True,
            'capture_subpages': True,
            'crawl_only': False,
            'visual_check_only': False,
            'blur_check_only': False,
            'performance_check_only': False,
            'check_config': {
                'crawl_enabled': True,     # Need to crawl to find internal pages
                'visual_enabled': True,    # Need to capture visual baselines
                'blur_enabled': False,     # No blur detection during baseline creation
                'performance_enabled': False  # No performance checks during baseline creation
            },
            'is_scheduled': False
        }
        
        # Start baseline creation in background
        threading.Thread(
            target=run_background_task,
            args=(baseline_task_id, perform_website_check, site_id, baseline_options, 'config/config.yaml', website_manager, history_manager, crawler_module)
        ).start()
        
        # Step 2: Schedule full check after baseline (wait for completion)
        def run_full_check_after_baseline():
            import time
            start_time = time.time()
            timeout_seconds = 600  # 10 minutes max wait
            poll_interval = 3

            # Wait until baseline task completes or baseline paths are present
            while True:
                # Check task status first
                baseline_done = tasks.get(baseline_task_id, {}).get('status') == 'completed'
                if baseline_done:
                    break

                # Fallback: check website record for baselines
                site = website_manager.get_website(site_id)
                has_flag = site and (site.get('has_subpage_baselines') or site.get('baseline_visual_path'))
                if has_flag:
                    break

                if time.time() - start_time > timeout_seconds:
                    logger.warning(f"Baseline wait timed out for {site_name} ({site_id}). Proceeding with full check.")
                    break
                time.sleep(poll_interval)
            
            full_check_task_id = str(uuid.uuid4())
            tasks[full_check_task_id] = {
                'status': 'pending',
                'description': f'Auto-running full check for {site_name}'
            }
            
            full_check_options = {
                'create_baseline': False,
                'capture_subpages': True,
                'crawl_only': False,
                'visual_check_only': False,
                'blur_check_only': False,
                'performance_check_only': False,
                'check_config': {
                    'crawl_enabled': True,
                    'visual_enabled': True,
                    'blur_enabled': True,
                    'performance_enabled': True
                },
                'is_scheduled': False
            }
            
            # Start full check in background
            threading.Thread(
                target=run_background_task,
                args=(full_check_task_id, perform_website_check, site_id, full_check_options, 'config/config.yaml', website_manager, history_manager, crawler_module)
            ).start()
        
        # Start the follow-up full check watcher
        threading.Thread(target=run_full_check_after_baseline).start()
        
        logger.info(f"Auto-setup initiated for website {site_name} ({site_id}): baseline + full check")
        
    except Exception as e:
        logger.error(f"Error in auto-setup for website {website}: {e}")

@app.route('/bulk-import', methods=['GET', 'POST'])
def bulk_import():
    """Developer bulk import page for managing multiple websites."""
    current_config = get_app_config()
    
    if request.method == 'POST':
        try:
            action = request.form.get('action')
            
            if action == 'import_csv':
                # Handle CSV import
                if 'csv_file' not in request.files:
                    flash('No CSV file selected', 'error')
                    return redirect(url_for('bulk_import'))
                
                csv_file = request.files['csv_file']
                if csv_file.filename == '':
                    flash('No CSV file selected', 'error')
                    return redirect(url_for('bulk_import'))
                
                if csv_file and csv_file.filename.endswith('.csv'):
                    # Process CSV import
                    import csv
                    import io
                    
                    # Read CSV content
                    csv_content = csv_file.read().decode('utf-8')
                    csv_reader = csv.DictReader(io.StringIO(csv_content))
                    
                    imported_count = 0
                    errors = []
                    
                    for row in csv_reader:
                        try:
                            # Map CSV fields to internal schema expected by WebsiteManagerSQLite
                            name = (row.get('name') or '').strip()
                            url = (row.get('url') or '').strip()
                            if not name or not url:
                                errors.append(f"Row missing name or URL: {row}")
                                continue

                            # Parse exclude pages keywords from CSV
                            exclude_pages_keywords_str = row.get('exclude_pages_keywords', '').strip()
                            exclude_pages_keywords = [keyword.strip() for keyword in exclude_pages_keywords_str.split(',') if keyword.strip()] if exclude_pages_keywords_str else []

                            # Convert monitoring_interval from seconds to minutes
                            monitoring_interval_seconds = int(row.get('monitoring_interval', 86400))  # Default to 24 hours (86400 seconds)
                            check_interval_minutes = monitoring_interval_seconds // 60
                            
                            website_record = {
                                'name': name,
                                'url': url,
                                'check_interval_minutes': check_interval_minutes,  # Convert from seconds to minutes
                                'max_crawl_depth': int(row.get('max_depth', 2)),
                                'is_active': True,
                                'capture_subpages': True,
                                'auto_crawl_enabled': (row.get('enable_crawl', 'true').lower() == 'true'),
                                'auto_visual_enabled': (row.get('enable_visual', 'true').lower() == 'true'),
                                'auto_blur_enabled': (row.get('enable_blur_detection', 'true').lower() == 'true'),
                                'enable_blur_detection': (row.get('enable_blur_detection', 'true').lower() == 'true'),
                                'auto_performance_enabled': (row.get('enable_performance', 'true').lower() == 'true'),
                                'auto_full_check_enabled': True,
                                'render_delay': 6,
                                'visual_diff_threshold': 5,
                                'blur_detection_scheduled': False,
                                'blur_detection_manual': True,
                                'exclude_pages_keywords': exclude_pages_keywords,
                                'tags': [],
                                'notification_emails': []
                            }

                            # Add website using dict signature
                            website = website_manager.add_website(website_record)
                            imported_count += 1
                            
                            # Small delay to respect concurrency limits (like improved script)
                            time.sleep(0.5)
                            
                        except Exception as e:
                            errors.append(f"Error importing row {row}: {str(e)}")
                    
                    if imported_count > 0:
                        flash(f'Successfully imported {imported_count} websites', 'success')
                    if errors:
                        flash(f'Import completed with {len(errors)} errors. Check logs for details.', 'warning')
                        logger.warning(f"Bulk import errors: {errors}")
                    
                else:
                    flash('Please select a valid CSV file', 'error')
            
            elif action == 'import_json':
                # Handle JSON import
                if 'json_file' not in request.files:
                    flash('No JSON file selected', 'error')
                    return redirect(url_for('bulk_import'))
                
                json_file = request.files['json_file']
                if json_file.filename == '':
                    flash('No JSON file selected', 'error')
                    return redirect(url_for('bulk_import'))
                
                if json_file and json_file.filename.endswith('.json'):
                    try:
                        # Process JSON import
                        json_content = json_file.read().decode('utf-8')
                        websites_data = json.loads(json_content)
                        
                        imported_count = 0
                        errors = []
                        
                        for website in websites_data:
                            try:
                                # Validate
                                if not website.get('name') or not website.get('url'):
                                    errors.append(f"Website missing name or URL: {website}")
                                    continue

                                # Convert monitoring_interval from seconds to minutes
                                monitoring_interval_seconds = int(website.get('monitoring_interval', 86400))  # Default to 24 hours (86400 seconds)
                                check_interval_minutes = monitoring_interval_seconds // 60
                                
                                # Normalize to internal schema
                                website_record = {
                                    'name': website.get('name').strip(),
                                    'url': website.get('url').strip(),
                                    'check_interval_minutes': check_interval_minutes,  # Convert from seconds to minutes
                                    'max_crawl_depth': int(website.get('max_depth', 2)),
                                    'is_active': True,
                                    'capture_subpages': True,
                                    'auto_crawl_enabled': bool(website.get('enable_crawl', True)),
                                    'auto_visual_enabled': bool(website.get('enable_visual', True)),
                                    'auto_blur_enabled': bool(website.get('enable_blur_detection', True)),
                                    'enable_blur_detection': bool(website.get('enable_blur_detection', True)),
                                    'auto_performance_enabled': bool(website.get('enable_performance', True)),
                                    'auto_full_check_enabled': True,
                                    'render_delay': 6,
                                    'visual_diff_threshold': 5,
                                    'blur_detection_scheduled': False,
                                    'blur_detection_manual': True,
                                    'exclude_pages_keywords': website.get('exclude_pages_keywords', []),
                                    'tags': website.get('tags', []),
                                    'notification_emails': website.get('notification_emails', [])
                                }

                                website = website_manager.add_website(website_record)
                                imported_count += 1
                                
                                # Small delay to respect concurrency limits (like improved script)
                                time.sleep(0.5)
                                
                            except Exception as e:
                                errors.append(f"Error importing website {website}: {str(e)}")
                        
                        if imported_count > 0:
                            flash(f'Successfully imported {imported_count} websites', 'success')
                        if errors:
                            flash(f'Import completed with {len(errors)} errors. Check logs for details.', 'warning')
                            logger.warning(f"Bulk import errors: {errors}")
                            
                    except json.JSONDecodeError as e:
                        flash(f'Invalid JSON file: {str(e)}', 'error')
                    except Exception as e:
                        flash(f'Error processing JSON file: {str(e)}', 'error')
                else:
                    flash('Please select a valid JSON file', 'error')
            
            elif action == 'export_csv':
                # Handle CSV export
                websites = website_manager.list_websites()
                
                # Create CSV content
                import csv
                import io
                
                output = io.StringIO()
                fieldnames = ['name', 'url', 'monitoring_interval', 'enable_crawl', 'enable_visual', 
                             'enable_blur_detection', 'enable_performance', 'max_depth', 'description']
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                
                for site_id, site_data in websites.items():
                    writer.writerow({
                        'name': site_data.get('name', ''),
                        'url': site_data.get('url', ''),
                        'monitoring_interval': site_data.get('monitoring_interval', 300),
                        'enable_crawl': site_data.get('enable_crawl', True),
                        'enable_visual': site_data.get('enable_visual', True),
                        'enable_blur_detection': site_data.get('enable_blur_detection', False),
                        'enable_performance': site_data.get('enable_performance', False),
                        'max_depth': site_data.get('max_depth', 2),
                        'description': site_data.get('description', '')
                    })
                
                # Return CSV file
                from flask import Response
                output.seek(0)
                return Response(
                    output.getvalue(),
                    mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=websites_export.csv'}
                )
            
            elif action == 'export_json':
                # Handle JSON export
                websites = website_manager.list_websites()
                
                # Convert to exportable format
                export_data = []
                for site_id, site_data in websites.items():
                    export_data.append({
                        'name': site_data.get('name', ''),
                        'url': site_data.get('url', ''),
                        'monitoring_interval': site_data.get('monitoring_interval', 300),
                        'enable_crawl': site_data.get('enable_crawl', True),
                        'enable_visual': site_data.get('enable_visual', True),
                        'enable_blur_detection': site_data.get('enable_blur_detection', False),
                        'enable_performance': site_data.get('enable_performance', False),
                        'max_depth': site_data.get('max_depth', 2),
                        'description': site_data.get('description', '')
                    })
                
                # Return JSON file
                from flask import Response
                return Response(
                    json.dumps(export_data, indent=2),
                    mimetype='application/json',
                    headers={'Content-Disposition': 'attachment; filename=websites_export.json'}
                )
            
            elif action == 'clear_all':
                # Handle clear all data
                confirm = request.form.get('confirm_clear')
                if confirm == 'yes':
                    try:
                        # Clear all websites - convert to list to avoid iteration error
                        websites = website_manager.list_websites()
                        site_ids = list(websites.keys())  # Convert to list to avoid dict modification during iteration
                        for site_id in site_ids:
                            website_manager.remove_website(site_id)
                        
                        # Clear history data using cleanup method
                        history_manager.cleanup_old_records(days_to_keep=0)  # Clear all records
                        
                        flash('All website data has been cleared successfully', 'success')
                        logger.info("Bulk clear operation completed successfully")
                        
                    except Exception as e:
                        flash(f'Error clearing data: {str(e)}', 'error')
                        logger.error(f"Error during bulk clear: {e}")
                else:
                    flash('Clear operation cancelled - confirmation required', 'warning')
            
            return redirect(url_for('bulk_import'))
            
        except Exception as e:
            flash(f'Error processing request: {str(e)}', 'error')
            logger.error(f"Bulk import error: {e}")
            return redirect(url_for('bulk_import'))
    
    # GET request - show the bulk import page
    websites = website_manager.list_websites()
    total_websites = len(websites)
    
    return render_template('bulk_import.html', 
                         current_config=current_config,
                         total_websites=total_websites,
                         websites=websites)

# Replace the old block with this one
if __name__ == '__main__':
    # Initialize scheduler with proper configuration
    config_path = 'config/config.yaml'
    start_scheduler(config_path=config_path)
    
    # Start queue processor for manual checks
    from src.queue_processor import start_queue_processor
    from src.websocket_server import start_websocket_server
    
    logger.info("🚀 Starting queue processor...")
    start_queue_processor(config_path=config_path)
    
    logger.info("🚀 Starting WebSocket server...")
    start_websocket_server(config_path=config_path)
    
    # Explicitly load app's config for its run parameters
    app_specific_config = get_config(config_path='config/config.yaml') 
    
    # 1. CHANGED: Default host is now '0.0.0.0' for deployment
    app_host = app_specific_config.get('dashboard_host', '0.0.0.0')
    app_port = app_specific_config.get('dashboard_port', 5001)
    
    # 2. CHANGED: Default debug mode is now False for production
    app_debug = app_specific_config.get('dashboard_debug_mode', True) 
    
    logger.info(f"Starting Flask web server on http://{app_host}:{app_port}, Debug: {app_debug}")
    logger.info(f"WebSocket server running on ws://{app_host}:8765")
    app.run(host=app_host, port=app_port, debug=app_debug) 
