import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import html # Added for html.escape
from src.config_loader import get_config
from src.logger_setup import setup_logging

logger = setup_logging()
config = get_config()

def send_email_alert(subject: str, body_html: str, body_text: str = None, recipient_emails: list = None):
    """
    Sends an email alert using SMTP settings from the configuration.

    Args:
        subject (str): The subject of the email.
        body_html (str): The HTML content of the email.
        body_text (str, optional): Plain text version of the email. If None, HTML body is used for text part.
        recipient_emails (list, optional): A list of email addresses to send the alert to.
                                        If None or empty, uses default from config.
    """
    smtp_sender = config.get('notification_email_from') # Use the correct config key
    default_recipients_str = config.get('notification_email_to', config.get('default_notification_email'))
    
    target_recipients = []
    if recipient_emails: # Prioritize per-site emails if provided
        target_recipients = [email for email in recipient_emails if email.strip()] # Basic validation
    
    if not target_recipients and default_recipients_str: # Fallback to default config
        if isinstance(default_recipients_str, str):
            target_recipients = [email.strip() for email in default_recipients_str.split(',') if email.strip()]
        elif isinstance(default_recipients_str, list):
            target_recipients = [email for email in default_recipients_str if email.strip()]

    if not target_recipients:
        logger.error("No recipient email addresses specified (neither per-site nor default). Cannot send alert.")
        return False

    email_config = {
        'from': smtp_sender,
        'to': ", ".join(target_recipients), # Join list for the 'To' header
        'smtp_server': config.get('smtp_server'),
        'smtp_port': config.get('smtp_port', 587), # Default to 587 if not specified
        'smtp_username': config.get('smtp_username'),
        'smtp_password': config.get('smtp_password'),
        'use_tls': config.get('smtp_use_tls', True) # Default to True for security
    }

    required_fields = ['from', 'to', 'smtp_server']
    if not all(email_config.get(field) for field in required_fields):
        logger.error("Email configuration missing required fields (from, to, smtp_server). Cannot send alert.")
        # Recipient 'to' is handled by target_recipients logic above
        missing = [field for field in required_fields if not email_config.get(field)]
        logger.error(f"Missing email config fields: {missing}")
        return False

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = email_config['from']
    msg['To'] = email_config['to']

    # Attach parts
    if body_text:
        part_text = MIMEText(body_text, 'plain')
        msg.attach(part_text)
    
    part_html = MIMEText(body_html, 'html')
    msg.attach(part_html)

    try:
        logger.info(f"Attempting to send email alert to {email_config['to']} via {email_config['smtp_server']}:{email_config['smtp_port']}")
        with smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port']) as server:
            if email_config.get('use_tls', True): # Default to True if not specified
                server.starttls() # Secure the connection
            if email_config['smtp_username'] and email_config['smtp_password']:
                server.login(email_config['smtp_username'], email_config['smtp_password'])
            server.sendmail(email_config['from'], target_recipients, msg.as_string()) # Use target_recipients list here
        logger.info(f"Email alert '{subject}' sent successfully to {email_config['to']}.")
        return True
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP Authentication Error: {e}. Check username/password or app password requirements.")
        return False
    except smtplib.SMTPServerDisconnected as e:
        logger.error(f"SMTP Server Disconnected: {e}. Check server address, port, or network.")
        return False
    except smtplib.SMTPConnectError as e:
        logger.error(f"SMTP Connection Error: {e}. Check server address, port, or firewall.")
        return False
    except ConnectionRefusedError as e:
        logger.error(f"Connection Refused Error: {e}. Ensure SMTP server is running and accessible.")
        return False
    except Exception as e:
        logger.error(f"Failed to send email alert: {e}", exc_info=True)
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