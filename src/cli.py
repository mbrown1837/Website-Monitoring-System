import click
import json # For pretty printing dicts/lists
import os # For file operations
# Import classes and modules as needed
from src.config_loader import get_config
from src.website_manager_sqlite import WebsiteManager
from src.history_manager_sqlite import HistoryManager
from src import report_generator, scheduler, config_loader # Keep scheduler and report_generator as module imports
from src.logger_setup import setup_logging # To ensure logger is initialized
import src.alerter as alerter_module # Import the module

# Initialize logger and config early, as other modules might use them upon import
logger = setup_logging()
config = get_config() # Ensures config is loaded

# Instantiate managers for CLI use, using default config
website_mng = WebsiteManager()
history_mng = HistoryManager()
# No instance of Alerter needed if using module functions

@click.group()
def cli():
    """A CLI for managing the Website Monitoring System."""
    pass

# --- Website Management Commands ---
@cli.command("add-site")
@click.argument('url')
@click.option('--name', default=None, help="A friendly name for the website.")
@click.option('--interval', type=int, default=None, help="Monitoring interval in hours.")
@click.option('--active/--inactive', 'is_active', default=True, show_default=True, help="Set site as active or inactive.")
@click.option('--tags', default=None, help="Comma-separated tags for the website.")
@click.option('--notify-email', 'notification_emails', multiple=True, help="Email address for notifications. Can be used multiple times.")
def add_site(url, name, interval, is_active, tags, notification_emails):
    """Adds a new website, sets it active, captures initial baseline, and allows specifying notification emails."""
    tag_list = [tag.strip() for tag in tags.split(',')] if tags else []
    actual_name = name if name else url

    click.echo(f"Adding site: {actual_name} ({url})...")
    click.echo(f"Parameters: Interval={interval if interval is not None else 'default'}, Active={is_active}, Tags={tag_list}, NotifyEmails={list(notification_emails)}")

    click.echo("Attempting to add site and capture initial baseline (HTML and Visual)... Please wait.")
    
    site = website_mng.add_website(
        url=url, 
        name=name, 
        interval=interval, 
        is_active=is_active, 
        tags=tag_list,
        notification_emails=list(notification_emails)
    )
    
    if site:
        click.echo(click.style(f"Successfully added site: {site.get('name')}", fg='green'))
        click.echo("Baseline capture process initiated by WebsiteManager.")
        
        baseline_html_path = site.get('baseline_html_path')
        baseline_visual_path = site.get('baseline_visual_path')

        html_ok = baseline_html_path and isinstance(baseline_html_path, str) and os.path.exists(baseline_html_path)
        visual_ok = baseline_visual_path and isinstance(baseline_visual_path, str) and os.path.exists(baseline_visual_path)

        if html_ok:
            click.echo(click.style(f"  - Baseline HTML snapshot saved: {baseline_html_path}", fg='green'))
        else:
            click.echo(click.style(f"  - Baseline HTML snapshot: Failed or not captured (Path: {baseline_html_path}).", fg='yellow'))
        
        if visual_ok:
            click.echo(click.style(f"  - Baseline Visual snapshot saved: {baseline_visual_path}", fg='green'))
        else:
            click.echo(click.style(f"  - Baseline Visual snapshot: Failed or not captured (Path: {baseline_visual_path}).", fg='yellow'))
        
        if not html_ok or not visual_ok:
            click.echo(click.style("Warning: Initial baseline capture might be incomplete. Check logs or use 'set-baseline' command later.", fg='yellow'))
        else:
            click.echo(click.style("Initial baseline captured successfully.", fg='green'))

        click.echo("Site details:")
        click.echo(json.dumps(site, indent=2))
        
        click.echo("\nPerforming an initial check for the new site to populate history...")
        # Ensure scheduler.perform_website_check uses the most up-to-date site info if it re-fetches
        # For CLI, the baseline is just set, so this check will be against that new baseline effectively.
        check_outcome = scheduler.perform_website_check(site['id']) 
        if check_outcome and check_outcome.get('status') not in ["failed_fetch", "error"]:
            click.echo(click.style(f"Initial check completed. Status: {check_outcome.get('status')}. Check ID: {check_outcome.get('check_id')}", fg='green'))
        elif check_outcome:
            click.echo(click.style(f"Initial check failed or had issues. Status: {check_outcome.get('status')}, Error: {check_outcome.get('error_message')}", fg='red'))
        else:
            click.echo(click.style("Initial check outcome not available or an issue occurred.", fg='red'))

    else:
        click.echo(click.style(f"Failed to add site (it might already exist, URL was empty, or an error occurred during baseline). Check logs for details: {url}", fg='red'), err=True)

