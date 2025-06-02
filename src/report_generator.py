import json
import csv
import io
import html # Added for html.escape
from src.logger_setup import setup_logging

logger = setup_logging()

def generate_json_report(check_record: dict) -> str:
    """Generates a JSON report string from a single check record."""
    try:
        return json.dumps(check_record, indent=2)
    except TypeError as e:
        logger.error(f"Error serializing check_record to JSON: {e} - Record: {check_record}")
        return json.dumps({"error": "Failed to serialize record to JSON", "details": str(e)})

def generate_csv_report(check_records: list[dict]) -> str:
    """
    Generates a CSV report string from a list of check records.
    The CSV will have a predefined set of columns, and complex fields will be JSON stringified.
    """
    if not check_records:
        return ""

    # Define a consistent set of headers. Add more as needed.
    # Complex fields like dictionaries or lists will be JSON.dumps'd into a single CSV cell.
    headers = [
        'check_id', 'site_id', 'timestamp_utc', 'status',
        'html_snapshot_path', 'html_content_hash', 'visual_snapshot_path',
        'content_diff_score', 'structure_diff_score', 'visual_diff_score',
        'meta_changes', 'link_changes', 'image_src_changes', 'canonical_url_change',
        'significant_change_detected', 'errors'
    ]

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers, extrasaction='ignore') # ignore fields not in headers
    
    writer.writeheader()
    for record in check_records:
        row_to_write = {}
        for header in headers:
            value = record.get(header)
            if isinstance(value, (dict, list, set)):
                try:
                    row_to_write[header] = json.dumps(value) # Serialize complex types
                except TypeError:
                    row_to_write[header] = str(value) # Fallback to string
            elif value is None:
                row_to_write[header] = '' # Empty string for None
            else:
                row_to_write[header] = value
        writer.writerow(row_to_write)
    
    return output.getvalue()

