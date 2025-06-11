import os
import sys
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json

# Ensure src directory is in Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.config_loader import get_config, save_config
from src.logger_setup import setup_logging
from src.website_manager import WebsiteManager
from src.history_manager import HistoryManager
from src.scheduler import perform_website_check # We'll call this directly for manual checks
from src.crawler_module import CrawlerModule # Import the crawler module
# from src.alerter import send_email_alert # For testing alerts

app = Flask(__name__, template_folder=os.path.join(project_root, 'templates'))
app.secret_key = os.urandom(24) # For flash messages

logger = setup_logging(config_path='config/config.yaml') # Explicitly point to config for app
config = get_config(config_path='config/config.yaml')

website_manager = WebsiteManager(config_path='config/config.yaml')
history_manager = HistoryManager(config_path='config/config.yaml')

# --- Helper Functions ---
def get_app_config():
    # Reload config to ensure it's fresh, especially after edits
    return get_config(config_path='config/config.yaml')

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
        site_stats = crawler.get_crawl_stats(site_id)
        crawler_stats[site_id] = {
            'broken_links_count': site_stats.get('total_broken_links', 0),
            'missing_meta_tags_count': site_stats.get('total_missing_meta_tags', 0),
            'total_pages_crawled': site_stats.get('total_pages_crawled', 0)
        }
        
        # Mark websites with issues
        has_issues = (crawler_stats[site_id]['broken_links_count'] > 0 or 
                      crawler_stats[site_id]['missing_meta_tags_count'] > 0)
        
        if has_issues:
            websites_with_issues += 1
            websites[site_id]['crawler_issues'] = True
    
    return render_template('index.html', 
                           websites=websites, 
                           config=current_config, 
                           crawler_stats=crawler_stats,
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
            
            # Update Notification (SMTP) settings
            current_config['notification_email_from'] = request.form.get('notification_email_from', current_config['notification_email_from'])
            current_config['notification_email_to'] = request.form.get('notification_email_to', current_config.get('notification_email_to'))
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
            
            current_config['visual_difference_threshold'] = float(request.form.get('visual_difference_threshold', current_config['visual_difference_threshold']))
            current_config['meta_tags_to_check'] = [tag.strip() for tag in request.form.get('meta_tags_to_check', '').split(',') if tag.strip()]
            
            # Update Crawler settings
            current_config['crawler_max_depth'] = int(request.form.get('crawler_max_depth', current_config.get('crawler_max_depth', 2)))
            current_config['crawler_respect_robots'] = request.form.get('crawler_respect_robots') == 'True'
            current_config['crawler_check_external_links'] = request.form.get('crawler_check_external_links') == 'True'
            current_config['crawler_user_agent'] = request.form.get('crawler_user_agent', current_config.get('crawler_user_agent', 'SiteMonitor Bot'))

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
            name = request.form['name']
            url = request.form['url']
            interval = int(request.form.get('interval', current_config.get('default_monitoring_interval_hours', 24)))
            tags_str = request.form.get('tags', '')
            tags = [tag.strip() for tag in tags_str.split(',') if tag.strip()]
            notification_emails_str = request.form.get('notification_emails', '')
            notification_emails = [email.strip() for email in notification_emails_str.split(',') if email.strip()]
            crawl_only = request.form.get('crawl_only') == 'on'
            
            if not name or not url:
                flash('Name and URL are required.', 'danger')
            else:
                # First add the website without the crawl_only flag
                website = website_manager.add_website(url, name, interval, True, tags, notification_emails)
                
                # If website was added successfully
                if website:
                    # Update with crawl_only option immediately before any baselines are created
                    website_manager.update_website(website['id'], {'crawl_only': crawl_only})
                    website = website_manager.get_website(website['id'])  # Refresh website data
                    
                    # Now that crawl_only is set, capture baseline if appropriate
                    if not website.get('crawl_only', False):
                        logger.info(f"Creating baseline for new website ID: {website['id']}")
                        baseline_success = website_manager.capture_baseline_for_site(website['id'])
                        if not baseline_success:
                            logger.warning(f"Failed to create baseline for website ID: {website['id']}")
                    else:
                        logger.info(f"Skipping baseline for crawl-only website ID: {website['id']}")
                    
                    # Run an initial crawl regardless of crawl-only setting
                    crawler_options = {
                        'max_depth': 2,
                        'crawl_only': website.get('crawl_only', False),
                        'visual_check_only': False,
                        'create_baseline': False  # Never create baseline during initial crawl
                    }
                    
                    logger.info(f"Running initial crawl for website ID: {website['id']}")
                    # Execute crawl in the background to avoid blocking the response
                    # The actual crawl will happen when the scheduler triggers
                    flash(f'Website "{name}" added successfully! Initial crawl scheduled.', 'success')
                    
                    # Return to index page
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
            notification_emails = [email.strip() for email in request.form.get('notification_emails', '').split(',') if email.strip()]
            updated_data = {
                'name': request.form['name'],
                'url': request.form['url'],
                'interval': int(request.form.get('interval', website.get('interval'))),
                'tags': [tag.strip() for tag in request.form.get('tags', '').split(',') if tag.strip()],
                'notification_emails': notification_emails,
                'is_active': request.form.get('is_active') == 'on',  # Checkbox value
                'crawl_only': request.form.get('crawl_only') == 'on'  # Crawl only option
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
    current_config = get_app_config()
    website = website_manager.get_website(site_id)
    if not website:
        flash(f'Website with ID "{site_id}" not found.', 'danger')
        return redirect(url_for('index'))
    
    # Force reload history to get latest data
    history_manager._load_history(force_reload=True) 
    history_records = history_manager.get_history_for_site(site_id, limit=current_config.get('dashboard_history_limit', 20))
    
    if not history_records:
        logger.warning(f"No history records found for site ID: {site_id}. Check if history file exists.")
        
    return render_template('history.html', website=website, history=history_records, config=current_config)

@app.route('/website/<site_id>/manual_check', methods=['POST'])
def manual_check_website(site_id):
    website = website_manager.get_website(site_id)
    if not website:
        flash(f'Website with ID "{site_id}" not found.', 'danger')
        return redirect(url_for('index'))

    # Get check type and options
    check_type = request.form.get('check_type', 'full')
    create_baseline = 'create_baseline' in request.form
    
    # Check if this website is configured as crawl-only
    website_is_crawl_only = website.get('crawl_only', False)
    
    # Set crawler options based on the selected check type
    crawler_options = {
        'create_baseline': create_baseline and not website_is_crawl_only,  # Skip baseline if site is crawl-only
        'max_depth': 2  # Default depth
    }
    
    # Configure options based on check type, but respect website's crawl_only setting
    if website_is_crawl_only:
        # For crawl-only websites, force crawl-only mode regardless of check type
        crawler_options['crawl_only'] = True
        crawler_options['visual_check_only'] = False
        crawler_options['create_baseline'] = False
        logger.info(f"Enforcing crawl-only mode for website {website.get('name')} (ID: {site_id})")
    elif check_type == 'crawl':
        # Regular website, but manual crawl selected
        crawler_options['crawl_only'] = True
        crawler_options['visual_check_only'] = False
    elif check_type == 'visual':
        # Visual check only
        crawler_options['crawl_only'] = False
        crawler_options['visual_check_only'] = True
    else:  # 'full' check
        crawler_options['crawl_only'] = False
        crawler_options['visual_check_only'] = False
    
    try:
        # Run the check using the scheduler's function
        check_result = perform_website_check(site_id, crawler_options)
        
        # Handle results based on status
        if check_result.get('status') == 'failed_fetch':
            flash(f'Failed to fetch content from {website["url"]}: {check_result.get("error_message")}', 'danger')
        else:
            # Determine message based on check type and baseline creation
            if website_is_crawl_only:
                message = "Crawl-only check completed for website configured in crawl-only mode."
            elif create_baseline and not website_is_crawl_only:
                message = "Website baseline creation completed."
            elif check_type == 'crawl':
                message = "Crawl-only check completed."
            elif check_type == 'visual':
                message = "Visual check completed."
            else:
                message = "Full website check completed."
                
            # Add details about changes if available
            if check_result.get('significant_change_detected'):
                message += " Significant changes were detected."
                
            # Add broken link and SEO issue counts if available
            if 'broken_links' in check_result:
                message += f" Found {check_result.get('broken_links', 0)} broken links."
            if 'missing_meta_tags' in check_result:
                message += f" Found {check_result.get('missing_meta_tags', 0)} SEO issues."
            
            flash(message, 'success')
            
    except Exception as e:
        logger.error(f"Error during manual check for {website.get('name', site_id)}: {e}", exc_info=True)
        flash(f"Error performing manual check: {str(e)}", 'danger')
    
    return redirect(url_for('website_history', site_id=site_id))

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
    if status_code_filter:
        try:
            status_code_filter = int(status_code_filter)
            all_pages = crawler.get_pages_by_status_code(crawl_id, status_code_filter)
        except ValueError:
            all_pages = crawler.get_pages_by_status_code(crawl_id)
    else:
        all_pages = crawler.get_pages_by_status_code(crawl_id)
    
    # Filter by URL if search query provided
    if search_url:
        all_pages = [page for page in all_pages if search_url.lower() in page.get('url', '').lower()]
        broken_links = [link for link in broken_links if search_url.lower() in link.get('url', '').lower()]
        missing_tags = [tag for tag in missing_tags if search_url.lower() in tag.get('url', '').lower()]
    
    # Filter by internal/external link type if specified
    if link_type_filter:
        if link_type_filter == 'internal':
            all_pages = [page for page in all_pages if page.get('is_internal', True)]
            broken_links = [link for link in broken_links if 
                           any(page.get('url') == link.get('url') and page.get('is_internal', True) 
                               for page in crawler_results.get('all_pages', []))]
        elif link_type_filter == 'external':
            all_pages = [page for page in all_pages if not page.get('is_internal', True)]
            broken_links = [link for link in broken_links if 
                           any(page.get('url') == link.get('url') and not page.get('is_internal', True) 
                               for page in crawler_results.get('all_pages', []))]
    
    # Calculate counts for display
    internal_pages_count = len([p for p in all_pages if p.get('is_internal', True)])
    external_pages_count = len([p for p in all_pages if not p.get('is_internal', True)])
    
    return render_template('crawler_results.html',
                         website_name=website.get('name'),
                         website_url=website.get('url'),
                         website_id=site_id,
                         crawler_results=crawler_results,
                         status_counts=status_counts,
                         all_pages=all_pages,
                         broken_links=broken_links,
                         missing_tags=missing_tags,
                         timestamp=timestamp,
                         internal_pages_count=internal_pages_count,
                         external_pages_count=external_pages_count,
                         current_link_type=link_type_filter)

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
    
    if tag_type_filter:
        missing_tags = [tag for tag in missing_tags if tag.get('tag_type') == tag_type_filter]
    
    if search_url:
        missing_tags = [tag for tag in missing_tags if search_url.lower() in tag.get('url', '').lower()]
    
    return render_template('missing_meta_tags.html',
                         website_name=website.get('name'),
                         website_url=website.get('url'),
                         website_id=site_id,
                         missing_tags=missing_tags,
                         timestamp=timestamp)

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
def serve_data_file(filepath):
    # Ensure the path is secure and within the intended directory
    # For simplicity, we assume filepath is already sanitized or trusted if coming from our history manager
    # In a production scenario, add more robust path checking and sanitization
    logger.debug(f"Attempting to serve file from data directory: {filepath}")
    # Construct the full path relative to the DATA_DIRECTORY
    # filepath is expected to be like 'snapshots/site_id/html/file.html'
    return send_from_directory(DATA_DIRECTORY, filepath, as_attachment=False)

if __name__ == '__main__':
    # Explicitly load app's config for its run parameters
    app_specific_config = get_config(config_path='config/config.yaml') 
    app_host = app_specific_config.get('dashboard_host', '127.0.0.1')
    app_port = app_specific_config.get('dashboard_port', 5001)
    # Defaulting debug mode to True for development for easier template/code reloading
    app_debug = app_specific_config.get('dashboard_debug_mode', True) 
    logger.info(f"Starting Flask web server on http://{app_host}:{app_port}, Debug: {app_debug}")
    app.run(host=app_host, port=app_port, debug=app_debug) 