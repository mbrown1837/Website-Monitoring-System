"""
Container-specific utilities to handle compatibility issues.
This module provides safe alternatives to complex f-strings that might fail in containers.
"""

def safe_format_visual_score(check_results):
    """Safely format visual difference score."""
    if check_results.get('visual_diff_percent'):
        return f'<p><strong>Visual Difference Score:</strong> {check_results.get("visual_diff_percent", 0):.2f}%</p>'
    return ''

def safe_format_broken_links(broken_links):
    """Safely format broken links count."""
    if broken_links:
        return f'<p><strong>Broken Links:</strong> {len(broken_links)} found</p>'
    return ''

def safe_format_missing_meta(missing_meta):
    """Safely format missing meta tags count."""
    if missing_meta:
        return f'<p><strong>Missing Meta Tags:</strong> {len(missing_meta)} found</p>'
    return ''

def safe_format_blur_percentage(check_results):
    """Safely format blur percentage."""
    blur_percentage = check_results.get('blur_detection_summary', {}).get('blur_percentage')
    if blur_percentage:
        return f'<p><strong>Blur Percentage:</strong> {blur_percentage}%</p>'
    return ''

def safe_format_performance_scores(check_results):
    """Safely format performance scores."""
    perf_data = check_results.get('performance_check', {}).get('performance_check_summary', {})
    mobile_score = perf_data.get('avg_mobile_score')
    desktop_score = perf_data.get('avg_desktop_score')
    
    result = ''
    if mobile_score:
        result += f'<p><strong>Average Mobile Score:</strong> {mobile_score}/100</p>'
    if desktop_score:
        result += f'<p><strong>Average Desktop Score:</strong> {desktop_score}/100</p>'
    
    return result

def safe_format_baseline_comparison(check_results):
    """Safely format baseline comparison status."""
    has_baselines = check_results.get('visual_baselines', []) or check_results.get('latest_snapshots', {})
    status = "Completed" if has_baselines else "No baseline available"
    return f'<p><strong>Baseline Comparison:</strong> {status}</p>'