@cli.command("list-sites")
@click.option('--active-only', is_flag=True, help="Show only active websites.")
def list_sites(active_only):
    """Lists all monitored websites."""
    sites = website_mng.list_websites(active_only=active_only)
    if sites:
        click.echo("Monitored Websites:")
        output_sites = []
        for site_id, site_data in sites.items():
            site_display = site_data.copy()
            baseline_status = []
            if site_display.get('baseline_html_available'):
                baseline_status.append("HTML")
            if site_display.get('baseline_visual_available'):
                baseline_status.append("Visual")
            site_display['baseline_status'] = ", ".join(baseline_status) if baseline_status else "Not Available"
            output_sites.append(site_display)
        click.echo(json.dumps(output_sites, indent=2)) 
    else:
        click.echo("No websites found.")

@cli.command("remove-site")
@click.argument('site_id_or_url')
def remove_site(site_id_or_url):
    """Removes a website by its ID or URL."""
    site_to_remove = website_mng.get_website(site_id_or_url) or website_mng.get_website_by_url(site_id_or_url)
    if not site_to_remove:
        click.echo(f"Error: Website '{site_id_or_url}' not found.", err=True)
        return

    if click.confirm(f"Are you sure you want to remove site: {site_to_remove.get('name')} ({site_to_remove.get('url')})?", abort=True):
        if website_mng.remove_website(site_to_remove['id']):
            click.echo(f"Site {site_to_remove.get('name')} removed successfully.")
        else:
            click.echo(f"Failed to remove site {site_to_remove.get('name')}.", err=True)

@cli.command("update-site")
@click.argument('site_id_or_url')
@click.option('--url', 'new_url', default=None, help="New URL for the website.")
@click.option('--name', default=None, help="New friendly name for the website.")
@click.option('--interval', type=int, default=None, help="New monitoring interval in hours.")
@click.option('--active/--inactive', 'new_active_status', default=None, help="Set site as active or inactive.")
@click.option('--tags', default=None, help="New comma-separated tags (will replace existing tags). Example: 'tag1,tag2' or '' to clear.")
@click.option('--notify-email', 'notification_emails', multiple=True, help="Set/replace notification emails. Use multiple times. To clear, provide this option with an empty string: --notify-email ''")
@click.option('--recapture-baseline', is_flag=True, help="Recapture the baseline for this site.")
def update_site(site_id_or_url, new_url, name, interval, new_active_status, tags, notification_emails, recapture_baseline):
    """Updates an existing website. Can also recapture baseline and update notification emails."""
    site_to_update = website_mng.get_website(site_id_or_url) or website_mng.get_website_by_url(site_id_or_url)
    if not site_to_update:
        click.echo(f"Error: Website '{site_id_or_url}' not found.", err=True)
        return

    updates = {}
    if new_url is not None: updates['url'] = new_url
    if name is not None: updates['name'] = name
    if interval is not None: updates['interval'] = interval
    if new_active_status is not None: updates['is_active'] = new_active_status
    if tags is not None:
        updates['tags'] = [tag.strip() for tag in tags.split(',')] if tags else []
    if notification_emails: # If the option is used, even if it's to clear
        # If one of the emails is an empty string, treat it as clearing the list
        if '' in notification_emails and len(notification_emails) == 1:
            updates['notification_emails'] = []
        else:
            updates['notification_emails'] = [email for email in notification_emails if email] # Filter out empty strings if mixed

    if not updates and not recapture_baseline:
        click.echo("No update parameters or --recapture-baseline flag provided.")
        return

    if recapture_baseline:
        updates['recapture_baseline'] = True

    updated_site = website_mng.update_website(site_to_update['id'], updates)
    if updated_site:
        click.echo(f"Successfully updated site: {updated_site.get('name')}")
        click.echo(json.dumps(updated_site, indent=2))
    else:
        click.echo(f"Failed to update site {site_to_update.get('name')}. Check logs for details (e.g. URL conflict).", err=True)

