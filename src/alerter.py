"""
Simplified email alerting system for website monitoring.
Uses plain HTML without complex CSS for better email client compatibility.
"""

import smtplib
import html
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from datetime import datetime
from src.config_loader import get_config
from src.logger_setup import setup_logging

logger = setup_logging()

def get_config_dynamic():
    """Get config dynamically to ensure environment variables are loaded."""
    from src.config_loader import get_config_path_for_environment
    config_path = get_config_path_for_environment()
    logger.info(f"Loading config from: {config_path}")
    config = get_config(config_path=config_path)
    logger.info(f"Config loaded - keys: {list(config.keys()) if config else 'None'}")
    return config

def send_report(website: dict, check_results: dict):
    """
    Analyzes check results and sends the appropriate detailed email report.
    Simplified version without complex CSS styling.
    """
    site_name = website.get('name', 'N/A')
    site_url = website.get('url', 'N/A')
    recipient_emails = website.get('notification_emails', [])
    
    # Debug logging to see what data we're working with
    logger.info(f"EMAIL DEBUG - Site: {site_name}")
    logger.info(f"EMAIL DEBUG - Check results keys: {list(check_results.keys())}")
    logger.info(f"EMAIL DEBUG - Crawl stats: {check_results.get('crawl_stats', {})}")
    logger.info(f"EMAIL DEBUG - Broken links count: {len(check_results.get('broken_links', []))}")
    logger.info(f"EMAIL DEBUG - Missing meta tags count: {len(check_results.get('missing_meta_tags', []))}")
    
    # Determine if this is a change report
    is_change_report = check_results.get('significant_change_detected', False)

    # Create subject
    subject = f"Monitoring Report for {site_name}"
    if is_change_report:
        subject = f"Change Detected on {site_name}"

    # Get dashboard URL - prioritize environment variable for Coolify
    config = get_config_dynamic()
    dashboard_url = os.environ.get('DASHBOARD_URL') or config.get('dashboard_url', 'http://localhost:5001')
    
    # Log the dashboard URL being used for debugging
    logger.info(f"Using dashboard URL: {dashboard_url}")
    
    # If no DASHBOARD_URL is set, use the provided Coolify domain
    if not os.environ.get('DASHBOARD_URL') and dashboard_url == 'http://localhost:5001':
        dashboard_url = 'http://y0sos0scg00g0swwg8o4wk8k.167.86.123.94.sslip.io'
        logger.info(f"Using fallback Coolify domain: {dashboard_url}")
    
    # Create simple HTML email body without CSS
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Website Monitoring Report - {site_name}</title>
    </head>
    <body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5;">
        <div style="max-width: 800px; margin: 0 auto; background: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); overflow: hidden;">
            
            <!-- Header -->
            <div style="background: #4a90e2; color: white; padding: 30px 20px; text-align: center;">
                <h1 style="margin: 0; font-size: 28px; font-weight: bold;">🌐 Website Monitoring Report</h1>
                <p style="margin: 8px 0 0 0; font-size: 16px; opacity: 0.9;">{html.escape(site_name)}</p>
            </div>
            
            <!-- Content -->
            <div style="padding: 30px;">
                
                <!-- Check Summary -->
                <h2 style="color: #333; border-bottom: 2px solid #4a90e2; padding-bottom: 10px;">📊 Check Summary</h2>
                <p>A comprehensive check has been completed for <strong><a href="{html.escape(site_url)}" style="color: #4a90e2;">{html.escape(site_url)}</a></strong></p>
                <p><strong>Check Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                <p><strong>Status:</strong> {check_results.get('status', 'Completed')}</p>
                
                <!-- Key Metrics -->
                <h2 style="color: #333; border-bottom: 2px solid #4a90e2; padding-bottom: 10px;">📈 Key Metrics</h2>
                <div style="display: flex; justify-content: space-around; margin: 20px 0; flex-wrap: wrap;">
                    <div style="background: #f8f9fa; padding: 20px; margin: 10px; border-radius: 8px; text-align: center; min-width: 150px; border: 1px solid #ddd;">
                        <div style="font-size: 32px; font-weight: bold; color: #4a90e2;">{check_results.get('crawl_stats', {}).get('pages_crawled', 0)}</div>
                        <div style="font-size: 14px; color: #666; text-transform: uppercase;">Pages Crawled</div>
                    </div>
                    <div style="background: #f8f9fa; padding: 20px; margin: 10px; border-radius: 8px; text-align: center; min-width: 150px; border: 1px solid #ddd;">
                        <div style="font-size: 32px; font-weight: bold; color: #dc3545;">{len(check_results.get('broken_links', []))}</div>
                        <div style="font-size: 14px; color: #666; text-transform: uppercase;">Broken Links</div>
                    </div>
                    <div style="background: #f8f9fa; padding: 20px; margin: 10px; border-radius: 8px; text-align: center; min-width: 150px; border: 1px solid #ddd;">
                        <div style="font-size: 32px; font-weight: bold; color: #ffc107;">{len(check_results.get('missing_meta_tags', []))}</div>
                        <div style="font-size: 14px; color: #666; text-transform: uppercase;">Missing Meta Tags</div>
                    </div>
                </div>

                <!-- Quick Actions -->
                <h2 style="color: #333; border-bottom: 2px solid #4a90e2; padding-bottom: 10px;">🔗 Quick Actions</h2>
                <div style="text-align: center; margin: 20px 0;">
                    <a href="{dashboard_url}/website/{check_results.get('website_id')}" style="background: #4a90e2; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 5px; display: inline-block; font-weight: bold;">View Dashboard</a>
                    <a href="{dashboard_url}/website/{check_results.get('website_id')}/history" style="background: #28a745; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 5px; display: inline-block; font-weight: bold;">View History</a>
                    <a href="{dashboard_url}/website/{check_results.get('website_id')}/crawler" style="background: #17a2b8; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 5px; display: inline-block; font-weight: bold;">View Crawler Results</a>
                </div>

                <!-- Footer -->
                <div style="background: #2c3e50; color: #ecf0f1; padding: 30px; text-align: center; margin-top: 30px; border-radius: 8px;">
                    <p style="margin: 0 0 10px 0;">This is an automated report from your Website Monitoring System.</p>
                    <p style="margin: 0;"><a href="{dashboard_url}" style="color: #3498db; text-decoration: none;">Visit Dashboard</a> | <a href="{dashboard_url}/settings" style="color: #3498db; text-decoration: none;">Settings</a></p>
                </div>
                
            </div>
        </div>
    </body>
    </html>
    """
    
    # Create simple text version
    text_body = f"""