def generate_detailed_html_report_for_check(check_record: dict, site_name:str = "N/A", site_url:str = "N/A") -> str:
    """Generates a detailed HTML report for a single check record."""
    if not check_record:
        return "<p>No check record data provided.</p>"

    # Helper to safely get values and format them (used for general fields)
    def get_val(key, default='N/A', precision=None):
        val = check_record.get(key, default)
        if val is None: val = default
        if precision is not None and isinstance(val, (float, int)):
            return f"{val:.{precision}f}"
        # Fallback for other complex types if not handled by specific formatters
        if isinstance(val, list) or isinstance(val, dict):
            try:
                return f"<pre>{html.escape(json.dumps(val, indent=2))}</pre>"
            except TypeError:
                return html.escape(str(val))
        return html.escape(str(val))

    # Helper for semantic diff details
    def format_semantic_diffs(diff_details):
        if not diff_details or not isinstance(diff_details, list):
            return "<p>No semantic diff details available.</p>"
        parts = []
        for op, text in diff_details:
            escaped_text = html.escape(text).replace("\n", "<br>")
            if op == 0: # DIFF_EQUAL
                parts.append(f'<span style="color: grey;">{escaped_text}</span>')
            elif op == -1: # DIFF_DELETE
                parts.append(f'<span style="color: red; text-decoration: line-through;">{escaped_text}</span>')
            elif op == 1: # DIFF_INSERT
                parts.append(f'<span style="color: green;">{escaped_text}</span>')
        return f"<pre>{''.join(parts)}</pre>"

    # Helper for difflib text diff details
    def format_difflib_details(diff_lines):
        if not diff_lines or not isinstance(diff_lines, list):
            return "<p>No difflib details available.</p>"
        html_output = "<pre>"
        for line in diff_lines:
            line_escaped = html.escape(line)
            if line.startswith('+'):
                html_output += f'<span style="color: green;">{line_escaped}</span>\n'
            elif line.startswith('-'):
                html_output += f'<span style="color: red;">{line_escaped}</span>\n'
            elif line.startswith('@'):
                html_output += f'<span style="color: blue;">{line_escaped}</span>\n'
            else:
                html_output += f'{line_escaped}\n'
        html_output += "</pre>"
        return html_output

    # Helper for Meta Tag Changes
    def format_meta_changes_html(meta_changes_dict):
        if not meta_changes_dict or not isinstance(meta_changes_dict, dict):
            return "<p>No meta tag changes detected or data unavailable.</p>"
        parts = []
        for tag_name, change_detail in meta_changes_dict.items():
            old_val = html.escape(str(change_detail.get('old', 'N/A')))
            new_val = html.escape(str(change_detail.get('new', 'N/A')))
            parts.append(f"<li>Meta tag <strong>{html.escape(tag_name)}</strong>: changed from '<code>{old_val}</code>' to '<code>{new_val}</code>'.</li>")
        if not parts:
            return "<p>No specific meta tag changes recorded.</p>"
        return f"<ul>{''.join(parts)}</ul>"

    # Helper for Link Changes
    def format_link_changes_html(link_changes_dict):
        if not link_changes_dict or not isinstance(link_changes_dict, dict):
            return "<p>No link changes detected or data unavailable.</p>"
        parts = []
        added_links = link_changes_dict.get('added', [])
        removed_links = link_changes_dict.get('removed', [])

        if added_links:
            parts.append("<h5>Added Links:</h5><ul>")
            for link in added_links:
                parts.append(f"<li><code>{html.escape(link)}</code></li>")
            parts.append("</ul>")
        
        if removed_links:
            parts.append("<h5>Removed Links:</h5><ul>")
            for link in removed_links:
                parts.append(f"<li><code>{html.escape(link)}</code></li>")
            parts.append("</ul>")

        if not parts:
            return "<p>No specific link changes recorded.</p>"
        return "".join(parts)

    # Helper for Image Source Changes
    def format_image_src_changes_html(image_src_changes_dict):
        if not image_src_changes_dict or not isinstance(image_src_changes_dict, dict):
            return "<p>No image source changes detected or data unavailable.</p>"
        parts = []
        added_sources = image_src_changes_dict.get('added_images', []) # Key from comparator
        removed_sources = image_src_changes_dict.get('removed_images', []) # Key from comparator

        if added_sources:
            parts.append("<h5>Added Image Sources:</h5><ul>")
            for src in added_sources:
                parts.append(f"<li><code>{html.escape(src)}</code></li>")
            parts.append("</ul>")

        if removed_sources:
            parts.append("<h5>Removed Image Sources:</h5><ul>")
            for src in removed_sources:
                parts.append(f"<li><code>{html.escape(src)}</code></li>")
            parts.append("</ul>")
            
        if not parts:
            return "<p>No specific image source changes recorded.</p>"
        return "".join(parts)

    # Helper for Canonical URL Change
    def format_canonical_url_change_html(canonical_change_data):
        if canonical_change_data is None: # Explicitly None means no change recorded or not applicable
            return "<p>No change in canonical URL or not applicable.</p>"
        if not isinstance(canonical_change_data, dict):
            return f"<p>Canonical URL data: {get_val('canonical_url_change')}</p>" # Fallback to get_val if unexpected format

        old_url = canonical_change_data.get('old')
        new_url = canonical_change_data.get('new')

        if old_url == new_url: # Should ideally be None if no change, but double check
             return "<p>No change in canonical URL.</p>"
        
        msg_parts = ["Canonical URL:"]
        if old_url and new_url:
            msg_parts.append(f" changed from <code>{html.escape(old_url)}</code> to <code>{html.escape(new_url)}</code>.")
        elif new_url:
            msg_parts.append(f" added '<code>{html.escape(new_url)}</code>'.")
        elif old_url: # Only old_url exists implies it was removed
            msg_parts.append(f" removed '<code>{html.escape(old_url)}</code>'.")
        else: # Both None, but handled by initial check usually
            return "<p>Canonical URL: No specific change details.</p>"
        return f"<p>{''.join(msg_parts)}</p>"

    body = f"""
    <html>
    <head>
        <title>Check Report: {site_name}</title>
        <style>
            body {{ font-family: sans-serif; margin: 20px; background-color: #f4f4f4; color: #333; }}
            .container {{ background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
            h1, h2, h3 {{ color: #333; }}
            table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
            th, td {{ text-align: left; padding: 10px; border-bottom: 1px solid #ddd; }}
            th {{ background-color: #e9e9e9; }}
            .status-ok {{ color: green; font-weight: bold; }}
            .status-changed {{ color: red; font-weight: bold; }}
            .status-error {{ color: orange; font-weight: bold; }}
            .snapshot-link {{ display: inline-block; margin: 5px 0; padding: 8px 12px; background-color: #007bff; color: white; text-decoration: none; border-radius: 4px; }}
            .snapshot-link:hover {{ background-color: #0056b3; }}
            pre {{ white-space: pre-wrap; word-wrap: break-word; background: #eee; padding: 10px; border-radius: 4px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Monitoring Check Report</h1>
            <p><strong>Site:</strong> {site_name} (<a href=\"{site_url}\">{site_url}</a>)</p>
            <p><strong>Check ID:</strong> {get_val('check_id')}</p>
            <p><strong>Timestamp (UTC):</strong> {get_val('timestamp_utc')}</p>
            <p><strong>Status:</strong> <span class="status-{{ 'changed' if check_record.get('significant_change_detected') else ('error' if 'fail' in check_record.get('status','').lower() else 'ok') }}">
                {get_val('status').replace('_',' ').title()}
            </span></p>
            <p><strong>Significant Change Detected:</strong> {get_val('significant_change_detected')}</p>
            
            <h2>Snapshots</h2>
            <table>
                <tr><th>Type</th><th>Path/Link</th><th>Hash</th></tr>
                <tr>
                    <td>HTML</td>
                    <td>{get_val('html_snapshot_path') if check_record.get('html_snapshot_path') else 'N/A'}</td>
                    <td>{get_val('html_content_hash')}</td>
                </tr>
                <tr>
                    <td>Visual</td>
                    <td>{get_val('visual_snapshot_path') if check_record.get('visual_snapshot_path') else 'N/A'}</td>
                    <td>N/A</td>
                </tr>
                 <tr>
                    <td>Visual Diff Image</td>
                    <td>{get_val('visual_diff_image_path') if check_record.get('visual_diff_image_path') else 'N/A'}</td>
                    <td>N/A</td>
                </tr>
            </table>
            
            <h2>Comparison Scores</h2>
            <table>
                <tr><th>Metric</th><th>Score</th></tr>
                <tr><td>Content Similarity (Difflib)</td><td>{get_val('content_diff_score', precision=4)}</td></tr>
                <tr><td>Semantic Similarity (Diff-Match-Patch)</td><td>{get_val('semantic_diff_score', precision=4)}</td></tr>
                <tr><td>Structure Similarity</td><td>{get_val('structure_diff_score', precision=4)}</td></tr>
                <tr><td>Visual Difference (MSE)</td><td>{get_val('visual_diff_score', precision=4)}</td></tr>
                <tr><td>Visual Similarity (SSIM)</td><td>{get_val('ssim_score', precision=4)}</td></tr>
            </table>

            <h2>Detailed Differences</h2>
            
            <h3>Text Content Differences (Difflib)</h3>
            {format_difflib_details(check_record.get('content_diff_details'))}
            
            <h3>Semantic Text Differences (Diff-Match-Patch)</h3>
            {format_semantic_diffs(check_record.get('semantic_diff_details'))}
            
            <h3>Meta Tag Changes</h3>
            {format_meta_changes_html(check_record.get('meta_changes'))}
            
            <h3>Link Changes</h3>
            {format_link_changes_html(check_record.get('link_changes'))}
            
            <h3>Image Source Changes</h3>
            {format_image_src_changes_html(check_record.get('image_src_changes'))}

            <h3>Canonical URL Change</h3>
            {format_canonical_url_change_html(check_record.get('canonical_url_change'))}
            
        </div>
    </body>
    </html>
    """

    error_section = ""
    if check_record.get('errors'):
        error_section = f"""
            <h2>Errors</h2>
            <p style=\"color: red;\">{get_val('errors')}</p>
        """
    
    # Correctly insert the error section into the main body
    # Find the closing div of the container and insert before it.
    body_parts = body.split("        </div>")
    if len(body_parts) == 2:
        final_body = body_parts[0] + error_section + "\n        </div>" + body_parts[1]
    else: # Fallback if split doesn't work as expected (e.g. spacing changes)
        final_body = body.replace("</body>", error_section + "\n</body>") # Less precise but should work

    return final_body

