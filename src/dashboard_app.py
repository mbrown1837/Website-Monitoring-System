from flask import Flask, render_template, jsonify, send_from_directory, request, flash, redirect, url_for
import os
import sys

# Add project root to sys.path to allow importing other src modules
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.website_manager import WebsiteManager
from src.history_manager import HistoryManager
from src.config_loader import get_config
from src.logger_setup import setup_logging
from src.scheduler import perform_website_check

app = Flask(__name__)
# It's good practice to set a secret key for flash messages, even if simple for now
app.secret_key = config.get('flask_secret_key', os.urandom(24))
config = get_config()
logger = setup_logging(config.get('log_level_dashboard', 'INFO'), config.get('log_file_dashboard', 'data/dashboard.log'))

# Instantiate managers here. These instances will be used by the dashboard routes.
website_mng_app = WebsiteManager()
history_mng_app = HistoryManager()

# Ensure snapshot directory is absolute or relative to project root for serving files
SNAPSHOT_DIR = config.get('snapshot_directory', 'data/snapshots')
if not os.path.isabs(SNAPSHOT_DIR):
    SNAPSHOT_DIR = os.path.join(PROJECT_ROOT, SNAPSHOT_DIR)
app.config['SNAPSHOT_DIRECTORY'] = SNAPSHOT_DIR

@app.route('/')
def index():
    sites = website_mng_app.list_websites()
    sites_with_status = []
    for site_id, site_data in sites.items():
        current_site_id = site_data.get('id', site_id)

        latest_check = history_mng_app.get_latest_check_for_site(current_site_id)
        site_status = latest_check['status'] if latest_check else 'N/A'
        last_checked = latest_check['timestamp_utc'] if latest_check else 'Never'
        significant_change = latest_check.get('significant_change_detected', False) if latest_check else False
        
        site_info_to_append = site_data.copy()
        site_info_to_append.update({
            'status': site_status,
            'last_checked': last_checked,
            'significant_change': significant_change
        })
        if 'id' not in site_info_to_append:
            site_info_to_append['id'] = current_site_id
            
        sites_with_status.append(site_info_to_append)
    return render_template('index.html', sites=sites_with_status)

@app.route('/site/<site_id>')
def site_details(site_id):
    site = website_mng_app.get_website(site_id)
    if not site:
        return render_template('404.html', message=f"Site with ID {site_id} not found."), 404
    
    history_limit = config.get('dashboard_history_limit', 20)
    history_records = history_mng_app.get_history_for_site(site_id, limit=history_limit)
    
    return render_template('site_details.html', site=site, history=history_records)

@app.route('/site/<site_id>/run_check', methods=['POST'])
def run_manual_check_from_ui(site_id):
    site = website_mng_app.get_website(site_id)
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
        
        check_outcome = perform_website_check(site_id=site_id)
        
        status = check_outcome.get('status')
        changes_detected = check_outcome.get('significant_change_detected', False)
        error_message = check_outcome.get('error_message')
        check_id_val = check_outcome.get('check_id', 'N/A')

        if status == "failed_fetch" or status == "error":
            flash(f'Manual check for "{site_name}" (Check ID: {check_id_val}) encountered an error: {error_message or "Unknown error"}', 'danger')
        elif status == "initial_check_completed":
            flash(f'Manual check for "{site_name}" (Check ID: {check_id_val}) completed (initial check). Changes detected: {changes_detected}', 'info')
        elif status == "completed_no_changes":
            flash(f'Manual check for "{site_name}" (Check ID: {check_id_val}) completed. No significant changes detected.', 'success')
        elif status == "completed_with_changes":
            flash(f'Manual check for "{site_name}" (Check ID: {check_id_val}) completed. Significant changes detected!', 'warning')
        else:
            flash(f'Manual check for "{site_name}" (Check ID: {check_id_val}) run. Outcome: {status or "Unknown"}', 'info')

    except Exception as e:
        logger.error(f"Error during manual check route for {site_id} from UI: {e}", exc_info=True)
        flash(f'Error triggering manual check for "{site.get("name")}": {str(e)}', 'danger')
    
    return redirect(url_for('site_details', site_id=site_id))

@app.route('/site/<site_id>/compare_snapshots/<check_id_current>/<check_id_previous>')
def compare_snapshots_visual(site_id, check_id_current, check_id_previous):
    site = website_mng_app.get_website(site_id)
    if not site:
        return render_template('404.html', message=f"Site with ID {site_id} not found."), 404

    current_check = history_mng_app.get_check_by_id(check_id_current)
    previous_check = history_mng_app.get_check_by_id(check_id_previous)

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
    sites = website_mng_app.list_websites()
    return jsonify(sites)

@app.route('/api/site/<site_id>/history')
def api_site_history(site_id):
    history_limit = config.get('dashboard_api_history_limit', 100)
    history = history_mng_app.get_history_for_site(site_id, limit=history_limit)
    if not history and not website_mng_app.get_website(site_id):
        return jsonify({"error": "Site not found"}), 404
    return jsonify(history)

@app.route('/snapshots/<site_id>/<type>/<filename>')
def serve_snapshot(site_id, type, filename):
    allowed_types = ["html", "visual", "diff"]
    if type not in allowed_types:
        return render_template('404.html', message="Invalid snapshot type."), 404
    
    directory = os.path.join(app.config['SNAPSHOT_DIRECTORY'], site_id, type)
    
    logger.debug(f"Attempting to serve: {filename} from directory: {directory}")
    if not os.path.exists(os.path.join(directory, filename)):
         logger.warning(f"Snapshot file not found: {os.path.join(directory, filename)}")
         return render_template('404.html', message=f"Snapshot file {filename} not found."), 404

    return send_from_directory(directory, filename)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html', message=str(e)), 404

@app.errorhandler(500)
def internal_server_error(e):
    logger.error(f"Internal server error: {e}", exc_info=True)
    return render_template('500.html', message="An internal server error occurred."), 500

if __name__ == '__main__':
    app.run(debug=True, port=config.get('dashboard_port', 5001)) 