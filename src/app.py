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
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.config_loader import get_config, save_config
from src.logger_setup import setup_logging
from src.website_manager import WebsiteManager
from src.history_manager import HistoryManager
from src.scheduler import perform_website_check, make_json_serializable
from src.crawler_module import CrawlerModule # Import the crawler module
# from src.alerter import send_email_alert # For testing alerts

app = Flask(__name__, template_folder=os.path.join(project_root, 'templates'))
app.secret_key = os.urandom(24) # For flash messages

logger = setup_logging(config_path='config/config.yaml') # Explicitly point to config for app
config = get_config(config_path='config/config.yaml')

website_manager = WebsiteManager(config_path='config/config.yaml')
history_manager = HistoryManager(config_path='config/config.yaml')

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
    if not path_from_project_root or not isinstance(path_from_project_root, str):
        return None
    
    # Ensure forward slashes for consistency, as paths are stored with them
    path = path_from_project_root.replace("\\", "/")

    # The 'data_files' endpoint serves from the 'data' directory, so we
    # need to provide a path relative to it. We strip the 'data/' prefix.
    if path.startswith('data/'):
        return path[5:]  # len('data/') is 5
    
    # If the path is already in the correct format (e.g., 'snapshots/foo.png'),
    # or an unexpected format, return it as is. The data_files route has fallbacks.
    logger.warning(f"Path '{path}' provided to make_path_web_accessible did not start with 'data/'. Using it as is.")
    return path

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
            current_config['default_monitoring_interval_hours'] = int(request.form.get('default_monitoring_interval_hours', current_config['default_monitoring_interval_hours']))

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