if __name__ == '__main__':
    from datetime import datetime, timezone # For demo data
    logger.info("----- Report Generator Demo -----")

    sample_check_record_1 = {
        "check_id": "demo-check-001", "site_id": "site-abc", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "completed_with_changes",
        "html_snapshot_path": "path/html1.html", "html_content_hash": "hashA",
        "visual_snapshot_path": "path/img1.png", "visual_diff_score": 0.11,
        "content_diff_score": 0.85, "structure_diff_score": 0.92,
        "meta_changes": {"description": {"old": "Old", "new": "New"}},
        "link_changes": {"added": ["/new_link"]},
        "image_src_changes": {},
        "canonical_url_change": None,
        "significant_change_detected": True, "errors": None
    }
    sample_check_record_2 = {
        "check_id": "demo-check-002", "site_id": "site-xyz", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "failed",
        "html_snapshot_path": None, "html_content_hash": None,
        "visual_snapshot_path": None, "visual_diff_score": None,
        "content_diff_score": None, "structure_diff_score": None,
        "meta_changes": {},
        "link_changes": {},
        "image_src_changes": {},
        "canonical_url_change": None,
        "significant_change_detected": False, "errors": "Timeout during fetch"
    }
    sample_check_record_3 = {
        "check_id": "demo-check-003", "site_id": "site-abc", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "completed_no_changes",
        "html_snapshot_path": "path/html2.html", "html_content_hash": "hashB",
        "visual_snapshot_path": "path/img2.png", "visual_diff_score": 0.001,
        "content_diff_score": 0.999, "structure_diff_score": 1.0,
        "meta_changes": {},
        "link_changes": {},
        "image_src_changes": {},
        "canonical_url_change": None,
        "significant_change_detected": False, "errors": None
    }

    print("\n--- JSON Report (Single Record) ---")
    json_report = generate_json_report(sample_check_record_1)
    print(json_report)
    # Basic validation
    try:
        loaded_json = json.loads(json_report)
        assert loaded_json['check_id'] == sample_check_record_1['check_id']
        logger.info("JSON report for single record generated and validated successfully.")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse generated JSON report: {e}")

    print("\n--- CSV Report (Multiple Records) ---")
    all_records = [sample_check_record_1, sample_check_record_2, sample_check_record_3]
    csv_report = generate_csv_report(all_records)
    print(csv_report)
    # Basic validation: check for header and at least one data row
    assert headers[0] in csv_report # Check if the first header is present
    assert sample_check_record_1['check_id'] in csv_report # Check if a unique ID from a record is present
    logger.info("CSV report for multiple records generated successfully (basic check).")

    print("\n--- Detailed HTML Report (Single Record) ---")
    html_report = generate_detailed_html_report_for_check(sample_check_record_1, "Demo Site", "http://example.com/demo")
    # print(html_report) # Can be very long
    with open("temp_detailed_report.html", "w", encoding="utf-8") as f_html:
        f_html.write(html_report)
    logger.info("Detailed HTML report generated and saved to temp_detailed_report.html")
    assert "<h1>Monitoring Check Report</h1>" in html_report
    assert "Content Similarity (Difflib)" in html_report
    assert "Semantic Text Differences (Diff-Match-Patch)" in html_report

    logger.info("----- Report Generator Demo Finished -----") 