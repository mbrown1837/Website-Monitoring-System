import os
import sys
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Ensure src directory is in Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.config_loader import get_config, save_config
from src.logger_setup import setup_logging
from src.website_manager import WebsiteManager
from src.history_manager import HistoryManager
from src.scheduler import perform_website_check # We'll call this directly for manual checks
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
    return render_template('index.html', websites=websites, config=current_config)

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
            
            current_config['visual_difference_threshold'] = float(request.form.get('visual_difference_threshold', current_config['visual_difference_threshold']))
            current_config['meta_tags_to_check'] = [tag.strip() for tag in request.form.get('meta_tags_to_check', '').split(',') if tag.strip()]


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
            
            if not name or not url:
                flash('Name and URL are required.', 'danger')
            else:
                website_manager.add_website(url, name, interval, True, tags, notification_emails)
                flash(f'Website "{name}" added successfully!', 'success')
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
                'is_active': request.form.get('is_active') == 'on' # Checkbox value
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

@app.route('/website/check/<site_id>', methods=['POST'])
def manual_check_website(site_id):
    website = website_manager.get_website(site_id)
    if not website:
        flash(f'Website with ID "{site_id}" not found to perform check.', 'danger')
        return redirect(url_for('index'))
    
    if not website.get('is_active', True):
        flash(f'Website "{website.get("name")}" is marked as inactive. Activate it first to perform a manual check.', 'warning')
        return redirect(url_for('index'))

    try:
        site_name = website.get("name", website.get("url")) # Get name for messages
        logger.info(f"Manually triggering check for {site_name} ({site_id})")
        
        # Call the imported perform_website_check from scheduler.py
        # It now takes only site_id and returns a dictionary with the outcome.
        check_outcome = perform_website_check(site_id=site_id)
        
        # Process the check_outcome dictionary
        status = check_outcome.get('status')
        changes_detected = check_outcome.get('significant_change_detected', False) # significant_change_detected
        error_message = check_outcome.get('error_message')
        
        # Always send email notification for manual checks
        if status != "failed_fetch" and status != "error":
            logger.info(f"Sending manual check email notification for {site_name} ({site_id})")
            
            # Get email addresses from website settings
            site_notification_emails = website.get('notification_emails', [])
            
            # Format the email
            from src.alerter import format_alert_message, send_email_alert
            subject, alert_html_body, alert_text_body = format_alert_message(
                site_url=website.get('url'),
                site_name=site_name,
                check_record=check_outcome
            )
            
            # Modify subject for manual checks
            subject = f"[Manual Check] {subject}"
            
            # Send the email alert
            send_email_alert(
                subject, 
                alert_html_body, 
                alert_text_body, 
                recipient_emails=site_notification_emails
            )
        
        if status == "failed_fetch" or status == "error": # General error status from perform_website_check
            flash(f'Manual check for "{site_name}" encountered an error: {error_message or "Unknown error"}', 'danger')
        elif status == "initial_check_completed":
            flash(f'Manual check for "{site_name}" completed (initial check). Changes detected: {changes_detected}', 'info')
        elif status == "completed_no_changes":
            flash(f'Manual check for "{site_name}" completed. No significant changes detected.', 'success')
        elif status == "completed_with_changes":
            flash(f'Manual check for "{site_name}" completed. Significant changes detected!', 'warning')
        else: # Fallback for any other status or if outcome is None (should not happen ideally)
            flash(f'Manual check for "{site_name}" run. Outcome: {status or "Unknown"}', 'info')

    except Exception as e:
        # This catches exceptions from the call to perform_website_check itself, or other logic here
        logger.error(f"Error during manual check route for {site_id}: {e}", exc_info=True)
        flash(f'Error triggering manual check for "{website.get("name")}": {str(e)}', 'danger')
    
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