@app.route('/website/add', methods=['GET', 'POST'])
def add_website():
    current_config = get_app_config()
    if request.method == 'POST':
        try:
            # Basic fields
            name = request.form['name']
            url = request.form['url']
            interval = int(request.form.get('interval', current_config.get('default_monitoring_interval_hours', 24)))
            tags_str = request.form.get('tags', '')
            tags = [tag.strip() for tag in tags_str.split(',') if tag.strip()]
            notification_emails_str = request.form.get('notification_emails', '')
            notification_emails = [email.strip() for email in notification_emails_str.split(',') if email.strip()]
            
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
                # Add the website with core details first
                website = website_manager.add_website(url, name, interval, True, tags, notification_emails, 
                                                    enable_blur_detection, blur_detection_scheduled, blur_detection_manual,
                                                    auto_crawl_enabled, auto_visual_enabled, auto_blur_enabled, auto_performance_enabled,
                                                    auto_full_check_enabled)
                
                if website:
                    # Update with all settings
                    website_manager.update_website(website['id'], {
                        'render_delay': render_delay,
                        'max_crawl_depth': max_crawl_depth,
                        'visual_diff_threshold': visual_diff_threshold,
                        'capture_subpages': True # Always true now
                    })
                    
                    # Handle initial setup based on user choice
                    if initial_setup == 'none':
                        # Just add the website, no initial checks
                        flash(f'Website "{name}" added successfully. No initial checks were run.', 'success')
                        return redirect(url_for('index'))
                    elif initial_setup == 'baseline':
                        # Create baseline only (crawl + visual baselines)
                        task_id = str(uuid.uuid4())
                        tasks[task_id] = {
                            'status': 'pending',
                            'description': f'Creating baseline for {name}'
                        }
                        
                        logger.info(f"Creating baseline for new website ID: {website['id']} (Task ID: {task_id})")
                        
                        thread_args = (
                            website['id'],
                            {
                                'create_baseline': True,
                                'capture_subpages': True,
                                'check_config': {'crawl_enabled': True, 'visual_enabled': True, 'blur_enabled': False, 'performance_enabled': False}
                            }
                        )
                        
                        thread = threading.Thread(
                            target=run_background_task,
                            args=(task_id, perform_website_check) + thread_args
                        )
                        thread.daemon = True
                        thread.start()
                        
                        flash(f'Website "{name}" added. Baseline creation started in the background.', 'success')
                        return redirect(url_for('index'))
                    elif initial_setup == 'full':
                        # Run full check with all enabled monitoring types
                        task_id = str(uuid.uuid4())
                        tasks[task_id] = {
                            'status': 'pending',
                            'description': f'Full initial check for {name}'
                        }
                        
                        logger.info(f"Running full initial check for new website ID: {website['id']} (Task ID: {task_id})")
                        
                        # Use the automated check configuration based on what user selected
                        check_config = website_manager.get_automated_check_config(website['id'])
                        
                        thread_args = (
                            website['id'],
                            {
                                'create_baseline': not website.get('baseline_visual_path'),  # Create baseline if none exists
                                'capture_subpages': True,
                                'check_config': check_config,
                                'is_scheduled': False
                            }
                        )
                        
                        thread = threading.Thread(
                            target=run_background_task,
                            args=(task_id, perform_website_check) + thread_args
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
                'url': request.form['url'],
                'interval': int(request.form.get('interval', website.get('interval'))),
                'tags': [tag.strip() for tag in request.form.get('tags', '').split(',') if tag.strip()],
                'notification_emails': notification_emails,
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
            website_manager.remove_website(site_id)
            flash(f'Website "{website.get("name", site_id)}" removed successfully!', 'success')
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
    Manually trigger a check for a specific website.
    This endpoint now always runs the check in the background and returns a task ID.
    """
    website = website_manager.get_website(site_id)
    if not website:
        return jsonify({'status': 'error', 'message': f'Website with ID "{site_id}" not found.'}), 404

    if not website.get('is_active', True):
        return jsonify({'status': 'error', 'message': f'Cannot check inactive website: {website.get("name")}. Please activate it first.'}), 400
        
    # Get check type and options from form
    check_type = request.form.get('check_type', 'full')
    create_baseline = request.form.get('create_baseline') == 'true'
    capture_subpages = request.form.get('capture_subpages') == 'true'
    
    # Configure crawler options
    crawler_options = {
        'create_baseline': create_baseline,
        'capture_subpages': capture_subpages,
        'crawl_only': check_type == 'crawl',
        'visual_check_only': check_type == 'visual',
        'blur_check_only': check_type == 'blur',
        'performance_check_only': check_type == 'performance'
    }
    
    # Get check configuration - use automated config if Full Check is enabled, otherwise use manual config
    if website.get('auto_full_check_enabled', False) and check_type == 'full':
        # If Full Check is enabled on the website and user clicked full check, use automated config
        check_config = website_manager.get_automated_check_config(site_id)
        logger.info(f"Using automated Full Check configuration for website {site_id}: {check_config}")
    else:
        # Use manual check configuration
        check_config = website_manager.get_manual_check_config(check_type)
        logger.info(f"Using manual check configuration for check type '{check_type}': {check_config}")
    
    # Add check configuration to crawler options
    crawler_options['check_config'] = check_config
    crawler_options['is_scheduled'] = False  # This is a manual check
    
    # Create a task for the background job
    task_id = str(uuid.uuid4())
    description = f"Manual '{check_type}' check for {website.get('name')}"
    if create_baseline:
        description = f"Baseline creation for {website.get('name')}"

    tasks[task_id] = {
        'status': 'pending',
        'description': description
    }

    # Start the check in a background thread
    thread = threading.Thread(
        target=run_background_task,
        args=(task_id, perform_website_check, site_id, crawler_options)
    )
    thread.daemon = True
    thread.start()
    
    logger.info(f"Initiated background task {task_id} for site {site_id} with options: {crawler_options}")
    
    # Return immediate response with task ID
    return jsonify({
        'status': 'initiated',
        'message': f'{description} initiated in the background.',
        'task_id': task_id
    })

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
        # Connect to SMTP server
        server = smtplib.SMTP(smtp_server, smtp_port)
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
    
    # Get blur detection statistics if enabled
    blur_stats = None
    if website.get('enable_blur_detection', False):
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
    
    # Get blur detection statistics if enabled
    blur_stats = None
    if website.get('enable_blur_detection', False):
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
        'uptime_percentage': 100
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
    current_config = get_app_config()
    website = website_manager.get_website(site_id)
    if not website:
        flash(f'Website with ID "{site_id}" not found.', 'danger')
        return redirect(url_for('index'))

    # Get performance results
    from src.performance_checker import PerformanceChecker
    performance_checker = PerformanceChecker(config_path='config/config.yaml')
    performance_results = performance_checker.get_latest_performance_results(site_id, limit=50)
    
    # Check if performance monitoring is enabled for informational message
    performance_enabled = website.get('auto_performance_enabled', False)
    
    # Always show the performance page, even if no data exists (empty state)
    if not performance_results:
        # Show empty state with helpful message
        performance_history = []
        if not performance_enabled:
            empty_message = f'Performance monitoring is not enabled for "{website.get("name")}". Enable it in website settings or run a manual performance check.'
        else:
            empty_message = f'No performance data available yet for "{website.get("name")}". Performance data will appear here after running a performance check.'
    else:
        # Group results by crawl_id and timestamp (multiple pages per check)
        grouped_results = {}
        for result in performance_results:
            crawl_id = result['crawl_id']
            timestamp = result['timestamp']
            
            # Create unique key for each performance check
            check_key = f"{crawl_id}_{timestamp}"
            
            if check_key not in grouped_results:
                grouped_results[check_key] = {
                    'crawl_id': crawl_id,
                    'timestamp': timestamp,
                    'pages': {}
                }
            
            # Group by page URL
            page_url = result['url']
            page_title = result.get('page_title', 'Unknown Page')
            
            if page_url not in grouped_results[check_key]['pages']:
                grouped_results[check_key]['pages'][page_url] = {
                    'url': page_url,
                    'page_title': page_title,
                    'mobile': None,
                    'desktop': None
                }
            
            # Add device-specific data
            device_type = result['device_type']
            grouped_results[check_key]['pages'][page_url][device_type] = result
        
        # Convert to list and sort by timestamp (newest first)
        performance_history = []
        for check_data in grouped_results.values():
            # Convert pages dict to list for easier template handling
            pages_list = list(check_data['pages'].values())
            
            performance_history.append({
                'crawl_id': check_data['crawl_id'],
                'timestamp': check_data['timestamp'],
                'pages': pages_list,
                'pages_count': len(pages_list)
            })
        
        # Sort by timestamp (newest first) - handle None values
        performance_history.sort(key=lambda x: x['timestamp'] or '', reverse=True)
        empty_message = None
    
    return render_template('performance_results.html', 
                           website=website, 
                           performance_history=performance_history,
                           empty_message=empty_message,
                           performance_enabled=performance_enabled,
                           config=current_config)

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

# Route to serve files from the data directory (e.g., snapshots)
DATA_DIRECTORY = os.path.join(project_root, 'data')

@app.route('/data_files/<path:filepath>')
def data_files(filepath):
    # Ensure the path is secure and within the intended directory
    logger.debug(f"Attempting to serve file from data directory: {filepath}")
    
    # Check if the file exists first
    full_path = os.path.join(DATA_DIRECTORY, filepath)
    if not os.path.isfile(full_path):
        logger.warning(f"File not found at primary path: {full_path}")
        
        # Hotfix: If path doesn't start with 'snapshots', try adding it.
        # This handles cases where the template generates an incorrect relative path.
        if not filepath.startswith('snapshots/'):
            potential_path = os.path.join('snapshots', filepath)
            potential_full_path = os.path.join(DATA_DIRECTORY, potential_path)
            if os.path.isfile(potential_full_path):
                logger.info(f"Found file by prepending 'snapshots/': {potential_path}")
                # Normalize path to use OS-specific separators to fix serving on Windows
                normalized_potential_path = os.path.normpath(potential_path)
                return send_from_directory(DATA_DIRECTORY, normalized_potential_path, as_attachment=False)
        
        # If it's a baseline path, try alternative locations
        if 'baseline' in filepath:
            # Try different baseline path patterns
            variations = [
                filepath,
                # For paths from older versions
                filepath.replace('/baseline_', '/baseline/baseline_'),
                filepath.replace('/baseline/', '/'),
                # For newer path format
                filepath.replace('baseline.png', 'home.png'),
                filepath.replace('baseline.png', 'homepage.png')
            ]
            
            # Try each variation
            for var_path in variations:
                var_full_path = os.path.join(DATA_DIRECTORY, var_path)
                if os.path.isfile(var_full_path):
                    logger.info(f"Found file at alternative path: {var_path}")
                    return send_from_directory(DATA_DIRECTORY, var_path, as_attachment=False)
                    
            # If we get here, none of the variations worked
            logger.error(f"Could not find any matching file for {filepath}")
            # Return placeholder image
            return redirect(url_for('static', filename='img/placeholder.png'))
    
    # Standard case - file exists at expected path
    try:
        return send_from_directory(DATA_DIRECTORY, filepath, as_attachment=False)
    except Exception as e:
        logger.error(f"Error serving file {filepath}: {e}")
        # Return placeholder image on error
        return redirect(url_for('static', filename='img/placeholder.png'))

if __name__ == '__main__':
    # Explicitly load app's config for its run parameters
    app_specific_config = get_config(config_path='config/config.yaml') 
    app_host = app_specific_config.get('dashboard_host', '127.0.0.1')
    app_port = app_specific_config.get('dashboard_port', 5001)
    # Defaulting debug mode to True for development for easier template/code reloading
    app_debug = app_specific_config.get('dashboard_debug_mode', True) 
    logger.info(f"Starting Flask web server on http://{app_host}:{app_port}, Debug: {app_debug}")
    app.run(host=app_host, port=app_port, debug=app_debug) 