@cli.command("set-baseline")
@click.argument('site_id_or_url')
def set_baseline(site_id_or_url):
    """Manually captures and sets the current state of a website as its baseline."""
    site_to_baseline = website_mng.get_website(site_id_or_url) or website_mng.get_website_by_url(site_id_or_url)
    if not site_to_baseline:
        click.echo(f"Error: Website '{site_id_or_url}' not found.", err=True)
        return

    click.echo(f"Attempting to capture baseline for site: {site_to_baseline.get('name')} ({site_to_baseline.get('url')})...")
    success = website_mng.capture_baseline_for_site(site_to_baseline['id'])
    if success:
        click.echo("Successfully captured and set new baseline.")
        updated_site_info = website_mng.get_website(site_to_baseline['id'])
        click.echo("Current baseline status:")
        html_path = updated_site_info.get('baseline_html_path', 'N/A')
        visual_path = updated_site_info.get('baseline_visual_path', 'N/A')
        click.echo(f"  HTML: {html_path}")
        click.echo(f"  Visual: {visual_path}")
    else:
        click.echo("Failed to capture baseline. Check logs for details.", err=True)

# --- Check History and Manual Check Commands ---
@cli.command("get-history")
@click.argument('site_id_or_url')
@click.option('--limit', type=int, default=10, help="Number of history records to show (0 for all). Default 10.")
def get_history(site_id_or_url, limit):
    """Shows check history for a specific website."""
    site = website_mng.get_website(site_id_or_url) or website_mng.get_website_by_url(site_id_or_url)
    if not site:
        click.echo(f"Error: Website '{site_id_or_url}' not found.", err=True)
        return
    
    history = history_mng.get_history_for_site(site['id'], limit=limit if limit > 0 else None)
    if history:
        click.echo(json.dumps(history, indent=2))
    else:
        click.echo(f"No history found for site: {site.get('name')}")

@cli.command("run-check")
@click.argument('site_id_or_url')
def run_check(site_id_or_url):
    """Manually triggers a monitoring check for a specific website."""
    site = website_mng.get_website(site_id_or_url) or website_mng.get_website_by_url(site_id_or_url)
    if not site:
        click.echo(f"Error: Website '{site_id_or_url}' not found.", err=True)
        return
    if not site.get('is_active', True):
        click.echo(f"Warning: Site '{site.get('name')}' is marked as inactive. Proceeding with manual check anyway.")

    click.echo(f"Manually triggering check for: {site.get('name')} ({site.get('url')}) ...")
    check_outcome = scheduler.perform_website_check(site['id'])
    if check_outcome:
        status = check_outcome.get('status')
        changes = check_outcome.get('significant_change_detected')
        error = check_outcome.get('error_message')
        if error:
            click.echo(f"Check for {site.get('name')} resulted in an error: {error}", err=True)
        elif status == "initial_check_completed":
            click.echo(f"Check for {site.get('name')} completed (initial check). Significant changes: {changes}")
        elif status == "completed_no_changes":
            click.echo(f"Check for {site.get('name')} completed. No significant changes detected.")
        elif status == "completed_with_changes":
            click.echo(f"Check for {site.get('name')} completed. Significant changes detected! Details in history.")
        else:
            click.echo(f"Manual check for {site.get('name')} run. Status: {status}. Check logs and history for details.")
    else:
        click.echo("Manual check process initiated. Outcome not immediately available or an issue occurred. Check logs.")

