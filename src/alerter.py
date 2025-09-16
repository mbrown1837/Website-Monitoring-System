import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage # Import for embedding images
import html # Added for html.escape
import os # For path handling
from datetime import datetime, timezone
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
    This is the new main function for sending alerts.
    """
    site_name = website.get('name', 'N/A')
    site_url = website.get('url', 'N/A')
    recipient_emails = website.get('notification_emails', [])
    
    # Simplified logic: If a significant change was detected, the alert is a "Change Detected" report.
    # The scheduler already determined this based on thresholds.
    is_change_report = check_results.get('significant_change_detected', False)

    # These flags determine which SECTIONS to add to the report.
    has_visual_change = 'visual_diff_image_path' in check_results and check_results.get('visual_diff_image_path') is not None
    has_crawl_issues = check_results.get('crawler_results', {}).get('total_broken_links', 0) > 0 or \
                       check_results.get('crawler_results', {}).get('total_missing_meta_tags', 0) > 0
    has_performance_data = 'performance_check' in check_results and check_results.get('performance_check') is not None
    
    monitoring_mode = website.get('monitoring_mode', 'full') # Default to 'full'

    subject = f"Monitoring Report for {site_name}"
    if is_change_report:
        subject = f"Change Detected on {site_name}"
    elif has_performance_data:
        subject = f"Performance Report for {site_name}"

    # --- Build HTML Body ---
    # Enhanced modern styling for the email
    html_style = """
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif; 
            margin: 0; padding: 0; color: #2c3e50; background-color: #f8f9fa; 
            line-height: 1.6;
        }
        .email-container { 
            max-width: 800px; margin: 20px auto; background: white; 
            border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); 
            overflow: hidden;
        }
        .header { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            padding: 30px 20px; color: white; text-align: center;
        }
        .header h1 { margin: 0; font-size: 28px; font-weight: 600; }
        .header .subtitle { margin: 8px 0 0 0; font-size: 16px; opacity: 0.9; }
        .content { padding: 30px; }
        .content-section { 
            margin-bottom: 30px; 
            padding: 20px; 
            background: #f8f9fa; 
            border-radius: 8px; 
            border-left: 4px solid #667eea;
        }
        .content-section h3 { 
            margin: 0 0 15px 0; color: #2c3e50; font-size: 20px; 
            border-bottom: 2px solid #e9ecef; padding-bottom: 10px;
        }
        .summary-table { 
            width: 100%; border-collapse: collapse; margin-top: 15px; 
            background: white; border-radius: 8px; overflow: hidden;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        }
        .summary-table th, .summary-table td { 
            padding: 12px 15px; text-align: left; border-bottom: 1px solid #e9ecef;
        }
        .summary-table th { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white; font-weight: 600; font-size: 14px;
        }
        .summary-table tr:hover { background-color: #f8f9fa; }
        .status-badge { 
            display: inline-block; padding: 6px 12px; border-radius: 20px; 
            font-size: 12px; font-weight: 600; text-transform: uppercase;
        }
        .status-success { background: #d4edda; color: #155724; }
        .status-warning { background: #fff3cd; color: #856404; }
        .status-error { background: #f8d7da; color: #721c24; }
        .status-info { background: #d1ecf1; color: #0c5460; }
        .metric-card { 
            display: inline-block; background: white; padding: 15px; 
            margin: 5px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            text-align: center; min-width: 120px;
        }
        .metric-value { font-size: 24px; font-weight: 700; color: #667eea; }
        .metric-label { font-size: 12px; color: #6c757d; text-transform: uppercase; }
        .image-container { 
            text-align: center; margin: 20px 0; 
            background: white; padding: 20px; border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        }
        .image-container img { 
            max-width: 100%; border-radius: 8px; 
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        .action-button { 
            display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white; padding: 12px 24px; text-decoration: none; 
            border-radius: 6px; font-weight: 600; margin: 10px 5px;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
            transition: transform 0.2s;
        }
        .action-button:hover { transform: translateY(-2px); }
        .footer { 
            background: #2c3e50; color: #ecf0f1; padding: 30px; 
            text-align: center; font-size: 14px;
        }
        .footer a { color: #3498db; text-decoration: none; }
        .footer a:hover { text-decoration: underline; }
        .divider { height: 1px; background: #e9ecef; margin: 20px 0; }
        .highlight-box { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white; padding: 20px; border-radius: 8px; margin: 20px 0;
        }
        .recommendations { 
            background: #fff3cd; border: 1px solid #ffeaa7; 
            padding: 20px; border-radius: 8px; margin: 20px 0;
        }
        .recommendations h4 { color: #856404; margin-top: 0; }
        @media (max-width: 600px) {
            .email-container { margin: 10px; border-radius: 8px; }
            .content { padding: 20px; }
            .header h1 { font-size: 24px; }
            .metric-card { min-width: 100px; margin: 3px; }
        }
    </style>
    """
    
    html_body_parts = [
        f"<html><head>{html_style}</head><body><div class='email-container'>",
        f"<div class='header'>",
        f"<h1>🌐 Website Monitoring Report</h1>",
        f"<div class='subtitle'>{html.escape(site_name)}</div>",
        f"</div>",
        f"<div class='content'>",
        f"<div class='content-section'>",
        f"<h3>📊 Check Summary</h3>",
        f"<p>A comprehensive check has been completed for <strong><a href='{html.escape(site_url)}'>{html.escape(site_url)}</a></strong></p>",
        f"<p><strong>Check Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>",
        f"</div>"
    ]
    
    attachments = []

    # If it's a change report, add the reasons.
    if is_change_report:
        reasons = check_results.get('reasons', [])
        html_body_parts.append("<div class='content-section'>")
        html_body_parts.append("<h3>🚨 Changes Detected</h3>")
        html_body_parts.append("<div class='highlight-box'>")
        html_body_parts.append(f"<h4>⚠️ {len(reasons)} significant change(s) detected</h4>")
        html_body_parts.append("<ul>")
        for reason in reasons:
            html_body_parts.append(f"<li>{html.escape(reason)}</li>")
        html_body_parts.append("</ul>")
        html_body_parts.append("</div>")
        html_body_parts.append("</div>")

    # --- Section 1: Visual Change Report ---
    if has_visual_change and monitoring_mode in ['full', 'visual']:
        diff_image_path = check_results.get('visual_diff_image_path')
        page_url = check_results.get('url', site_url) # URL of the specific page with changes
        
        html_body_parts.append("<div class='content-section'>")
        html_body_parts.append("<h3>👁️ Visual Comparison</h3>")
        
        if diff_image_path and os.path.exists(diff_image_path):
            html_body_parts.append(f"<p>A visual change was detected on the page: <a href='{html.escape(page_url)}'>{html.escape(page_url)}</a></p>")
            html_body_parts.append("<div class='image-container'>")
            html_body_parts.append("<h4>📸 Before vs. After Comparison</h4>")
            html_body_parts.append("<img src='cid:visual_diff_image' alt='Visual Difference Comparison'>")
            html_body_parts.append("</div>")
            
            # Prepare image attachment
            try:
                with open(diff_image_path, 'rb') as f:
                    img = MIMEImage(f.read())
                    img.add_header('Content-ID', '<visual_diff_image>')
                    img.add_header('Content-Disposition', 'inline', filename=os.path.basename(diff_image_path))
                    attachments.append(img)
            except Exception as e:
                logger.error(f"Failed to read or attach diff image at {diff_image_path}: {e}")
                html_body_parts.append("<div class='status-badge status-error'>Error loading visual comparison image</div>")
        else:
             html_body_parts.append("<div class='status-badge status-warning'>Visual difference image not available</div>")
        html_body_parts.append("</div>")

    # --- Section 2: Crawler Health Report ---
    if has_crawl_issues and monitoring_mode in ['full', 'crawl']:
        if not is_change_report: # Avoid double subjects
            subject = f"Crawler Issues Found on {site_name}"
        
        crawler_results = check_results.get('crawler_results', {})
        broken_links = crawler_results.get('broken_links', [])
        missing_meta_tags = crawler_results.get('missing_meta_tags', [])
        
        html_body_parts.append("<div class='content-section'>")
        html_body_parts.append("<h3>🕷️ Crawler Health Report</h3>")
        
        # Crawl metrics cards
        total_pages = crawler_results.get('total_pages_crawled', 0)
        total_links = crawler_results.get('total_links', 0)
        total_images = crawler_results.get('total_images', 0)
        
        html_body_parts.append("<div style='display: flex; flex-wrap: wrap; margin: 20px 0;'>")
        html_body_parts.append(f"<div class='metric-card'><div class='metric-value'>{total_pages}</div><div class='metric-label'>Pages Crawled</div></div>")
        html_body_parts.append(f"<div class='metric-card'><div class='metric-value'>{total_links}</div><div class='metric-label'>Links Found</div></div>")
        html_body_parts.append(f"<div class='metric-card'><div class='metric-value'>{total_images}</div><div class='metric-label'>Images Found</div></div>")
        html_body_parts.append(f"<div class='metric-card'><div class='metric-value'>{len(broken_links)}</div><div class='metric-label'>Broken Links</div></div>")
        html_body_parts.append("</div>")
        
        if not broken_links:
            html_body_parts.append("<div class='status-badge status-success'>✅ No broken links found</div>")
        else:
            subject = f"Action Required: Broken Links Found on {site_name}"
            html_body_parts.append(f"<div class='status-badge status-error'>❌ Found {len(broken_links)} broken link(s)</div>")
            html_body_parts.append("<table class='summary-table'>")
            html_body_parts.append("<tr><th>Broken URL</th><th>Status Code</th><th>Found On Page</th></tr>")
            for link in broken_links[:10]: # Limit for email brevity
                link_url = html.escape(link.get('url', 'N/A'))
                status = html.escape(str(link.get('status_code', 'N/A')))
                source = html.escape(link.get('source_page', 'N/A'))
                status_class = "status-error" if str(status).startswith(('4', '5')) else "status-warning"
                html_body_parts.append(f"<tr><td><a href='{link_url}'>{link_url}</a></td><td class='{status_class}'>{status}</td><td><a href='{source}'>{source}</a></td></tr>")
            html_body_parts.append("</table>")
            if len(broken_links) > 10:
                html_body_parts.append(f"<p><em>...and {len(broken_links) - 10} more broken links. Check the dashboard for complete details.</em></p>")
        
        # Missing meta tags section
        if missing_meta_tags:
            html_body_parts.append(f"<div class='status-badge status-warning'>⚠️ {len(missing_meta_tags)} pages with missing meta tags</div>")
            html_body_parts.append("<h4>Missing Meta Tags</h4>")
            html_body_parts.append("<table class='summary-table'>")
            html_body_parts.append("<tr><th>Page</th><th>Missing Tag</th><th>Tag Type</th></tr>")
            for tag in missing_meta_tags[:5]:  # Show first 5
                page_url = html.escape(tag.get('url', 'N/A'))
                tag_name = html.escape(tag.get('tag_name', 'N/A'))
                tag_type = html.escape(tag.get('tag_type', 'N/A'))
                html_body_parts.append(f"<tr><td><a href='{page_url}'>{page_url}</a></td><td>{tag_name}</td><td>{tag_type}</td></tr>")
            html_body_parts.append("</table>")
            if len(missing_meta_tags) > 5:
                html_body_parts.append(f"<p><em>...and {len(missing_meta_tags) - 5} more missing meta tags.</em></p>")
        else:
            html_body_parts.append("<div class='status-badge status-success'>✅ No missing meta tags found</div>")
        
        html_body_parts.append("</div>")

    # If no specific issues were flagged, but it was a crawl check, send a success report
    elif check_results.get('check_type') == 'crawl':
        subject = f"Crawl Completed for {site_name}: No Issues Found"
        crawler_results = check_results.get('crawler_results', {})
        total_pages = crawler_results.get('total_pages_crawled', 0)
        
        html_body_parts.append("<div class='content-section'><h3>Crawler Health Report</h3>")
        html_body_parts.append(f"<p style='color: green;'><strong>Crawl completed successfully. No broken links or major issues found.</strong></p>")
        html_body_parts.append(f"<p>Total pages crawled: <strong>{total_pages}</strong>.</p>")
        html_body_parts.append("</div>")

    # --- Section 3: Performance Report ---
    if has_performance_data and monitoring_mode in ['full', 'performance']:
        performance_data = check_results.get('performance_check', {})
        performance_summary = performance_data.get('performance_check_summary', {})
        
        html_body_parts.append("<div class='content-section'>")
        html_body_parts.append("<h3>⚡ Performance Analysis</h3>")
        
        if performance_summary:
            pages_analyzed = performance_summary.get('pages_analyzed', 0)
            avg_score = performance_summary.get('average_performance_score', 0)
            
            # Performance overview cards
            html_body_parts.append("<div style='display: flex; flex-wrap: wrap; margin: 20px 0;'>")
            html_body_parts.append(f"<div class='metric-card'><div class='metric-value'>{pages_analyzed}</div><div class='metric-label'>Pages Analyzed</div></div>")
            html_body_parts.append(f"<div class='metric-card'><div class='metric-value'>{avg_score:.1f}</div><div class='metric-label'>Avg Score</div></div>")
            html_body_parts.append("</div>")
            
            # Performance grade with badge
            if avg_score >= 90:
                grade_class = "status-success"
                grade_text = "Excellent"
                grade_emoji = "🟢"
            elif avg_score >= 70:
                grade_class = "status-warning"
                grade_text = "Good"
                grade_emoji = "🟡"
            elif avg_score >= 50:
                grade_class = "status-error"
                grade_text = "Needs Improvement"
                grade_emoji = "🟠"
            else:
                grade_class = "status-error"
                grade_text = "Poor"
                grade_emoji = "🔴"
            
            html_body_parts.append(f"<div class='highlight-box'>")
            html_body_parts.append(f"<h4>{grade_emoji} Overall Performance Grade: {grade_text}</h4>")
            html_body_parts.append(f"<p>Average Score: <strong>{avg_score:.1f}/100</strong></p>")
            html_body_parts.append("</div>")
            
            # Detailed metrics table
            html_body_parts.append("<h4>📊 Detailed Performance Metrics</h4>")
            html_body_parts.append("<table class='summary-table'>")
            html_body_parts.append("<tr><th>Metric</th><th>Mobile</th><th>Desktop</th><th>Status</th></tr>")
            
            # Get mobile and desktop averages
            mobile_avg = performance_summary.get('mobile_average', {})
            desktop_avg = performance_summary.get('desktop_average', {})
            
            metrics = [
                ('Performance Score', 'performance_score', 'performance_score'),
                ('First Contentful Paint (s)', 'fcp_score', 'fcp_score'),
                ('Largest Contentful Paint (s)', 'lcp_score', 'lcp_score'),
                ('Cumulative Layout Shift', 'cls_score', 'cls_score'),
                ('Speed Index (s)', 'speed_index', 'speed_index'),
                ('Total Blocking Time (ms)', 'tbt_score', 'tbt_score')
            ]
            
            for metric_name, mobile_key, desktop_key in metrics:
                mobile_val = mobile_avg.get(mobile_key, 0)
                desktop_val = desktop_avg.get(desktop_key, 0)
                
                # Determine status
                if metric_name == 'Performance Score':
                    mobile_status = "🟢 Good" if mobile_val >= 70 else "🔴 Poor" if mobile_val < 50 else "🟡 Fair"
                    desktop_status = "🟢 Good" if desktop_val >= 70 else "🔴 Poor" if desktop_val < 50 else "🟡 Fair"
                elif metric_name in ['First Contentful Paint (s)', 'Largest Contentful Paint (s)', 'Speed Index (s)', 'Total Blocking Time (ms)']:
                    mobile_status = "🟢 Good" if mobile_val <= 2.5 else "🔴 Poor" if mobile_val > 4 else "🟡 Fair"
                    desktop_status = "🟢 Good" if desktop_val <= 2.5 else "🔴 Poor" if desktop_val > 4 else "🟡 Fair"
                else:  # CLS
                    mobile_status = "🟢 Good" if mobile_val <= 0.1 else "🔴 Poor" if mobile_val > 0.25 else "🟡 Fair"
                    desktop_status = "🟢 Good" if desktop_val <= 0.1 else "🔴 Poor" if desktop_val > 0.25 else "🟡 Fair"
                
                html_body_parts.append(f"<tr>")
                html_body_parts.append(f"<td><strong>{metric_name}</strong></td>")
                html_body_parts.append(f"<td>{mobile_val:.2f}</td>")
                html_body_parts.append(f"<td>{desktop_val:.2f}</td>")
                html_body_parts.append(f"<td>{mobile_status} / {desktop_status}</td>")
                html_body_parts.append(f"</tr>")
            
            html_body_parts.append("</table>")
            
            # Performance recommendations
            if avg_score < 70:
                html_body_parts.append("<div class='recommendations'>")
                html_body_parts.append("<h4>💡 Performance Recommendations</h4>")
                html_body_parts.append("<ul>")
                if mobile_avg.get('fcp_score', 0) > 2.5:
                    html_body_parts.append("<li><strong>Optimize First Contentful Paint:</strong> Reduce server response time and eliminate render-blocking resources</li>")
                if mobile_avg.get('lcp_score', 0) > 2.5:
                    html_body_parts.append("<li><strong>Improve Largest Contentful Paint:</strong> Optimize images and reduce resource load times</li>")
                if mobile_avg.get('cls_score', 0) > 0.1:
                    html_body_parts.append("<li><strong>Reduce Cumulative Layout Shift:</strong> Ensure images and ads have size attributes</li>")
                if mobile_avg.get('tbt_score', 0) > 200:
                    html_body_parts.append("<li><strong>Minimize Total Blocking Time:</strong> Reduce JavaScript execution time and implement code splitting</li>")
                html_body_parts.append("</ul>")
                html_body_parts.append("</div>")
        else:
            html_body_parts.append("<div class='status-badge status-warning'>⚠️ Performance data not available</div>")
        
        html_body_parts.append("</div>")
    
    # --- Dashboard Links and Actions ---
    config = get_config_dynamic()
    dashboard_url = config.get('dashboard_url', 'http://localhost:5001')
    website_id = website.get('id', '')
    
    html_body_parts.append("<div class='content-section'>")
    html_body_parts.append("<h3>🔗 Quick Actions</h3>")
    html_body_parts.append("<div style='text-align: center; margin: 20px 0;'>")
    html_body_parts.append(f"<a href='{dashboard_url}/website/{website_id}' class='action-button' target='_blank'>View Website Details</a>")
    html_body_parts.append(f"<a href='{dashboard_url}/website/history/{website_id}' class='action-button' target='_blank'>View Full History</a>")
    html_body_parts.append(f"<a href='{dashboard_url}' class='action-button' target='_blank'>Main Dashboard</a>")
    html_body_parts.append("</div>")
        html_body_parts.append("</div>")
    
    # --- Footer ---
    html_body_parts.append("<div class='footer'>")
    html_body_parts.append("<p><strong>🌐 Website Monitoring System</strong></p>")
    html_body_parts.append(f"<p>This is an automated monitoring report for <strong>{html.escape(site_name)}</strong></p>")
    html_body_parts.append(f"<p>Report generated on {datetime.now().strftime('%Y-%m-%d at %H:%M:%S UTC')}</p>")
    html_body_parts.append(f"<p><a href='{dashboard_url}'>Visit Dashboard</a> | <a href='{dashboard_url}/settings'>Manage Settings</a></p>")
    html_body_parts.append("</div>")
    html_body_parts.append("</div></body></html>")
    
    final_html = "".join(html_body_parts)

    # Use the existing send_email_alert function to handle SMTP logic
    try:
    return send_email_alert(subject, final_html, attachments=attachments, recipient_emails=recipient_emails)
    except Exception as e:
        logger.error(f"Failed to send email report for {site_name}: {e}")
        # Don't raise the exception - let the monitoring continue even if email fails
        return False

def send_email_alert(subject: str, body_html: str, body_text: str = None, recipient_emails: list = None, attachments: list = None):
    """
    Sends an email alert using SMTP settings from the configuration.
    (Now with attachment support)
    """
    config = get_config_dynamic()
    logger.info(f"Email config loaded - from: {config.get('notification_email_from')}, to: {config.get('notification_email_to')}, smtp_server: {config.get('smtp_server')}")
    smtp_sender = config.get('notification_email_from')
    default_recipients_str = config.get('notification_email_to', config.get('default_notification_email'))
    
    target_recipients = []
    if recipient_emails:
        target_recipients = [email for email in recipient_emails if email.strip()]
    
    if not target_recipients and default_recipients_str:
        if isinstance(default_recipients_str, str):
            target_recipients = [email.strip() for email in default_recipients_str.split(',') if email.strip()]
        elif isinstance(default_recipients_str, list):
            target_recipients = [email for email in default_recipients_str if email.strip()]

    if not target_recipients:
        logger.error("No recipient email addresses specified. Cannot send alert.")
        return False

    email_config = {
        'from': smtp_sender,
        'to': ", ".join(target_recipients),
        'smtp_server': config.get('smtp_server'),
        'smtp_port': config.get('smtp_port', 587),
        'smtp_username': config.get('smtp_username'),
        'smtp_password': config.get('smtp_password'),
        'use_tls': config.get('smtp_use_tls', True),
        'use_ssl': config.get('smtp_use_ssl', False)
    }

    required_fields = ['from', 'to', 'smtp_server']
    if not all(email_config.get(field) for field in required_fields):
        logger.error(f"Email configuration missing required fields: {required_fields}. Cannot send alert.")
        return False

    # Use 'mixed' when attachments are present, 'alternative' for just text/html
    msg = MIMEMultipart('mixed' if attachments else 'alternative')
    msg['Subject'] = subject
    msg['From'] = email_config['from']
    msg['To'] = email_config['to']

    # The HTML part should be related to the main content
    msg_related = MIMEMultipart('related')
    
    # The body of the email (HTML)
    # If there's plain text, it's an alternative to the related part
    msg_alternative = MIMEMultipart('alternative')
    msg_related.attach(msg_alternative)

    # Attach HTML part
    part_html = MIMEText(body_html, 'html')
    msg_alternative.attach(part_html)

    # Attach the msg_related to the main message
    msg.attach(msg_related)
    
    # Attach any images or other files
    if attachments:
        for attachment in attachments:
            msg.attach(attachment)

    try:
        logger.info(f"Attempting to send email report to {email_config['to']}")
        
        # Try multiple connection methods with better error handling
        connection_successful = False
        
        # Method 1: Try SSL first (for port 465)
        if email_config.get('use_ssl', False):
            try:
                logger.info(f"Attempting SSL connection to {email_config['smtp_server']}:{email_config['smtp_port']}")
                with smtplib.SMTP_SSL(email_config['smtp_server'], email_config['smtp_port'], timeout=15) as server:
                if email_config['smtp_username'] and email_config['smtp_password']:
                    server.login(email_config['smtp_username'], email_config['smtp_password'])
                server.sendmail(email_config['from'], target_recipients, msg.as_string())
                connection_successful = True
                logger.info("SSL connection successful")
            except Exception as ssl_error:
                logger.warning(f"SSL connection failed: {ssl_error}")
        
        # Method 2: Try TLS if SSL failed
        if not connection_successful:
            try:
                logger.info(f"Attempting TLS connection to {email_config['smtp_server']}:{email_config['smtp_port']}")
                with smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port'], timeout=15) as server:
                if email_config.get('use_tls', True):
                    server.starttls()
                if email_config['smtp_username'] and email_config['smtp_password']:
                    server.login(email_config['smtp_username'], email_config['smtp_password'])
                server.sendmail(email_config['from'], target_recipients, msg.as_string())
                connection_successful = True
                logger.info("TLS connection successful")
            except Exception as tls_error:
                logger.warning(f"TLS connection failed: {tls_error}")
        
        # Method 3: Try without authentication as last resort
        if not connection_successful:
            try:
                logger.info(f"Attempting unauthenticated connection to {email_config['smtp_server']}:{email_config['smtp_port']}")
                with smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port'], timeout=15) as server:
                    server.sendmail(email_config['from'], target_recipients, msg.as_string())
                connection_successful = True
                logger.info("Unauthenticated connection successful")
            except Exception as unauth_error:
                logger.error(f"All connection methods failed. Last error: {unauth_error}")
                raise unauth_error
        
        if not connection_successful:
            raise Exception("All SMTP connection methods failed")
        
        logger.info(f"Email report '{subject}' sent successfully to {email_config['to']}.")
        return True
    except Exception as e:
        logger.error(f"Failed to send email report: {e}", exc_info=True)
        return False

def format_alert_message(site_url: str, site_name: str, check_record: dict) -> tuple[str, str, str]:
    """
    Formats the subject, HTML body, and plain text body for an alert email.
    """
    subject = f"Alert: Change Detected on {html.escape(site_name) if site_name else html.escape(site_url)}"
    
    # --- HTML Body Construction ---
    html_body_parts = [
        "<html><body>",
        "<h2>Change Detected on Monitored Website</h2>",
        f"<p><strong>Website:</strong> {html.escape(site_name) if site_name else html.escape(site_url)} (<a href=\"{html.escape(site_url)}\">{html.escape(site_url)}</a>)</p>",
        f"<p><strong>Checked at (UTC):</strong> {html.escape(str(check_record.get('timestamp_utc')))}</p>",
        f"<p><strong>Status:</strong> {html.escape(str(check_record.get('status')))}</p>",
        "<h3>Summary of Changes:</h3>",
        "<ul>"
    ]

    # --- Plain Text Body Construction ---
    text_body_parts = [
        "Change Detected on Monitored Website\n",
        f"Website: {site_name if site_name else site_url} ({site_url})",
        f"Checked at (UTC): {check_record.get('timestamp_utc')}",
        f"Status: {check_record.get('status')}\n",
        "Summary of Changes:"
    ]

    # Add crawler results if available
    if check_record.get('crawler_results'):
        crawler_results = check_record.get('crawler_results', {})
        broken_links_count = crawler_results.get('broken_links_count', 0)
        missing_meta_tags_count = crawler_results.get('missing_meta_tags_count', 0)
        
        # Add crawler summary to the alert
        if broken_links_count > 0 or missing_meta_tags_count > 0:
            html_body_parts.append("<h3>Crawler Issues Detected:</h3>")
            text_body_parts.append("\nCrawler Issues Detected:")
            
        if broken_links_count > 0:
            html_body_parts.append(f"<li><strong>Broken Links:</strong> {broken_links_count} broken links detected</li>")
            text_body_parts.append(f"- Broken Links: {broken_links_count} broken links detected")
            
        if missing_meta_tags_count > 0:
            html_body_parts.append(f"<li><strong>Missing Meta Tags:</strong> {missing_meta_tags_count} missing meta tags detected</li>")
            text_body_parts.append(f"- Missing Meta Tags: {missing_meta_tags_count} missing meta tags detected")
            
        # Add a link to view detailed crawler results
        config = get_config_dynamic()
        dashboard_url = config.get('dashboard_url', 'http://localhost:5001')
        html_body_parts.append(f"<p><a href=\"{dashboard_url}/website/{check_record.get('site_id')}/crawler\">View Detailed Crawler Results</a></p>")
        text_body_parts.append(f"\nView Detailed Crawler Results: {dashboard_url}/website/{check_record.get('site_id')}/crawler")
    
    # Crawler error if any
    if check_record.get('crawler_error'):
        html_body_parts.append(f"<li><strong>Crawler Error:</strong> {html.escape(check_record.get('crawler_error'))}</li>")
        text_body_parts.append(f"- Crawler Error: {check_record.get('crawler_error')}")

    if check_record.get('html_content_hash'):
        html_body_parts.append(f"<li>New HTML content hash: {html.escape(str(check_record.get('html_content_hash')))}</li>")
        text_body_parts.append(f"- New HTML content hash: {check_record.get('html_content_hash')}")

    if 'content_diff_score' in check_record and check_record['content_diff_score'] is not None:
        similarity_percent = check_record['content_diff_score'] * 100
        html_body_parts.append(f"<li>Content Similarity: {similarity_percent:.2f}%</li>")
        text_body_parts.append(f"- Content Similarity: {similarity_percent:.2f}%")

    # For brevity in alerts, we might keep diff details summarized or link to a full report if one is generated and accessible
    # The current implementation shows a snippet which is reasonable for alerts.
    content_diff_details = check_record.get('content_diff_details')
    if content_diff_details:
        html_snippet = "<br>".join(html.escape(line) for line in content_diff_details[:10])
        text_snippet = "\n".join(content_diff_details[:10])
        if len(content_diff_details) > 10:
            html_snippet += "<br>... (diff truncated)"
            text_snippet += "\n... (diff truncated)"
        html_body_parts.append(f"<li>Detailed Text Differences (difflib): <pre>{html_snippet}</pre></li>")
        text_body_parts.append(f"- Detailed Text Differences (difflib):\n{text_snippet}")

    if 'semantic_diff_score' in check_record and check_record['semantic_diff_score'] is not None:
        semantic_similarity_percent = check_record['semantic_diff_score'] * 100
        html_body_parts.append(f"<li>Semantic Content Similarity: {semantic_similarity_percent:.2f}% (diff-match-patch)</li>")
        text_body_parts.append(f"- Semantic Content Similarity: {semantic_similarity_percent:.2f}% (diff-match-patch)")
        
        semantic_diff_details = check_record.get('semantic_diff_details')
        if semantic_diff_details:
            html_s_snippet_parts = []
            text_s_snippet_parts = []
            for op, text_val in semantic_diff_details[:10]: # show up to 10 operations
                op_char = '=' if op == 0 else '-' if op == -1 else '+'
                escaped_text_html = html.escape(text_val).replace("\n", "<br>")
                html_s_snippet_parts.append(f"{op_char} {escaped_text_html}")
                text_s_snippet_parts.append(f"  {op_char} {text_val}") # Plain text, no need to escape newlines here
            
            html_s_snippet = "<br>".join(html_s_snippet_parts)
            text_s_snippet = "\n".join(text_s_snippet_parts)

            if len(semantic_diff_details) > 10:
                html_s_snippet += "<br>... (diff truncated)"
                text_s_snippet += "\n  ... (diff truncated)"
            html_body_parts.append(f"<li>Semantic Differences (diff-match-patch): <pre>{html_s_snippet}</pre></li>")
            text_body_parts.append(f"- Semantic Differences (diff-match-patch):\n{text_s_snippet}")

    if 'structure_diff_score' in check_record and check_record['structure_diff_score'] is not None:
        struct_similarity_percent = check_record['structure_diff_score'] * 100
        html_body_parts.append(f"<li>Structure Similarity: {struct_similarity_percent:.2f}%</li>")
        text_body_parts.append(f"- Structure Similarity: {struct_similarity_percent:.2f}%")

    if 'visual_diff_score' in check_record and check_record['visual_diff_score'] is not None:
        visual_diff_score = check_record['visual_diff_score'] 
        html_body_parts.append(f"<li>Visual Difference Score (MSE): {visual_diff_score:.4f} (0=identical)</li>")
        text_body_parts.append(f"- Visual Difference Score (MSE): {visual_diff_score:.4f} (0=identical)")
        if check_record.get('visual_snapshot_path'):
             html_body_parts.append(f"<li>Current visual snapshot: {html.escape(str(check_record.get('visual_snapshot_path')))}</li>")
             text_body_parts.append(f"- Current visual snapshot: {check_record.get('visual_snapshot_path')}")
        if check_record.get('visual_diff_image_path'):
            html_body_parts.append(f"<li>Visual difference image: {html.escape(str(check_record.get('visual_diff_image_path')))}</li>")
            text_body_parts.append(f"- Visual difference image: {check_record.get('visual_diff_image_path')}")

    if 'ssim_score' in check_record and check_record['ssim_score'] is not None:
        ssim_score = check_record['ssim_score'] 
        html_body_parts.append(f"<li>Visual Structural Similarity (SSIM): {ssim_score:.4f} (1=identical)</li>")
        text_body_parts.append(f"- Visual Structural Similarity (SSIM): {ssim_score:.4f} (1=identical)")

    meta_changes = check_record.get('meta_changes')
    if meta_changes:
        html_meta_list = []
        text_meta_list = []
        for tag, vals in meta_changes.items():
            old_val = html.escape(str(vals.get('old', 'N/A')))
            new_val = html.escape(str(vals.get('new', 'N/A')))
            tag_esc = html.escape(tag)
            html_meta_list.append(f"<li><em>{tag_esc}</em>: from '<code>{old_val}</code>' to '<code>{new_val}</code>'</li>")
            text_meta_list.append(f"  - {tag}: from '{vals.get('old', 'N/A')}' to '{vals.get('new', 'N/A')}'")
        if html_meta_list:
            html_body_parts.append("<li>Meta Tags Changed:<ul>" + "".join(html_meta_list) + "</ul></li>")
            text_body_parts.append("- Meta Tags Changed:\n" + "\n".join(text_meta_list))

    link_changes = check_record.get('link_changes')
    if link_changes:
        html_link_parts = []
        text_link_parts = []
        added_links = link_changes.get('added', [])
        removed_links = link_changes.get('removed', [])
        if added_links:
            html_link_parts.append("<h5>Added Links:</h5><ul>" + "".join([f"<li><code>{html.escape(link)}</code></li>" for link in added_links[:5]]) + ("<li>...and more</li>" if len(added_links) > 5 else "") + "</ul>")
            text_link_parts.append(f"  Added Links ({len(added_links)}): {', '.join(list(added_links)[:3])}{'...' if len(added_links) > 3 else ''}")
        if removed_links:
            html_link_parts.append("<h5>Removed Links:</h5><ul>" + "".join([f"<li><code>{html.escape(link)}</code></li>" for link in removed_links[:5]]) + ("<li>...and more</li>" if len(removed_links) > 5 else "") + "</ul>")
            text_link_parts.append(f"  Removed Links ({len(removed_links)}): {', '.join(list(removed_links)[:3])}{'...' if len(removed_links) > 3 else ''}")
        if html_link_parts:
            html_body_parts.append("<li>Link Changes:" + "".join(html_link_parts) + "</li>")
            text_body_parts.append("- Link Changes:\n" + "\n".join(text_link_parts))

    image_src_changes = check_record.get('image_src_changes')
    if image_src_changes:
        html_img_parts = []
        text_img_parts = []
        added_imgs = image_src_changes.get('added_images', [])
        removed_imgs = image_src_changes.get('removed_images', [])
        if added_imgs:
            html_img_parts.append("<h5>Added Image Sources:</h5><ul>" + "".join([f"<li><code>{html.escape(src)}</code></li>" for src in added_imgs[:5]]) + ("<li>...and more</li>" if len(added_imgs) > 5 else "") + "</ul>")
            text_img_parts.append(f"  Added Image Sources ({len(added_imgs)}): {', '.join(list(added_imgs)[:3])}{'...' if len(added_imgs) > 3 else ''}")
        if removed_imgs:
            html_img_parts.append("<h5>Removed Image Sources:</h5><ul>" + "".join([f"<li><code>{html.escape(src)}</code></li>" for src in removed_imgs[:5]]) + ("<li>...and more</li>" if len(removed_imgs) > 5 else "") + "</ul>")
            text_img_parts.append(f"  Removed Image Sources ({len(removed_imgs)}): {', '.join(list(removed_imgs)[:3])}{'...' if len(removed_imgs) > 3 else ''}")
        if html_img_parts:
            html_body_parts.append("<li>Image Source Changes:" + "".join(html_img_parts) + "</li>")
            text_body_parts.append("- Image Source Changes:\n" + "\n".join(text_img_parts))
        
    canonical_change = check_record.get('canonical_url_change')
    if canonical_change:
        old_url = html.escape(str(canonical_change.get('old', 'N/A')))
        new_url = html.escape(str(canonical_change.get('new', 'N/A')))
        text_old = canonical_change.get('old', 'N/A')
        text_new = canonical_change.get('new', 'N/A')
        if text_old != text_new : # Ensure there is an actual change
            html_body_parts.append(f"<li>Canonical URL: changed from '<code>{old_url}</code>' to '<code>{new_url}</code>'.</li>")
            text_body_parts.append(f"- Canonical URL: changed from '{text_old}' to '{text_new}'.")

    html_body_parts.append("</ul>")

    # Add a link to the full detailed report if a CLI command for it exists and is known
    # For now, this is a placeholder concept.
    # html_body_parts.append(f'<p>For a full detailed report, run: cli_command_get_report --check_id {check_record.get("check_id")}</p>')

    html_body_parts.append("</body></html>")
    final_html_body = "".join(html_body_parts)
    final_text_body = "\n".join(text_body_parts)

    return subject, final_html_body, final_text_body

if __name__ == '__main__':
    logger.info("----- Alerter Demo -----")
    
    # IMPORTANT: For this demo to actually send an email, 
    # you MUST configure smtp settings in config/config.yaml
    # For example, using a Gmail account with an App Password:
    # smtp_sender_email: "your_gmail_address@gmail.com"
    # default_notification_email: "recipient_address@example.com" # Can be a comma-separated list
    # smtp_server: "smtp.gmail.com"
    # smtp_port: 587
    # smtp_username: "your_gmail_address@gmail.com"
    # smtp_password: "your_app_password_here" # NOT your regular Gmail password
    # smtp_use_tls: True

    # Check if SMTP is configured for a live test
    config = get_config_dynamic()
    can_send_live = all(config.get(k) for k in ['notification_email_from', 'notification_email_to', 'smtp_server', 'smtp_username', 'smtp_password'])

    sample_check_record_alert = {
        "check_id": "demo-check-123",
        "site_id": "demo-site-456",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "completed_with_changes",
        "html_snapshot_path": "data/snapshots/demo-site/html/demo.html",
        "html_content_hash": "abcdef123456",
        "visual_snapshot_path": "data/snapshots/demo-site/visual/demo.png",
        "visual_diff_image_path": "data/snapshots/demo-site/diffs/diff_demo.png",
        "visual_diff_score": 0.15,
        "content_diff_score": 0.85,
        "content_diff_details": ["- Old line 1", "+ New line 1", "  Common line 2", "- Old line 3"],
        "structure_diff_score": 0.90,
        "semantic_diff_score": 0.88, # Example semantic score
        "semantic_diff_details": [[0, "Unchanged text... "], [-1, "removed part"], [1, "added part"], [0, " more unchanged."]], # Example details
        "ssim_score": 0.92, # Example SSIM score
        "meta_changes": {"description": {"old": "Old boring description", "new": "New exciting description!"}},
        "link_changes": {"added": {"/new-link1", "/new-link2"}, "removed": {"/old-link"}},
        "image_src_changes": {"added_images": {"new_image.jpg"}},
        "canonical_url_change": {"old": "https://example.com/page", "new": "https://example.com/canonical-page"},
        "significant_change_detected": True
    }

    subj, html_b, text_b = format_alert_message("https://example.com/testpage", "My Test Site", sample_check_record_alert)
    print(f"Generated Alert Subject: {subj}")
    print(f"\nGenerated Alert HTML Body:\n{html_b}")
    print(f"\nGenerated Alert Text Body:\n{text_b}")

    if can_send_live:
        logger.info("SMTP settings appear to be configured. Attempting to send a live test email.")
        # Test sending to default recipient from config
        success_default = send_email_alert(subj, html_b, text_b)
        if success_default:
            logger.info(f"Test email sent successfully to default recipient(s): {config.get('notification_email_to')}.")
        else:
            logger.error("Failed to send test email to default recipient(s). Check logs and SMTP configuration.")
        
        # Test sending to a specific list (if different from default or for testing)
        test_specific_recipients = ["test1@example.com", "test2@example.com"]
        logger.info(f"Attempting to send a test email to specific recipients: {test_specific_recipients}")
        success_specific = send_email_alert(subj, html_b, text_b, recipient_emails=test_specific_recipients)
        if success_specific:
            logger.info(f"Test email sent successfully to {test_specific_recipients}.")
        else:
            logger.error(f"Failed to send test email to {test_specific_recipients}. Check logs and SMTP configuration.")
    else:
        logger.warning("SMTP settings not fully configured in config/config.yaml. Skipping live email send test.")
        logger.warning("To test email sending, please configure: notification_email_from, notification_email_to, smtp_server, smtp_port, smtp_username, smtp_password")

    logger.info("----- Alerter Demo Finished -----")

def send_single_check_email(website: dict, check_results: dict, check_type: str):
    """
    Sends a dedicated email notification for single check types.
    This function is called when specific check types are run independently.
    
    Args:
        website: Website configuration
        check_results: Results from the specific check
        check_type: Type of check ('visual', 'crawl', 'blur', 'performance')
    """
    site_name = website.get('name', 'N/A')
    site_url = website.get('url', 'N/A')
    recipient_emails = website.get('notification_emails', [])
    
    # Use default email if no recipient emails configured
    if not recipient_emails:
        config = get_config_dynamic()
        default_email = config.get('default_notification_email')
        if default_email:
            recipient_emails = [default_email]
            logger.info(f"Using default email {default_email} for {site_name}")
        else:
            logger.warning(f"No recipient emails configured for {site_name} and no default email set")
        return False
    
    # Create check-specific subject and content
    if check_type == 'visual':
        subject = f"Visual Check Report for {site_name}"
        return _send_visual_check_email(website, check_results, subject)
    elif check_type == 'crawl':
        subject = f"Crawl Check Report for {site_name}"
        return _send_crawl_check_email(website, check_results, subject)
    elif check_type == 'blur':
        subject = f"Blur Detection Report for {site_name}"
        return _send_blur_check_email(website, check_results, subject)
    elif check_type == 'performance':
        subject = f"Performance Report for {site_name}"
        return _send_performance_check_email(website, check_results, subject)
    elif check_type == 'baseline':
        subject = f"Baseline Creation Report for {site_name}"
        return _send_baseline_check_email(website, check_results, subject)
    elif check_type == 'full':
        subject = f"Full Check Report for {site_name}"
        return _send_full_check_email(website, check_results, subject)
    else:
        logger.error(f"Unknown check type: {check_type}")
        return False

def _send_visual_check_email(website: dict, check_results: dict, subject: str):
    """Send visual check specific email."""
    site_name = website.get('name', 'N/A')
    site_url = website.get('url', 'N/A')
    recipient_emails = website.get('notification_emails', [])
    
    # Use the same enhanced styling as the main report
    html_style = """
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif; 
            margin: 0; padding: 0; color: #2c3e50; background-color: #f8f9fa; 
            line-height: 1.6;
        }
        .email-container { 
            max-width: 800px; margin: 20px auto; background: white; 
            border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); 
            overflow: hidden;
        }
        .header { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            padding: 30px 20px; color: white; text-align: center;
        }
        .header h1 { margin: 0; font-size: 28px; font-weight: 600; }
        .header .subtitle { margin: 8px 0 0 0; font-size: 16px; opacity: 0.9; }
        .content { padding: 30px; }
        .content-section { 
            margin-bottom: 30px; 
            padding: 20px; 
            background: #f8f9fa; 
            border-radius: 8px; 
            border-left: 4px solid #667eea;
        }
        .content-section h3 { 
            margin: 0 0 15px 0; color: #2c3e50; font-size: 20px; 
            border-bottom: 2px solid #e9ecef; padding-bottom: 10px;
        }
        .summary-table { 
            width: 100%; border-collapse: collapse; margin-top: 15px; 
            background: white; border-radius: 8px; overflow: hidden;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        }
        .summary-table th, .summary-table td { 
            padding: 12px 15px; text-align: left; border-bottom: 1px solid #e9ecef;
        }
        .summary-table th { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white; font-weight: 600; font-size: 14px;
        }
        .summary-table tr:hover { background-color: #f8f9fa; }
        .status-badge { 
            display: inline-block; padding: 6px 12px; border-radius: 20px; 
            font-size: 12px; font-weight: 600; text-transform: uppercase;
        }
        .status-success { background: #d4edda; color: #155724; }
        .status-warning { background: #fff3cd; color: #856404; }
        .status-error { background: #f8d7da; color: #721c24; }
        .status-info { background: #d1ecf1; color: #0c5460; }
        .metric-card { 
            display: inline-block; background: white; padding: 15px; 
            margin: 5px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            text-align: center; min-width: 120px;
        }
        .metric-value { font-size: 24px; font-weight: 700; color: #667eea; }
        .metric-label { font-size: 12px; color: #6c757d; text-transform: uppercase; }
        .action-button { 
            display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white; padding: 12px 24px; text-decoration: none; 
            border-radius: 6px; font-weight: 600; margin: 10px 5px;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        }
        .footer { 
            background: #2c3e50; color: #ecf0f1; padding: 30px; 
            text-align: center; font-size: 14px;
        }
        .footer a { color: #3498db; text-decoration: none; }
        @media (max-width: 600px) {
            .email-container { margin: 10px; border-radius: 8px; }
            .content { padding: 20px; }
            .header h1 { font-size: 24px; }
        }
    </style>
    """
    
    # Get visual check data
    visual_data = check_results.get('visual_check', {})
    snapshots = visual_data.get('snapshots', [])
    baselines = visual_data.get('baselines', [])
    
    html_body_parts = [
        f"<html><head>{html_style}</head><body><div class='email-container'>",
        f"<div class='header'>",
        f"<h1>👁️ Visual Check Report</h1>",
        f"<div class='subtitle'>{html.escape(site_name)}</div>",
        f"</div>",
        f"<div class='content'>",
        f"<div class='content-section'>",
        f"<h3>📊 Check Summary</h3>",
        f"<p><strong>Website:</strong> {html.escape(site_name)}</p>",
        f"<p><strong>URL:</strong> <a href='{html.escape(site_url)}'>{html.escape(site_url)}</a></p>",
        f"<p><strong>Check Time:</strong> {check_results.get('timestamp', 'Unknown')}</p>",
        f"</div>"
    ]
    
    # Visual check summary
    if snapshots:
        html_body_parts.append("<div class='content-section'>")
        html_body_parts.append("<h3>👁️ Visual Check Summary</h3>")
        
        # Visual metrics cards
        html_body_parts.append("<div style='display: flex; flex-wrap: wrap; margin: 20px 0;'>")
        html_body_parts.append(f"<div class='metric-card'><div class='metric-value'>{len(snapshots)}</div><div class='metric-label'>Pages Screenshot</div></div>")
        html_body_parts.append(f"<div class='metric-card'><div class='metric-value'>{len(baselines)}</div><div class='metric-label'>Baselines Created</div></div>")
        html_body_parts.append(f"<div class='metric-card'><div class='metric-value'>{len([s for s in snapshots if any(b.get('url') == s.get('url') for b in baselines)])}</div><div class='metric-label'>Pages with Baselines</div></div>")
        html_body_parts.append("</div>")
        
        # Show pages that were checked
        html_body_parts.append("<h4>📄 Pages Checked</h4>")
        html_body_parts.append("<table class='summary-table'>")
        html_body_parts.append("<tr><th>Page</th><th>Status</th><th>Baseline Available</th></tr>")
        
        for snapshot in snapshots:
            page_url = snapshot.get('url', 'Unknown')
            page_title = snapshot.get('title', 'Unknown')
            has_baseline = any(b.get('url') == page_url for b in baselines)
            status = "Baseline Created" if has_baseline else "Screenshot Captured"
            status_class = "status-success" if has_baseline else "status-warning"
            
            html_body_parts.append(f"<tr>")
            html_body_parts.append(f"<td><a href='{html.escape(page_url)}'>{html.escape(page_title)}</a></td>")
            html_body_parts.append(f"<td><span class='status-badge {status_class}'>{status}</span></td>")
            html_body_parts.append(f"<td>{'✅ Yes' if has_baseline else '❌ No'}</td>")
            html_body_parts.append(f"</tr>")
        
        html_body_parts.append("</table>")
        html_body_parts.append("</div>")
    else:
        html_body_parts.append("<div class='content-section'>")
        html_body_parts.append("<div class='status-badge status-warning'>⚠️ No visual data available for this check</div>")
        html_body_parts.append("</div>")
    
    # Dashboard Links and Actions
    config = get_config_dynamic()
    dashboard_url = config.get('dashboard_url', 'http://localhost:5001')
    website_id = website.get('id', '')
    
    html_body_parts.append("<div class='content-section'>")
    html_body_parts.append("<h3>🔗 Quick Actions</h3>")
    html_body_parts.append("<div style='text-align: center; margin: 20px 0;'>")
    html_body_parts.append(f"<a href='{dashboard_url}/website/{website_id}' class='action-button' target='_blank'>View Website Details</a>")
    html_body_parts.append(f"<a href='{dashboard_url}/website/history/{website_id}' class='action-button' target='_blank'>View Full History</a>")
    html_body_parts.append(f"<a href='{dashboard_url}' class='action-button' target='_blank'>Main Dashboard</a>")
    html_body_parts.append("</div>")
    html_body_parts.append("</div>")
    
    # Footer
    html_body_parts.append("<div class='footer'>")
    html_body_parts.append("<p><strong>👁️ Visual Check Report</strong></p>")
    html_body_parts.append(f"<p>This is an automated visual check report for <strong>{html.escape(site_name)}</strong></p>")
    html_body_parts.append(f"<p>Report generated on {datetime.now().strftime('%Y-%m-%d at %H:%M:%S UTC')}</p>")
    html_body_parts.append(f"<p><a href='{dashboard_url}'>Visit Dashboard</a> | <a href='{dashboard_url}/settings'>Manage Settings</a></p>")
    html_body_parts.append("</div>")
    html_body_parts.append("</div></body></html>")
    
    final_html = "".join(html_body_parts)
    return send_email_alert(subject, final_html, recipient_emails=recipient_emails)

def _send_crawl_check_email(website: dict, check_results: dict, subject: str):
    """Send crawl check specific email."""
    site_name = website.get('name', 'N/A')
    site_url = website.get('url', 'N/A')
    recipient_emails = website.get('notification_emails', [])
    
    # Use the same enhanced styling as the main report
    html_style = """
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif; 
            margin: 0; padding: 0; color: #2c3e50; background-color: #f8f9fa; 
            line-height: 1.6;
        }
        .email-container { 
            max-width: 800px; margin: 20px auto; background: white; 
            border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); 
            overflow: hidden;
        }
        .header { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            padding: 30px 20px; color: white; text-align: center;
        }
        .header h1 { margin: 0; font-size: 28px; font-weight: 600; }
        .header .subtitle { margin: 8px 0 0 0; font-size: 16px; opacity: 0.9; }
        .content { padding: 30px; }
        .content-section { 
            margin-bottom: 30px; 
            padding: 20px; 
            background: #f8f9fa; 
            border-radius: 8px; 
            border-left: 4px solid #667eea;
        }
        .content-section h3 { 
            margin: 0 0 15px 0; color: #2c3e50; font-size: 20px; 
            border-bottom: 2px solid #e9ecef; padding-bottom: 10px;
        }
        .summary-table { 
            width: 100%; border-collapse: collapse; margin-top: 15px; 
            background: white; border-radius: 8px; overflow: hidden;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        }
        .summary-table th, .summary-table td { 
            padding: 12px 15px; text-align: left; border-bottom: 1px solid #e9ecef;
        }
        .summary-table th { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white; font-weight: 600; font-size: 14px;
        }
        .summary-table tr:hover { background-color: #f8f9fa; }
        .status-badge { 
            display: inline-block; padding: 6px 12px; border-radius: 20px; 
            font-size: 12px; font-weight: 600; text-transform: uppercase;
        }
        .status-success { background: #d4edda; color: #155724; }
        .status-warning { background: #fff3cd; color: #856404; }
        .status-error { background: #f8d7da; color: #721c24; }
        .status-info { background: #d1ecf1; color: #0c5460; }
        .metric-card { 
            display: inline-block; background: white; padding: 15px; 
            margin: 5px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            text-align: center; min-width: 120px;
        }
        .metric-value { font-size: 24px; font-weight: 700; color: #667eea; }
        .metric-label { font-size: 12px; color: #6c757d; text-transform: uppercase; }
        .action-button { 
            display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white; padding: 12px 24px; text-decoration: none; 
            border-radius: 6px; font-weight: 600; margin: 10px 5px;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        }
        .footer { 
            background: #2c3e50; color: #ecf0f1; padding: 30px; 
            text-align: center; font-size: 14px;
        }
        .footer a { color: #3498db; text-decoration: none; }
        @media (max-width: 600px) {
            .email-container { margin: 10px; border-radius: 8px; }
            .content { padding: 20px; }
            .header h1 { font-size: 24px; }
        }
    </style>
    """
    
    # Get crawl data
    crawl_data = check_results.get('crawler_results', {})
    broken_links = crawl_data.get('broken_links', [])
    missing_meta_tags = crawl_data.get('missing_meta_tags', [])
    crawl_stats = crawl_data.get('crawl_stats', {})
    
    html_body_parts = [
        f"<html><head>{html_style}</head><body><div class='email-container'>",
        f"<div class='header'>",
        f"<h1>🕷️ Crawl Check Report</h1>",
        f"<div class='subtitle'>{html.escape(site_name)}</div>",
        f"</div>",
        f"<div class='content'>",
        f"<div class='content-section'>",
        f"<h3>📊 Check Summary</h3>",
        f"<p><strong>Website:</strong> {html.escape(site_name)}</p>",
        f"<p><strong>URL:</strong> <a href='{html.escape(site_url)}'>{html.escape(site_url)}</a></p>",
        f"<p><strong>Check Time:</strong> {check_results.get('timestamp', 'Unknown')}</p>",
        f"</div>"
    ]
    
    # Crawl statistics
    if crawl_stats:
        html_body_parts.append("<div class='content-section'>")
        html_body_parts.append("<h3>📈 Crawl Statistics</h3>")
        
        # Crawl metrics cards
        pages_crawled = crawl_stats.get('pages_crawled', 0)
        total_links = crawl_stats.get('total_links', 0)
        total_images = crawl_stats.get('total_images', 0)
        sitemap_found = crawl_stats.get('sitemap_found', False)
        
        html_body_parts.append("<div style='display: flex; flex-wrap: wrap; margin: 20px 0;'>")
        html_body_parts.append(f"<div class='metric-card'><div class='metric-value'>{pages_crawled}</div><div class='metric-label'>Pages Crawled</div></div>")
        html_body_parts.append(f"<div class='metric-card'><div class='metric-value'>{total_links}</div><div class='metric-label'>Links Found</div></div>")
        html_body_parts.append(f"<div class='metric-card'><div class='metric-value'>{total_images}</div><div class='metric-label'>Images Found</div></div>")
        html_body_parts.append(f"<div class='metric-card'><div class='metric-value'>{'✅' if sitemap_found else '❌'}</div><div class='metric-label'>Sitemap</div></div>")
        html_body_parts.append("</div>")
        html_body_parts.append("</div>")
    
    # Broken links section
    if broken_links:
        html_body_parts.append("<div class='content-section'>")
        html_body_parts.append("<h3>🔗 Broken Links Found</h3>")
        html_body_parts.append(f"<div class='status-badge status-error'>❌ {len(broken_links)} broken links detected</div>")
        html_body_parts.append("<table class='summary-table'>")
        html_body_parts.append("<tr><th>Page</th><th>Broken Link</th><th>Status Code</th></tr>")
        
        for link in broken_links[:10]:  # Show first 10 broken links
            page_url = link.get('page_url', 'Unknown')
            broken_url = link.get('url', 'Unknown')
            status_code = link.get('status_code', 'Unknown')
            
            html_body_parts.append(f"<tr>")
            html_body_parts.append(f"<td><a href='{html.escape(page_url)}'>{html.escape(page_url)}</a></td>")
            html_body_parts.append(f"<td><a href='{html.escape(broken_url)}'>{html.escape(broken_url)}</a></td>")
            html_body_parts.append(f"<td><span class='status-badge status-error'>{status_code}</span></td>")
            html_body_parts.append(f"</tr>")
        
        if len(broken_links) > 10:
            html_body_parts.append(f"<tr><td colspan='3'><em>... and {len(broken_links) - 10} more broken links</em></td></tr>")
        
        html_body_parts.append("</table>")
        html_body_parts.append("</div>")
    else:
        html_body_parts.append("<div class='content-section'>")
        html_body_parts.append("<h3>🔗 Broken Links</h3>")
        html_body_parts.append("<div class='status-badge status-success'>✅ No broken links found!</div>")
        html_body_parts.append("</div>")
    
    # Missing meta tags section
    if missing_meta_tags:
        html_body_parts.append("<div class='content-section'>")
        html_body_parts.append("<h3>🏷️ Missing Meta Tags</h3>")
        html_body_parts.append(f"<div class='status-badge status-warning'>⚠️ {len(missing_meta_tags)} pages with missing meta tags</div>")
        html_body_parts.append("<table class='summary-table'>")
        html_body_parts.append("<tr><th>Page</th><th>Missing Tag</th><th>Tag Type</th></tr>")
        
        for tag in missing_meta_tags[:10]:  # Show first 10 missing tags
            page_url = tag.get('url', 'Unknown')
            tag_name = tag.get('tag_name', 'Unknown')
            tag_type = tag.get('tag_type', 'Unknown')
            
            html_body_parts.append(f"<tr>")
            html_body_parts.append(f"<td><a href='{html.escape(page_url)}'>{html.escape(page_url)}</a></td>")
            html_body_parts.append(f"<td>{html.escape(tag_name)}</td>")
            html_body_parts.append(f"<td>{html.escape(tag_type)}</td>")
            html_body_parts.append(f"</tr>")
        
        if len(missing_meta_tags) > 10:
            html_body_parts.append(f"<tr><td colspan='3'><em>... and {len(missing_meta_tags) - 10} more missing meta tags</em></td></tr>")
        
        html_body_parts.append("</table>")
        html_body_parts.append("</div>")
    else:
        html_body_parts.append("<div class='content-section'>")
        html_body_parts.append("<h3>🏷️ Missing Meta Tags</h3>")
        html_body_parts.append("<div class='status-badge status-success'>✅ No missing meta tags found!</div>")
        html_body_parts.append("</div>")
    
    # Dashboard Links and Actions
    config = get_config_dynamic()
    dashboard_url = config.get('dashboard_url', 'http://localhost:5001')
    website_id = website.get('id', '')
    
    html_body_parts.append("<div class='content-section'>")
    html_body_parts.append("<h3>🔗 Quick Actions</h3>")
    html_body_parts.append("<div style='text-align: center; margin: 20px 0;'>")
    html_body_parts.append(f"<a href='{dashboard_url}/website/{website_id}' class='action-button' target='_blank'>View Website Details</a>")
    html_body_parts.append(f"<a href='{dashboard_url}/website/history/{website_id}' class='action-button' target='_blank'>View Full History</a>")
    html_body_parts.append(f"<a href='{dashboard_url}' class='action-button' target='_blank'>Main Dashboard</a>")
    html_body_parts.append("</div>")
    html_body_parts.append("</div>")
    
    # Footer
    html_body_parts.append("<div class='footer'>")
    html_body_parts.append("<p><strong>🕷️ Crawl Check Report</strong></p>")
    html_body_parts.append(f"<p>This is an automated crawl check report for <strong>{html.escape(site_name)}</strong></p>")
    html_body_parts.append(f"<p>Report generated on {datetime.now().strftime('%Y-%m-%d at %H:%M:%S UTC')}</p>")
    html_body_parts.append(f"<p><a href='{dashboard_url}'>Visit Dashboard</a> | <a href='{dashboard_url}/settings'>Manage Settings</a></p>")
    html_body_parts.append("</div>")
    html_body_parts.append("</div></body></html>")
    
    final_html = "".join(html_body_parts)
    return send_email_alert(subject, final_html, recipient_emails=recipient_emails)

def _send_blur_check_email(website: dict, check_results: dict, subject: str):
    """Send blur check specific email."""
    site_name = website.get('name', 'N/A')
    site_url = website.get('url', 'N/A')
    recipient_emails = website.get('notification_emails', [])
    
    # Use the same enhanced styling as the main report
    html_style = """
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif; 
            margin: 0; padding: 0; color: #2c3e50; background-color: #f8f9fa; 
            line-height: 1.6;
        }
        .email-container { 
            max-width: 800px; margin: 20px auto; background: white; 
            border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); 
            overflow: hidden;
        }
        .header { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            padding: 30px 20px; color: white; text-align: center;
        }
        .header h1 { margin: 0; font-size: 28px; font-weight: 600; }
        .header .subtitle { margin: 8px 0 0 0; font-size: 16px; opacity: 0.9; }
        .content { padding: 30px; }
        .content-section { 
            margin-bottom: 30px; 
            padding: 20px; 
            background: #f8f9fa; 
            border-radius: 8px; 
            border-left: 4px solid #667eea;
        }
        .content-section h3 { 
            margin: 0 0 15px 0; color: #2c3e50; font-size: 20px; 
            border-bottom: 2px solid #e9ecef; padding-bottom: 10px;
        }
        .summary-table { 
            width: 100%; border-collapse: collapse; margin-top: 15px; 
            background: white; border-radius: 8px; overflow: hidden;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        }
        .summary-table th, .summary-table td { 
            padding: 12px 15px; text-align: left; border-bottom: 1px solid #e9ecef;
        }
        .summary-table th { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white; font-weight: 600; font-size: 14px;
        }
        .summary-table tr:hover { background-color: #f8f9fa; }
        .status-badge { 
            display: inline-block; padding: 6px 12px; border-radius: 20px; 
            font-size: 12px; font-weight: 600; text-transform: uppercase;
        }
        .status-success { background: #d4edda; color: #155724; }
        .status-warning { background: #fff3cd; color: #856404; }
        .status-error { background: #f8d7da; color: #721c24; }
        .status-info { background: #d1ecf1; color: #0c5460; }
        .metric-card { 
            display: inline-block; background: white; padding: 15px; 
            margin: 5px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            text-align: center; min-width: 120px;
        }
        .metric-value { font-size: 24px; font-weight: 700; color: #667eea; }
        .metric-label { font-size: 12px; color: #6c757d; text-transform: uppercase; }
        .action-button { 
            display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white; padding: 12px 24px; text-decoration: none; 
            border-radius: 6px; font-weight: 600; margin: 10px 5px;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        }
        .footer { 
            background: #2c3e50; color: #ecf0f1; padding: 30px; 
            text-align: center; font-size: 14px;
        }
        .footer a { color: #3498db; text-decoration: none; }
        @media (max-width: 600px) {
            .email-container { margin: 10px; border-radius: 8px; }
            .content { padding: 20px; }
            .header h1 { font-size: 24px; }
        }
    </style>
    """
    
    # Get blur check data
    blur_data = check_results.get('blur_check', {})
    blur_results = blur_data.get('blur_results', [])
    blur_stats = blur_data.get('blur_stats', {})
    
    html_body_parts = [
        f"<html><head>{html_style}</head><body><div class='email-container'>",
        f"<div class='header'>",
        f"<h1>🔍 Blur Detection Report</h1>",
        f"<div class='subtitle'>{html.escape(site_name)}</div>",
        f"</div>",
        f"<div class='content'>",
        f"<div class='content-section'>",
        f"<h3>📊 Check Summary</h3>",
        f"<p><strong>Website:</strong> {html.escape(site_name)}</p>",
        f"<p><strong>URL:</strong> <a href='{html.escape(site_url)}'>{html.escape(site_url)}</a></p>",
        f"<p><strong>Check Time:</strong> {check_results.get('timestamp', 'Unknown')}</p>",
        f"</div>"
    ]
    
    # Blur detection summary
    if blur_stats:
        html_body_parts.append("<div class='content-section'>")
        html_body_parts.append("<h3>🔍 Blur Detection Summary</h3>")
        
        # Blur metrics cards
        pages_checked = blur_stats.get('pages_checked', 0)
        images_analyzed = blur_stats.get('images_analyzed', 0)
        blurred_images = blur_stats.get('blurred_images', 0)
        avg_blur_score = blur_stats.get('average_blur_score', 0)
        
        html_body_parts.append("<div style='display: flex; flex-wrap: wrap; margin: 20px 0;'>")
        html_body_parts.append(f"<div class='metric-card'><div class='metric-value'>{pages_checked}</div><div class='metric-label'>Pages Checked</div></div>")
        html_body_parts.append(f"<div class='metric-card'><div class='metric-value'>{images_analyzed}</div><div class='metric-label'>Images Analyzed</div></div>")
        html_body_parts.append(f"<div class='metric-card'><div class='metric-value'>{blurred_images}</div><div class='metric-label'>Blurred Images</div></div>")
        html_body_parts.append(f"<div class='metric-card'><div class='metric-value'>{avg_blur_score:.2f}</div><div class='metric-label'>Avg Blur Score</div></div>")
        html_body_parts.append("</div>")
        html_body_parts.append("</div>")
    
    # Blurred images details
    if blur_results:
        html_body_parts.append("<div class='content-section'>")
        html_body_parts.append("<h3>🖼️ Blurred Images Found</h3>")
        html_body_parts.append(f"<div class='status-badge status-warning'>⚠️ {len(blur_results)} blurred images detected</div>")
        html_body_parts.append("<table class='summary-table'>")
        html_body_parts.append("<tr><th>Page</th><th>Image</th><th>Blur Score</th><th>Status</th></tr>")
        
        for result in blur_results[:10]:  # Show first 10 blurred images
            page_url = result.get('page_url', 'Unknown')
            image_url = result.get('image_url', 'Unknown')
            blur_score = result.get('blur_score', 0)
            is_blurred = result.get('is_blurred', False)
            
            status_class = "status-error" if is_blurred else "status-success"
            status_text = "Blurred" if is_blurred else "Clear"
            
            html_body_parts.append(f"<tr>")
            html_body_parts.append(f"<td><a href='{html.escape(page_url)}'>{html.escape(page_url)}</a></td>")
            html_body_parts.append(f"<td><a href='{html.escape(image_url)}'>{html.escape(image_url)}</a></td>")
            html_body_parts.append(f"<td>{blur_score:.2f}</td>")
            html_body_parts.append(f"<td><span class='status-badge {status_class}'>{status_text}</span></td>")
            html_body_parts.append(f"</tr>")
        
        if len(blur_results) > 10:
            html_body_parts.append(f"<tr><td colspan='4'><em>... and {len(blur_results) - 10} more images</em></td></tr>")
        
        html_body_parts.append("</table>")
        html_body_parts.append("</div>")
    else:
        html_body_parts.append("<div class='content-section'>")
        html_body_parts.append("<h3>🖼️ Blur Detection Results</h3>")
        html_body_parts.append("<div class='status-badge status-success'>✅ No blurred images found!</div>")
        html_body_parts.append("</div>")
    
    # Dashboard Links and Actions
    config = get_config_dynamic()
    dashboard_url = config.get('dashboard_url', 'http://localhost:5001')
    website_id = website.get('id', '')
    
    html_body_parts.append("<div class='content-section'>")
    html_body_parts.append("<h3>🔗 Quick Actions</h3>")
    html_body_parts.append("<div style='text-align: center; margin: 20px 0;'>")
    html_body_parts.append(f"<a href='{dashboard_url}/website/{website_id}' class='action-button' target='_blank'>View Website Details</a>")
    html_body_parts.append(f"<a href='{dashboard_url}/website/history/{website_id}' class='action-button' target='_blank'>View Full History</a>")
    html_body_parts.append(f"<a href='{dashboard_url}' class='action-button' target='_blank'>Main Dashboard</a>")
    html_body_parts.append("</div>")
    html_body_parts.append("</div>")
    
    # Footer
    html_body_parts.append("<div class='footer'>")
    html_body_parts.append("<p><strong>🔍 Blur Detection Report</strong></p>")
    html_body_parts.append(f"<p>This is an automated blur detection report for <strong>{html.escape(site_name)}</strong></p>")
    html_body_parts.append(f"<p>Report generated on {datetime.now().strftime('%Y-%m-%d at %H:%M:%S UTC')}</p>")
    html_body_parts.append(f"<p><a href='{dashboard_url}'>Visit Dashboard</a> | <a href='{dashboard_url}/settings'>Manage Settings</a></p>")
    html_body_parts.append("</div>")
    html_body_parts.append("</div></body></html>")
    
    final_html = "".join(html_body_parts)
    return send_email_alert(subject, final_html, recipient_emails=recipient_emails)

def _send_performance_check_email(website: dict, check_results: dict, subject: str):
    """Send performance check specific email."""
    # Extract performance data from check_results
    performance_data = check_results.get('performance_check', {})
    if not performance_data:
        # Fallback: use the entire check_results if performance_check key doesn't exist
        performance_data = check_results
    
    # Use the existing send_performance_email function
    return send_performance_email(website, performance_data)

def send_performance_email(website: dict, performance_data: dict):
    """
    Sends a dedicated performance email notification.
    This function is called when performance checks are run independently.
    """
    site_name = website.get('name', 'N/A')
    site_url = website.get('url', 'N/A')
    recipient_emails = website.get('notification_emails', [])
    
    subject = f"Performance Report for {site_name}"
    
    # Use the same enhanced styling as the main report
    html_style = """
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif; 
            margin: 0; padding: 0; color: #2c3e50; background-color: #f8f9fa; 
            line-height: 1.6;
        }
        .email-container { 
            max-width: 800px; margin: 20px auto; background: white; 
            border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); 
            overflow: hidden;
        }
        .header { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            padding: 30px 20px; color: white; text-align: center;
        }
        .header h1 { margin: 0; font-size: 28px; font-weight: 600; }
        .header .subtitle { margin: 8px 0 0 0; font-size: 16px; opacity: 0.9; }
        .content { padding: 30px; }
        .content-section { 
            margin-bottom: 30px; 
            padding: 20px; 
            background: #f8f9fa; 
            border-radius: 8px; 
            border-left: 4px solid #667eea;
        }
        .content-section h3 { 
            margin: 0 0 15px 0; color: #2c3e50; font-size: 20px; 
            border-bottom: 2px solid #e9ecef; padding-bottom: 10px;
        }
        .summary-table { 
            width: 100%; border-collapse: collapse; margin-top: 15px; 
            background: white; border-radius: 8px; overflow: hidden;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        }
        .summary-table th, .summary-table td { 
            padding: 12px 15px; text-align: left; border-bottom: 1px solid #e9ecef;
        }
        .summary-table th { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white; font-weight: 600; font-size: 14px;
        }
        .summary-table tr:hover { background-color: #f8f9fa; }
        .status-badge { 
            display: inline-block; padding: 6px 12px; border-radius: 20px; 
            font-size: 12px; font-weight: 600; text-transform: uppercase;
        }
        .status-success { background: #d4edda; color: #155724; }
        .status-warning { background: #fff3cd; color: #856404; }
        .status-error { background: #f8d7da; color: #721c24; }
        .status-info { background: #d1ecf1; color: #0c5460; }
        .metric-card { 
            display: inline-block; background: white; padding: 15px; 
            margin: 5px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            text-align: center; min-width: 120px;
        }
        .metric-value { font-size: 24px; font-weight: 700; color: #667eea; }
        .metric-label { font-size: 12px; color: #6c757d; text-transform: uppercase; }
        .performance-badge { 
            display: inline-block; padding: 8px 16px; border-radius: 20px; 
            font-size: 14px; font-weight: 600; text-transform: uppercase;
        }
        .excellent { background: #d4edda; color: #155724; }
        .good { background: #fff3cd; color: #856404; }
        .poor { background: #f8d7da; color: #721c24; }
        .action-button { 
            display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white; padding: 12px 24px; text-decoration: none; 
            border-radius: 6px; font-weight: 600; margin: 10px 5px;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        }
        .footer { 
            background: #2c3e50; color: #ecf0f1; padding: 30px; 
            text-align: center; font-size: 14px;
        }
        .footer a { color: #3498db; text-decoration: none; }
        .highlight-box { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white; padding: 20px; border-radius: 8px; margin: 20px 0;
        }
        .recommendations { 
            background: #fff3cd; border: 1px solid #ffeaa7; 
            padding: 20px; border-radius: 8px; margin: 20px 0;
        }
        .recommendations h4 { color: #856404; margin-top: 0; }
        @media (max-width: 600px) {
            .email-container { margin: 10px; border-radius: 8px; }
            .content { padding: 20px; }
            .header h1 { font-size: 24px; }
        }
    </style>
    """
    
    performance_summary = performance_data.get('performance_check_summary', {})
    
    html_body_parts = [
        f"<html><head>{html_style}</head><body><div class='email-container'>",
        f"<div class='header'>",
        f"<h1>⚡ Performance Report</h1>",
        f"<div class='subtitle'>{html.escape(site_name)}</div>",
        f"</div>",
        f"<div class='content'>",
        f"<div class='content-section'>",
        f"<h3>📊 Performance Analysis</h3>",
        f"<p>Performance analysis completed for <strong><a href='{html.escape(site_url)}'>{html.escape(site_url)}</a></strong></p>",
        f"<p><strong>Analysis Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>",
        f"</div>"
    ]
    
    if performance_summary:
        pages_analyzed = performance_summary.get('pages_analyzed', 0)
        avg_score = performance_summary.get('average_performance_score', 0)
        
        # Validate performance data
        if pages_analyzed == 0 or avg_score == 0:
            html_body_parts.append("<div class='content-section'>")
            html_body_parts.append("<h3>⚡ Performance Analysis</h3>")
            html_body_parts.append("<div class='status-badge status-warning'>⚠️ Performance data incomplete</div>")
            html_body_parts.append("<p><em>This could be due to:</em></p>")
            html_body_parts.append("<ul>")
            html_body_parts.append("<li>No pages were successfully analyzed</li>")
            html_body_parts.append("<li>Performance API returned no data</li>")
            html_body_parts.append("<li>Network connectivity issues during analysis</li>")
            html_body_parts.append("</ul>")
            html_body_parts.append("</div>")
        else:
            html_body_parts.append("<div class='content-section'>")
            html_body_parts.append("<h3>⚡ Performance Overview</h3>")
            
            # Performance metrics cards
            html_body_parts.append("<div style='display: flex; flex-wrap: wrap; margin: 20px 0;'>")
            html_body_parts.append(f"<div class='metric-card'><div class='metric-value'>{pages_analyzed}</div><div class='metric-label'>Pages Analyzed</div></div>")
            html_body_parts.append(f"<div class='metric-card'><div class='metric-value'>{avg_score:.1f}</div><div class='metric-label'>Avg Score</div></div>")
            html_body_parts.append("</div>")
            
            # Performance grade with badge
            if avg_score >= 90:
                grade_class = "excellent"
                grade_text = "Excellent"
                grade_emoji = "🟢"
            elif avg_score >= 70:
                grade_class = "good"
                grade_text = "Good"
                grade_emoji = "🟡"
            elif avg_score >= 50:
                grade_class = "poor"
                grade_text = "Needs Improvement"
                grade_emoji = "🟠"
            else:
                grade_class = "poor"
                grade_text = "Poor"
                grade_emoji = "🔴"
            
            html_body_parts.append(f"<div class='highlight-box'>")
            html_body_parts.append(f"<h4>{grade_emoji} Overall Performance Grade: {grade_text}</h4>")
            html_body_parts.append(f"<p>Average Score: <strong>{avg_score:.1f}/100</strong></p>")
            html_body_parts.append("</div>")
            html_body_parts.append("</div>")
        
            # Detailed metrics
            html_body_parts.append("<div class='content-section'>")
            html_body_parts.append("<h3>📊 Detailed Performance Metrics</h3>")
            html_body_parts.append("<table class='summary-table'>")
            html_body_parts.append("<tr><th>Metric</th><th>Mobile</th><th>Desktop</th><th>Status</th></tr>")
        
        mobile_avg = performance_summary.get('mobile_average', {})
        desktop_avg = performance_summary.get('desktop_average', {})
        
            # Validate mobile and desktop data
            if not mobile_avg or not desktop_avg:
                html_body_parts.append("<tr><td colspan='4'><em>Mobile/Desktop data not available</em></td></tr>")
            else:
        metrics = [
            ('Performance Score', 'performance_score', 'performance_score'),
            ('First Contentful Paint (s)', 'fcp_score', 'fcp_score'),
            ('Largest Contentful Paint (s)', 'lcp_score', 'lcp_score'),
            ('Cumulative Layout Shift', 'cls_score', 'cls_score'),
            ('Speed Index (s)', 'speed_index', 'speed_index'),
            ('Total Blocking Time (ms)', 'tbt_score', 'tbt_score')
        ]
        
        for metric_name, mobile_key, desktop_key in metrics:
            mobile_val = mobile_avg.get(mobile_key, 0)
            desktop_val = desktop_avg.get(desktop_key, 0)
            
            # Determine status
            if metric_name == 'Performance Score':
                mobile_status = "🟢 Good" if mobile_val >= 70 else "🔴 Poor" if mobile_val < 50 else "🟡 Fair"
                desktop_status = "🟢 Good" if desktop_val >= 70 else "🔴 Poor" if desktop_val < 50 else "🟡 Fair"
            elif metric_name in ['First Contentful Paint (s)', 'Largest Contentful Paint (s)', 'Speed Index (s)', 'Total Blocking Time (ms)']:
                mobile_status = "🟢 Good" if mobile_val <= 2.5 else "🔴 Poor" if mobile_val > 4 else "🟡 Fair"
                desktop_status = "🟢 Good" if desktop_val <= 2.5 else "🔴 Poor" if desktop_val > 4 else "🟡 Fair"
            else:  # CLS
                mobile_status = "🟢 Good" if mobile_val <= 0.1 else "🔴 Poor" if mobile_val > 0.25 else "🟡 Fair"
                desktop_status = "🟢 Good" if desktop_val <= 0.1 else "🔴 Poor" if desktop_val > 0.25 else "🟡 Fair"
            
            html_body_parts.append(f"<tr>")
            html_body_parts.append(f"<td><strong>{metric_name}</strong></td>")
            html_body_parts.append(f"<td>{mobile_val:.2f}</td>")
            html_body_parts.append(f"<td>{desktop_val:.2f}</td>")
            html_body_parts.append(f"<td>{mobile_status} / {desktop_status}</td>")
            html_body_parts.append(f"</tr>")
        
        html_body_parts.append("</table>")
        html_body_parts.append("</div>")
        
        # Performance recommendations
        if avg_score < 70:
            html_body_parts.append("<div class='content-section'><h3>Performance Recommendations</h3>")
            html_body_parts.append("<ul>")
            if mobile_avg.get('fcp_score', 0) > 2.5:
                html_body_parts.append("<li><strong>Optimize First Contentful Paint:</strong> Reduce server response time and eliminate render-blocking resources</li>")
            if mobile_avg.get('lcp_score', 0) > 2.5:
                html_body_parts.append("<li><strong>Improve Largest Contentful Paint:</strong> Optimize images and reduce resource load times</li>")
            if mobile_avg.get('cls_score', 0) > 0.1:
                html_body_parts.append("<li><strong>Reduce Cumulative Layout Shift:</strong> Ensure images and ads have size attributes</li>")
            if mobile_avg.get('tbt_score', 0) > 200:
                html_body_parts.append("<li><strong>Minimize Total Blocking Time:</strong> Reduce JavaScript execution time and implement code splitting</li>")
            html_body_parts.append("</ul>")
            html_body_parts.append("</div>")
    else:
        html_body_parts.append("<div class='content-section'><h3>Performance Analysis</h3>")
        html_body_parts.append("<p class='status-error'><strong>❌ Performance data not available</strong></p>")
        html_body_parts.append("<p><em>This could be due to:</em></p>")
        html_body_parts.append("<ul>")
        html_body_parts.append("<li>Performance check was not enabled for this website</li>")
        html_body_parts.append("<li>Performance API is not configured or accessible</li>")
        html_body_parts.append("<li>Error occurred during performance analysis</li>")
        html_body_parts.append("<li>No pages were available for performance testing</li>")
        html_body_parts.append("</ul>")
        html_body_parts.append("</div>")
    
    # Add dashboard link
    config = get_config_dynamic()
    dashboard_url = config.get('dashboard_url', 'http://localhost:5001')
    website_id = website.get('id', '')
    
    html_body_parts.append("<div class='content-section'><h3>View Detailed Results</h3>")
    html_body_parts.append(f"<p><a href='{dashboard_url}/website/{website_id}/performance' target='_blank' style='background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;'>View Performance Dashboard</a></p>")
    html_body_parts.append(f"<p><a href='{dashboard_url}/website/history/{website_id}' target='_blank' style='color: #007bff;'>View Full History</a> | <a href='{dashboard_url}' target='_blank' style='color: #007bff;'>Main Dashboard</a></p>")
    html_body_parts.append("</div>")
    
    # Footer
    html_body_parts.append(f"<div class='footer'><p>This is an automated performance report from the Website Monitoring System.</p></div>")
    html_body_parts.append("</div></body></html>")
    
    final_html = "".join(html_body_parts)
    
    # Send the email
    return send_email_alert(subject, final_html, recipient_emails=recipient_emails)

def _send_baseline_check_email(website: dict, check_results: dict, subject: str):
    """Send baseline check specific email."""
    site_name = website.get('name', 'N/A')
    site_url = website.get('url', 'N/A')
    recipient_emails = website.get('notification_emails', [])
    
    html_style = """
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; color: #333; }
        .container { max-width: 800px; margin: auto; border: 1px solid #ddd; padding: 20px; border-radius: 5px; }
        .header { background-color: #f8f9fa; padding: 10px 20px; border-bottom: 1px solid #ddd; }
        .header h2 { margin: 0; color: #0056b3; }
        .content-section { margin-top: 20px; }
        .content-section h3 { border-bottom: 2px solid #eee; padding-bottom: 5px; color: #333; }
        .summary-table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        .summary-table th, .summary-table td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        .summary-table th { background-color: #f2f2f2; }
        .status-good { color: #28a745; font-weight: bold; }
        .status-warning { color: #ffc107; font-weight: bold; }
        .status-error { color: #dc3545; font-weight: bold; }
        .footer { margin-top: 20px; font-size: 0.8em; color: #777; text-align: center; }
        a { color: #0056b3; }
    </style>
    """
    
    # Get baseline data
    visual_data = check_results.get('visual_check', {})
    baselines = visual_data.get('baselines', [])
    snapshots = visual_data.get('snapshots', [])
    
    html_body_parts = [
        f"<html><head>{html_style}</head><body>",
        f"<div class='container'>",
        f"<div class='header'><h2>Baseline Creation Report</h2></div>",
        f"<div class='content-section'>",
        f"<h3>Website Information</h3>",
        f"<p><strong>Website:</strong> {site_name}</p>",
        f"<p><strong>URL:</strong> <a href='{site_url}'>{site_url}</a></p>",
        f"<p><strong>Check Time:</strong> {check_results.get('timestamp', 'Unknown')}</p>",
        f"</div>"
    ]
    
    # Baseline creation summary
    if baselines:
        html_body_parts.append("<div class='content-section'><h3>Baseline Creation Summary</h3>")
        html_body_parts.append(f"<p class='status-good'><strong>✅ {len(baselines)} baseline(s) created successfully!</strong></p>")
        
        # Show pages that got baselines
        html_body_parts.append("<h4>Pages with New Baselines</h4>")
        html_body_parts.append("<table class='summary-table'>")
        html_body_parts.append("<tr><th>Page</th><th>Baseline Status</th><th>Created At</th></tr>")
        
        for baseline in baselines:
            page_url = baseline.get('url', 'Unknown')
            page_title = baseline.get('title', 'Unknown')
            created_at = baseline.get('created_at', 'Unknown')
            
            html_body_parts.append(f"<tr>")
            html_body_parts.append(f"<td><a href='{page_url}'>{page_title}</a></td>")
            html_body_parts.append(f"<td class='status-good'>Baseline Created</td>")
            html_body_parts.append(f"<td>{created_at}</td>")
            html_body_parts.append(f"</tr>")
        
        html_body_parts.append("</table>")
        html_body_parts.append("</div>")
        
        # Show pages that were excluded
        excluded_pages = [s for s in snapshots if not any(b.get('url') == s.get('url') for b in baselines)]
        if excluded_pages:
            html_body_parts.append("<div class='content-section'><h3>Excluded Pages</h3>")
            html_body_parts.append(f"<p><strong>{len(excluded_pages)} page(s) were excluded from baseline creation</strong></p>")
            html_body_parts.append("<p><em>These pages contain keywords that are excluded from visual checks (e.g., 'products', 'blogs', etc.)</em></p>")
            html_body_parts.append("<ul>")
            for page in excluded_pages[:5]:  # Show first 5 excluded pages
                page_url = page.get('url', 'Unknown')
                page_title = page.get('title', 'Unknown')
                html_body_parts.append(f"<li><a href='{page_url}'>{page_title}</a></li>")
            if len(excluded_pages) > 5:
                html_body_parts.append(f"<li><em>... and {len(excluded_pages) - 5} more pages</em></li>")
            html_body_parts.append("</ul>")
            html_body_parts.append("</div>")
    else:
        html_body_parts.append("<div class='content-section'><h3>Baseline Creation Summary</h3>")
        html_body_parts.append("<p class='status-warning'><strong>⚠️ No baselines were created</strong></p>")
        html_body_parts.append("<p><em>This could be due to:</em></p>")
        html_body_parts.append("<ul>")
        html_body_parts.append("<li>All pages were excluded due to exclude keywords</li>")
        html_body_parts.append("<li>No pages were successfully crawled</li>")
        html_body_parts.append("<li>Visual check was not enabled for this website</li>")
        html_body_parts.append("</ul>")
        html_body_parts.append("</div>")
    
    # Footer
    html_body_parts.append(f"<div class='footer'><p>This is an automated baseline creation report from the Website Monitoring System.</p></div>")
    html_body_parts.append("</div></body></html>")
    
    final_html = "".join(html_body_parts)
    return send_email_alert(subject, final_html, recipient_emails=recipient_emails)

def _send_full_check_email(website: dict, check_results: dict, subject: str):
    """Send full check specific email with all check types."""
    site_name = website.get('name', 'N/A')
    site_url = website.get('url', 'N/A')
    recipient_emails = website.get('notification_emails', [])
    
    html_style = """
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; color: #333; }
        .container { max-width: 800px; margin: auto; border: 1px solid #ddd; padding: 20px; border-radius: 5px; }
        .header { background-color: #f8f9fa; padding: 10px 20px; border-bottom: 1px solid #ddd; }
        .header h2 { margin: 0; color: #0056b3; }
        .content-section { margin-top: 20px; }
        .content-section h3 { border-bottom: 2px solid #eee; padding-bottom: 5px; color: #333; }
        .summary-table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        .summary-table th, .summary-table td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        .summary-table th { background-color: #f2f2f2; }
        .status-good { color: #28a745; font-weight: bold; }
        .status-warning { color: #ffc107; font-weight: bold; }
        .status-error { color: #dc3545; font-weight: bold; }
        .footer { margin-top: 20px; font-size: 0.8em; color: #777; text-align: center; }
        a { color: #0056b3; }
    </style>
    """
    
    html_body_parts = [html_style]
    html_body_parts.append(f"<div class='container'><div class='header'><h2>{subject}</h2></div>")
    html_body_parts.append(f"<div class='content-section'><h3>Website Information</h3>")
    html_body_parts.append(f"<p><strong>Website:</strong> {site_name}</p>")
    html_body_parts.append(f"<p><strong>URL:</strong> <a href='{site_url}'>{site_url}</a></p>")
    html_body_parts.append(f"<p><strong>Check Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>")
    html_body_parts.append("</div>")
    
    # Add all check results
    if 'crawl_check' in check_results:
        html_body_parts.append("<div class='content-section'><h3>Crawl Check Results</h3>")
        crawl_data = check_results['crawl_check']
        html_body_parts.append(f"<p>Pages crawled: {crawl_data.get('total_pages', 0)}</p>")
        html_body_parts.append(f"<p>Broken links found: {crawl_data.get('broken_links_count', 0)}</p>")
        html_body_parts.append("</div>")
    
    if 'visual_check' in check_results:
        html_body_parts.append("<div class='content-section'><h3>Visual Check Results</h3>")
        visual_data = check_results['visual_check']
        html_body_parts.append(f"<p>Visual comparison completed: {visual_data.get('comparison_completed', False)}</p>")
        html_body_parts.append("</div>")
    
    if 'performance_check' in check_results:
        html_body_parts.append("<div class='content-section'><h3>Performance Check Results</h3>")
        perf_data = check_results['performance_check']
        html_body_parts.append(f"<p>Performance analysis completed: {perf_data.get('analysis_completed', False)}</p>")
        html_body_parts.append("</div>")
    
    if 'blur_check' in check_results:
        html_body_parts.append("<div class='content-section'><h3>Blur Detection Results</h3>")
        blur_data = check_results['blur_check']
        html_body_parts.append(f"<p>Blur detection completed: {blur_data.get('detection_completed', False)}</p>")
        html_body_parts.append("</div>")
    
    # Footer
    html_body_parts.append(f"<div class='footer'><p>This is an automated full check report from the Website Monitoring System.</p></div>")
    html_body_parts.append("</div></body></html>")
    
    final_html = "".join(html_body_parts)
    return send_email_alert(subject, final_html, recipient_emails=recipient_emails) 