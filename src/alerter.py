import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage # Import for embedding images
import html # Added for html.escape
import os # For path handling
from src.config_loader import get_config
from src.logger_setup import setup_logging

logger = setup_logging()
config = get_config()

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
    
    monitoring_mode = website.get('monitoring_mode', 'full') # Default to 'full'

    subject = f"Monitoring Report for {site_name}"
    if is_change_report:
        subject = f"Change Detected on {site_name}"

    # --- Build HTML Body ---
    # Basic styling for the email
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
        .image-container { text-align: center; margin-top: 15px; }
        .image-container img { max-width: 100%; border: 1px solid #ccc; }
        .footer { margin-top: 20px; font-size: 0.8em; color: #777; text-align: center; }
        a { color: #0056b3; }
    </style>
    """
    
    html_body_parts = [
        f"<html><head>{html_style}</head><body><div class='container'>",
        f"<div class='header'><h2>Monitoring Report: {html.escape(site_name)}</h2></div>",
        f"<div class='content-section'><p>A check on <strong><a href='{html.escape(site_url)}'>{html.escape(site_url)}</a></strong> has completed.</p></div>"
    ]
    
    attachments = []

    # If it's a change report, add the reasons.
    if is_change_report:
        reasons = check_results.get('reasons', [])
        html_body_parts.append("<div class='content-section'><h3>Summary of Changes Detected</h3><ul>")
        for reason in reasons:
            html_body_parts.append(f"<li>{html.escape(reason)}</li>")
        html_body_parts.append("</ul></div>")

    # --- Section 1: Visual Change Report ---
    if has_visual_change and monitoring_mode in ['full', 'visual']:
        diff_image_path = check_results.get('visual_diff_image_path')
        page_url = check_results.get('url', site_url) # URL of the specific page with changes
        
        html_body_parts.append("<div class='content-section'><h3>Visual Comparison</h3>")
        
        if diff_image_path and os.path.exists(diff_image_path):
            html_body_parts.append(f"<p>A visual change was detected on the page: <a href='{html.escape(page_url)}'>{html.escape(page_url)}</a></p>")
            html_body_parts.append("<div class='image-container'>")
            html_body_parts.append("<p><strong>Comparison: Before vs. After</strong></p>")
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
                html_body_parts.append("<p><em>(Error attaching the visual difference image.)</em></p>")
        else:
             html_body_parts.append("<p><em>(The visual difference image was not found at the expected path.)</em></p>")
        html_body_parts.append("</div>")

    # --- Section 2: Crawler Health Report ---
    if has_crawl_issues and monitoring_mode in ['full', 'crawl']:
        if not is_change_report: # Avoid double subjects
            subject = f"Crawler Issues Found on {site_name}"
        
        crawler_results = check_results.get('crawler_results', {})
        broken_links = crawler_results.get('broken_links', [])
        
        html_body_parts.append("<div class='content-section'><h3>Crawler Health Report</h3>")
        if not broken_links:
            html_body_parts.append("<p style='color: green;'><strong>No broken links found.</strong></p>")
        else:
            subject = f"Action Required: Broken Links Found on {site_name}"
            html_body_parts.append(f"<p style='color: red;'><strong>Found {len(broken_links)} broken link(s):</strong></p>")
            html_body_parts.append("<table class='summary-table'><tr><th>Broken URL</th><th>Status</th><th>Found On</th></tr>")
            for link in broken_links[:15]: # Limit for email brevity
                link_url = html.escape(link.get('url', 'N/A'))
                status = html.escape(str(link.get('status_code', 'N/A')))
                source = html.escape(link.get('source_page', 'N/A'))
                html_body_parts.append(f"<tr><td><a href='{link_url}'>{link_url}</a></td><td>{status}</td><td><a href='{source}'>{source}</a></td></tr>")
            html_body_parts.append("</table>")
            if len(broken_links) > 15:
                html_body_parts.append("<p><em>...and more. Please check the dashboard for a full list.</em></p>")
        
        # Add summary stats
        total_pages = crawler_results.get('total_pages_crawled', 'N/A')
        html_body_parts.append("<h4>Crawl Summary</h4>")
        html_body_parts.append(f"<p>Total pages crawled: <strong>{total_pages}</strong></p>")
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
    
    # --- Footer ---
    html_body_parts.append(f"<div class='footer'><p>This is an automated alert from the Website Monitoring System.</p></div>")
    html_body_parts.append("</div></body></html>")
    
    final_html = "".join(html_body_parts)

    # Use the existing send_email_alert function to handle SMTP logic
    return send_email_alert(subject, final_html, attachments=attachments, recipient_emails=recipient_emails)

def send_email_alert(subject: str, body_html: str, body_text: str = None, recipient_emails: list = None, attachments: list = None):
    """
    Sends an email alert using SMTP settings from the configuration.
    (Now with attachment support)
    """
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
        'use_tls': config.get('smtp_use_tls', True)
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
        with smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port']) as server:
            if email_config.get('use_tls', True):
                server.starttls()
            if email_config['smtp_username'] and email_config['smtp_password']:
                server.login(email_config['smtp_username'], email_config['smtp_password'])
            server.sendmail(email_config['from'], target_recipients, msg.as_string())
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
        html_body_parts.append(f"<p><a href=\"http://localhost:5000/website/{check_record.get('site_id')}/crawler\">View Detailed Crawler Results</a></p>")
        text_body_parts.append(f"\nView Detailed Crawler Results: http://localhost:5000/website/{check_record.get('site_id')}/crawler")
    
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