# --- Reporting Commands ---
@cli.command("generate-report")
@click.option('--site-id', 'report_site_id', default=None, help="Generate report for a specific site ID. If not provided, reports for all sites.")
@click.option('--format', 'report_format', type=click.Choice(['json', 'csv'], case_sensitive=False), default='json', help="Report format.")
@click.option('--output-file', default=None, help="Path to save the report. If not provided, prints to console.")
@click.option('--history-limit', type=int, default=0, help="Number of recent history records per site for the report (0 for all). Default all.")
def generate_report(report_site_id, report_format, output_file, history_limit):
    """Generates a report of check history."""
    records = []
    if report_site_id:
        site = website_mng.get_website(report_site_id) or website_mng.get_website_by_url(report_site_id)
        if not site:
            click.echo(f"Error: Website with ID/URL '{report_site_id}' not found.", err=True)
            return
        records = history_mng.get_history_for_site(site['id'], limit=history_limit if history_limit > 0 else None)
    else:
        all_sites_map = website_mng.list_websites()
        for site_id, site_data in all_sites_map.items():
            site_history = history_mng.get_history_for_site(site_id, limit=history_limit if history_limit > 0 else None)
            records.extend(site_history)
    
    if not records:
        click.echo("No check history found to generate a report.")
        return

    report_content = ""
    if report_format == 'json':
        report_content = json.dumps(records, indent=2) 
    elif report_format == 'csv':
        report_content = report_generator.generate_csv_report(records)
    
    if output_file:
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report_content)
            click.echo(f"Report generated and saved to: {output_file}")
        except IOError as e:
            click.echo(f"Error saving report to {output_file}: {e}", err=True)
    else:
        click.echo(report_content)

@cli.command("send-check-report")
@click.argument('check_id')
@click.option('--email', 'recipient_email', required=True, help="Email address to send the detailed report to.")
def send_check_report(check_id, recipient_email):
    """Generates a detailed HTML report for a specific check ID and emails it."""
    click.echo(f"Fetching check record for ID: {check_id}...")
    check_record = history_mng.get_check_by_id(check_id)

    if not check_record:
        click.echo(click.style(f"Error: Check record with ID '{check_id}' not found.", fg='red'), err=True)
        return

    site_id = check_record.get('site_id')
    site_details = None
    if site_id:
        site_details = website_mng.get_website(site_id)
    
    site_name = site_details.get('name', "N/A") if site_details else check_record.get('url', "N/A")
    site_url = site_details.get('url', check_record.get('url', "N/A"))

    click.echo(f"Generating detailed HTML report for check ID: {check_id} for site: {site_name}...")
    report_html = report_generator.generate_detailed_html_report_for_check(check_record, site_name, site_url)

    if not report_html or "<p>No check record data provided.</p>" in report_html:
        click.echo(click.style("Failed to generate HTML report or report is empty.", fg='red'), err=True)
        return

    alert_subject = f"Detailed Monitoring Report for {site_name} - Check ID {check_id}"
    
    click.echo(f"Sending report to {recipient_email}...")
    success = alerter_module.send_email_alert(
        subject=alert_subject,
        body_html=report_html,
        body_text="Please view this report in an HTML-compatible email client.",
        recipient_emails=[recipient_email]
    )

    if success:
        click.echo(click.style(f"Detailed report for check ID {check_id} sent successfully to {recipient_email}.", fg='green'))
    else:
        click.echo(click.style(f"Failed to send report email for check ID {check_id} to {recipient_email}. Check SMTP settings and logs.", fg='red'), err=True)

if __name__ == '__main__':
    cli() 