Website Monitoring Report for {site_name}
========================================

Website: {site_url}
Check Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
Status: {check_results.get('status', 'Completed')}

Key Metrics:
- Pages Crawled: {check_results.get('pages_crawled', 0)}
- Broken Links: {check_results.get('broken_links_count', 0)}
- Missing Meta Tags: {check_results.get('missing_meta_tags_count', 0)}

Quick Actions:
- View Dashboard: {dashboard_url}/website/{check_results.get('website_id')}
- View History: {dashboard_url}/website/{check_results.get('website_id')}/history
- View Crawler Results: {dashboard_url}/website/{check_results.get('website_id')}/crawler

This is an automated report from your Website Monitoring System.
Visit Dashboard: {dashboard_url}
    """

    # Determine recipients
    target_recipients = recipient_emails if recipient_emails else []
    
    # If no specific recipients, use default from config
    if not target_recipients:
        default_email = config.get('default_notification_email')
        if default_email:
            target_recipients = [default_email]
            logger.info(f"Using default email {default_email} for {site_name}")
        else:
            logger.warning(f"No recipient emails configured for {site_name} and no default email set")
            return False

    # Send the email
    try:
        return send_email_alert(subject, html_body, text_body, target_recipients)
    except Exception as e:
        logger.error(f"Failed to send email report for {site_name}: {e}")
        return False

def send_email_alert(subject: str, body_html: str, body_text: str = None, recipient_emails: list = None, attachments: list = None):
    """
    Sends an email alert using SMTP settings from the configuration.
    Simplified version for better reliability.
    """
    try:
        config = get_config_dynamic()
        
        # Get email configuration
        smtp_server = config.get('smtp_server')
        smtp_port = config.get('smtp_port', 587)
        smtp_username = config.get('smtp_username')
        smtp_password = config.get('smtp_password')
        from_email = config.get('notification_email_from')
        use_tls = config.get('smtp_use_tls', True)
        use_ssl = config.get('smtp_use_ssl', False)
        
        # Validate required configuration
        if not all([smtp_server, smtp_username, smtp_password, from_email]):
            logger.error("Email configuration missing required fields")
            return False

        # Use default recipient if none provided
        if not recipient_emails:
            default_email = config.get('default_notification_email')
            if default_email:
                recipient_emails = [default_email]
                logger.info(f"Using default email {default_email}")
            else:
                logger.warning("No recipient emails provided and no default email set")
                return False

        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = from_email
        msg['To'] = ', '.join(recipient_emails)
        
        # Add text part
        if body_text:
            text_part = MIMEText(body_text, 'plain', 'utf-8')
            msg.attach(text_part)
        
        # Add HTML part
        html_part = MIMEText(body_html, 'html', 'utf-8')
        msg.attach(html_part)
        
        # Add attachments if any
        if attachments:
            for attachment in attachments:
                msg.attach(attachment)

        # Send email
        if use_ssl:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port)
            if use_tls:
                server.starttls()
        
        server.login(smtp_username, smtp_password)
        server.send_message(msg)
        server.quit()
        
        logger.info(f"Email sent successfully to {', '.join(recipient_emails)}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False

# Simplified versions of other email functions
def _send_visual_check_email(website: dict, check_record: dict):
    """Send visual check email with simple HTML."""
    return send_report(website, check_record)

def _send_crawl_check_email(website: dict, check_record: dict):
    """Send crawl check email with simple HTML."""
    return send_report(website, check_record)

def _send_blur_check_email(website: dict, check_record: dict):
    """Send blur check email with simple HTML."""
    return send_report(website, check_record)

def send_performance_email(website: dict, check_record: dict):
    """Send performance email with simple HTML."""
    return send_report(website, check_record)

def _send_baseline_check_email(website: dict, check_record: dict):
    """Send baseline check email with simple HTML."""
    return send_report(website, check_record)

def _send_full_check_email(website: dict, check_record: dict):
    """Send full check email with simple HTML."""
    return send_report(website, check_record)
