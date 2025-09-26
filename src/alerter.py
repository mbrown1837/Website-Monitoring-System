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

def _determine_check_type(check_results: dict) -> str:
    """
    Determine what type of check was performed based on the results.
    Returns: 'manual_visual', 'manual_crawl', 'manual_blur', 'manual_performance', 
             'manual_baseline', 'manual_full', 'scheduled_full', 'scheduled_combined'
    """
    # Check if this is a baseline creation
    if check_results.get('status') == 'Baseline Created':
        return 'manual_baseline'
    
    # Check if this is an error (like no baselines for visual check)
    if check_results.get('status') == 'error':
        return 'error'
    
    # Analyze what checks were actually performed
    has_crawl = bool(check_results.get('crawl_stats', {}).get('pages_crawled', 0) > 0)
    has_visual = bool(check_results.get('visual_baselines') or check_results.get('latest_snapshots'))
    has_blur = bool(check_results.get('blur_detection_summary', {}).get('total_images_processed', 0) > 0)
    has_performance = bool(check_results.get('performance_check', {}).get('performance_check_summary', {}).get('pages_analyzed', 0) > 0)
    
    # Count how many check types were performed
    check_count = sum([has_crawl, has_visual, has_blur, has_performance])
    
    # Determine if this was a manual check or scheduled check
    is_manual = check_results.get('is_manual', False)
    
    if check_count == 1:
        # Single check type
        if has_crawl:
            return 'manual_crawl' if is_manual else 'scheduled_crawl'
        elif has_visual:
            return 'manual_visual' if is_manual else 'scheduled_visual'
        elif has_blur:
            return 'manual_blur' if is_manual else 'scheduled_blur'
        elif has_performance:
            return 'manual_performance' if is_manual else 'scheduled_performance'
    elif check_count > 1:
        # Multiple check types
        if is_manual:
            return 'manual_full'
        else:
            return 'scheduled_combined'
    else:
        # No specific checks detected, assume full check
        return 'manual_full' if is_manual else 'scheduled_full'

def _create_subject(site_name: str, check_type: str, is_change_report: bool, check_results: dict) -> str:
    """
    Create appropriate subject line based on check type and website name.
    """
    # Base subject with website name
    base_subject = f"[{site_name}]"
    
    # Check type specific subjects
    if check_type == 'manual_visual':
        if is_change_report:
            return f"{base_subject} 🔍 Visual Changes Detected - Manual Check"
        else:
            return f"{base_subject} 📸 Visual Check Complete - Manual Check"
    
    elif check_type == 'manual_crawl':
        broken_links = len(check_results.get('broken_links', []))
        if broken_links > 0:
            return f"{base_subject} 🚨 {broken_links} Broken Links Found - Manual Crawl Check"
        else:
            return f"{base_subject} ✅ Crawl Check Complete - Manual Check"
    
    elif check_type == 'manual_blur':
        blur_issues = check_results.get('blur_detection_summary', {}).get('blurry_images', 0)
        if blur_issues > 0:
            return f"{base_subject} 🔍 {blur_issues} Blurry Images Found - Manual Blur Check"
        else:
            return f"{base_subject} 📸 Blur Check Complete - Manual Check"
    
    elif check_type == 'manual_performance':
        avg_score = check_results.get('performance_check', {}).get('performance_check_summary', {}).get('avg_mobile_score', 0)
        if avg_score < 50:
            return f"{base_subject} ⚡ Performance Issues Detected (Score: {avg_score}/100) - Manual Check"
        else:
            return f"{base_subject} ⚡ Performance Check Complete (Score: {avg_score}/100) - Manual Check"
    
    elif check_type == 'manual_baseline':
        return f"{base_subject} 📸 Baseline Created Successfully - Manual Check"
    
    elif check_type == 'manual_full':
        if is_change_report:
            return f"{base_subject} 🚨 Issues Detected - Full Manual Check"
        else:
            return f"{base_subject} ✅ Full Check Complete - Manual Check"
    
    elif check_type == 'scheduled_full':
        if is_change_report:
            return f"{base_subject} 🚨 Issues Detected - Scheduled Full Check"
        else:
            return f"{base_subject} ✅ Scheduled Check Complete"
    
    elif check_type == 'scheduled_combined':
        if is_change_report:
            return f"{base_subject} 🚨 Issues Detected - Scheduled Combined Check"
        else:
            return f"{base_subject} ✅ Scheduled Combined Check Complete"
    
    elif check_type == 'error':
        error_msg = check_results.get('error', 'Unknown error')
        return f"{base_subject} ❌ Check Failed: {error_msg}"
    
    else:
        # Fallback
        if is_change_report:
            return f"{base_subject} 🚨 Changes Detected - Website Check"
        else:
            return f"{base_subject} ✅ Website Check Complete"

def get_config_dynamic():
    """Get config dynamically to ensure environment variables are loaded."""
    from src.config_loader import get_config_path_for_environment
    config_path = get_config_path_for_environment()
    logger.info(f"Loading config from: {config_path}")
    config = get_config(config_path=config_path)
    logger.info(f"Config loaded - keys: {list(config.keys()) if config else 'None'}")
    return config

def _create_email_content(site_name: str, site_url: str, check_type: str, check_results: dict, dashboard_url: str) -> str:
    """
    Create check-type specific email content.
    """
    # Determine header color and icon based on check type
    if check_type.startswith('manual_'):
        header_color = '#28a745'  # Green for manual checks
        header_icon = '🔧'
        check_type_text = 'Manual Check'
    elif check_type.startswith('scheduled_'):
        header_color = '#4a90e2'  # Blue for scheduled checks
        header_icon = '⏰'
        check_type_text = 'Scheduled Check'
    elif check_type == 'error':
        header_color = '#dc3545'  # Red for errors
        header_icon = '❌'
        check_type_text = 'Check Failed'
    else:
        header_color = '#6c757d'  # Gray for unknown
        header_icon = '📊'
        check_type_text = 'Website Check'
    
    # Create check-specific content sections
    content_sections = _create_content_sections(check_type, check_results)
    
    # Create metrics section
    metrics_section = _create_metrics_section(check_type, check_results)
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{check_type_text} - {site_name}</title>
    </head>
    <body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5;">
        <div style="max-width: 800px; margin: 0 auto; background: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); overflow: hidden;">
            
            <!-- Header -->
            <div style="background: {header_color}; color: white; padding: 30px 20px; text-align: center;">
                <h1 style="margin: 0; font-size: 28px; font-weight: bold;">{header_icon} {check_type_text}</h1>
                <p style="margin: 8px 0 0 0; font-size: 16px; opacity: 0.9;">{html.escape(site_name)}</p>
            </div>
            
            <!-- Content -->
            <div style="padding: 30px;">
                
                <!-- Check Summary -->
                <h2 style="color: #333; border-bottom: 2px solid {header_color}; padding-bottom: 10px;">📊 Check Summary</h2>
                <p>A {check_type_text.lower()} has been completed for <strong><a href="{html.escape(site_url)}" style="color: {header_color};">{html.escape(site_url)}</a></strong></p>
                <p><strong>Check Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                <p><strong>Status:</strong> {check_results.get('status', 'Completed')}</p>
                
                {metrics_section}
                
                {content_sections}
                
                <!-- Quick Actions -->
                <h2 style="color: #333; border-bottom: 2px solid {header_color}; padding-bottom: 10px;">🔗 Quick Actions</h2>
                <div style="text-align: center; margin: 20px 0;">
                    <a href="{dashboard_url}/website/history/{check_results.get('site_id', check_results.get('site_id', check_results.get('website_id')))}" style="background: #28a745; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 5px; display: inline-block; font-weight: bold;">View History</a>
                    <a href="{dashboard_url}/website/{check_results.get('site_id', check_results.get('site_id', check_results.get('website_id')))}" style="background: #4a90e2; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 5px; display: inline-block; font-weight: bold;">View Dashboard</a>
                    <a href="{dashboard_url}/website/{check_results.get('site_id', check_results.get('site_id', check_results.get('website_id')))}/crawler" style="background: #17a2b8; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 5px; display: inline-block; font-weight: bold;">View Crawler Results</a>
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

def _create_metrics_section(check_type: str, check_results: dict) -> str:
    """
    Create metrics section based on check type.
    """
    if check_type == 'manual_visual':
        return f"""
                <!-- Visual Check Metrics -->
                <h2 style="color: #333; border-bottom: 2px solid #28a745; padding-bottom: 10px;">📸 Visual Check Results</h2>
                <div style="display: flex; justify-content: space-around; margin: 20px 0; flex-wrap: wrap;">
                    <div style="background: #f8f9fa; padding: 20px; margin: 10px; border-radius: 8px; text-align: center; min-width: 150px; border: 1px solid #ddd;">
                        <div style="font-size: 32px; font-weight: bold; color: #28a745;">{len(check_results.get('visual_baselines', []) or check_results.get('latest_snapshots', {}))}</div>
                        <div style="font-size: 14px; color: #666; text-transform: uppercase;">Snapshots</div>
                    </div>
                    <div style="background: #f8f9fa; padding: 20px; margin: 10px; border-radius: 8px; text-align: center; min-width: 150px; border: 1px solid #ddd;">
                        <div style="font-size: 32px; font-weight: bold; color: {'#dc3545' if check_results.get('significant_change_detected', False) else '#28a745'};">{'Yes' if check_results.get('significant_change_detected', False) else 'No'}</div>
                        <div style="font-size: 14px; color: #666; text-transform: uppercase;">Changes Detected</div>
                    </div>
                    {f'<div style="background: #f8f9fa; padding: 20px; margin: 10px; border-radius: 8px; text-align: center; min-width: 150px; border: 1px solid #ddd;"><div style="font-size: 32px; font-weight: bold; color: #ffc107;">{check_results.get("visual_diff_percent", 0):.1f}%</div><div style="font-size: 14px; color: #666; text-transform: uppercase;">Difference</div></div>' if check_results.get('visual_diff_percent') else ''}
                </div>
        """
    
    elif check_type == 'manual_crawl':
        broken_links = len(check_results.get('broken_links', []))
        missing_meta = len(check_results.get('missing_meta_tags', []))
        return f"""
                <!-- Crawl Check Metrics -->
                <h2 style="color: #333; border-bottom: 2px solid #4a90e2; padding-bottom: 10px;">🌐 Crawl Check Results</h2>
                <div style="display: flex; justify-content: space-around; margin: 20px 0; flex-wrap: wrap;">
                    <div style="background: #f8f9fa; padding: 20px; margin: 10px; border-radius: 8px; text-align: center; min-width: 150px; border: 1px solid #ddd;">
                        <div style="font-size: 32px; font-weight: bold; color: #4a90e2;">{check_results.get('crawl_stats', {}).get('pages_crawled', 0)}</div>
                        <div style="font-size: 14px; color: #666; text-transform: uppercase;">Pages Crawled</div>
                    </div>
                    <div style="background: #f8f9fa; padding: 20px; margin: 10px; border-radius: 8px; text-align: center; min-width: 150px; border: 1px solid #ddd;">
                        <div style="font-size: 32px; font-weight: bold; color: {'#dc3545' if broken_links > 0 else '#28a745'};">{broken_links}</div>
                        <div style="font-size: 14px; color: #666; text-transform: uppercase;">Broken Links</div>
                    </div>
                    <div style="background: #f8f9fa; padding: 20px; margin: 10px; border-radius: 8px; text-align: center; min-width: 150px; border: 1px solid #ddd;">
                        <div style="font-size: 32px; font-weight: bold; color: {'#ffc107' if missing_meta > 0 else '#28a745'};">{missing_meta}</div>
                        <div style="font-size: 14px; color: #666; text-transform: uppercase;">Missing Meta Tags</div>
                    </div>
                </div>
        """
    
    elif check_type == 'manual_blur':
        blur_issues = check_results.get('blur_detection_summary', {}).get('blurry_images', 0)
        total_images = check_results.get('blur_detection_summary', {}).get('total_images_processed', 0)
        return f"""
                <!-- Blur Check Metrics -->
                <h2 style="color: #333; border-bottom: 2px solid #17a2b8; padding-bottom: 10px;">🔍 Blur Detection Results</h2>
                <div style="display: flex; justify-content: space-around; margin: 20px 0; flex-wrap: wrap;">
                    <div style="background: #f8f9fa; padding: 20px; margin: 10px; border-radius: 8px; text-align: center; min-width: 150px; border: 1px solid #ddd;">
                        <div style="font-size: 32px; font-weight: bold; color: #17a2b8;">{total_images}</div>
                        <div style="font-size: 14px; color: #666; text-transform: uppercase;">Images Analyzed</div>
                    </div>
                    <div style="background: #f8f9fa; padding: 20px; margin: 10px; border-radius: 8px; text-align: center; min-width: 150px; border: 1px solid #ddd;">
                        <div style="font-size: 32px; font-weight: bold; color: {'#dc3545' if blur_issues > 0 else '#28a745'};">{blur_issues}</div>
                        <div style="font-size: 14px; color: #666; text-transform: uppercase;">Blur Issues</div>
                    </div>
                    {f'<div style="background: #f8f9fa; padding: 20px; margin: 10px; border-radius: 8px; text-align: center; min-width: 150px; border: 1px solid #ddd;"><div style="font-size: 32px; font-weight: bold; color: #ffc107;">{check_results.get("blur_detection_summary", {}).get("blur_percentage", 0)}%</div><div style="font-size: 14px; color: #666; text-transform: uppercase;">Blur Percentage</div></div>' if check_results.get('blur_detection_summary', {}).get('blur_percentage') else ''}
                </div>
        """
    
    elif check_type == 'manual_performance':
        avg_score = check_results.get('performance_check', {}).get('performance_check_summary', {}).get('avg_mobile_score', 0)
        pages_checked = check_results.get('performance_check', {}).get('performance_check_summary', {}).get('pages_analyzed', 0)
        return f"""
                <!-- Performance Check Metrics -->
                <h2 style="color: #333; border-bottom: 2px solid #6f42c1; padding-bottom: 10px;">⚡ Performance Check Results</h2>
                <div style="display: flex; justify-content: space-around; margin: 20px 0; flex-wrap: wrap;">
                    <div style="background: #f8f9fa; padding: 20px; margin: 10px; border-radius: 8px; text-align: center; min-width: 150px; border: 1px solid #ddd;">
                        <div style="font-size: 32px; font-weight: bold; color: #6f42c1;">{pages_checked}</div>
                        <div style="font-size: 14px; color: #666; text-transform: uppercase;">Pages Checked</div>
                    </div>
                    <div style="background: #f8f9fa; padding: 20px; margin: 10px; border-radius: 8px; text-align: center; min-width: 150px; border: 1px solid #ddd;">
                        <div style="font-size: 32px; font-weight: bold; color: {'#dc3545' if avg_score < 50 else '#28a745' if avg_score >= 80 else '#ffc107'};">{avg_score}</div>
                        <div style="font-size: 14px; color: #666; text-transform: uppercase;">Mobile Score</div>
                    </div>
                    {f'<div style="background: #f8f9fa; padding: 20px; margin: 10px; border-radius: 8px; text-align: center; min-width: 150px; border: 1px solid #ddd;"><div style="font-size: 32px; font-weight: bold; color: #6f42c1;">{check_results.get("performance_check", {}).get("performance_check_summary", {}).get("avg_desktop_score", 0)}</div><div style="font-size: 14px; color: #666; text-transform: uppercase;">Desktop Score</div></div>' if check_results.get('performance_check', {}).get('performance_check_summary', {}).get('avg_desktop_score') else ''}
                </div>
        """
    
    elif check_type == 'manual_baseline':
        return f"""
                <!-- Baseline Creation Metrics -->
                <h2 style="color: #333; border-bottom: 2px solid #28a745; padding-bottom: 10px;">📸 Baseline Creation Results</h2>
                <div style="display: flex; justify-content: space-around; margin: 20px 0; flex-wrap: wrap;">
                    <div style="background: #f8f9fa; padding: 20px; margin: 10px; border-radius: 8px; text-align: center; min-width: 150px; border: 1px solid #ddd;">
                        <div style="font-size: 32px; font-weight: bold; color: #28a745;">{len(check_results.get('visual_baselines', []) or check_results.get('latest_snapshots', {}))}</div>
                        <div style="font-size: 14px; color: #666; text-transform: uppercase;">Baselines Created</div>
                    </div>
                    <div style="background: #f8f9fa; padding: 20px; margin: 10px; border-radius: 8px; text-align: center; min-width: 150px; border: 1px solid #ddd;">
                        <div style="font-size: 32px; font-weight: bold; color: #28a745;">✅</div>
                        <div style="font-size: 14px; color: #666; text-transform: uppercase;">Status</div>
                    </div>
                </div>
        """
    
    else:
        # Full check or combined check - show all metrics
        return f"""
                <!-- Comprehensive Check Metrics -->
                <h2 style="color: #333; border-bottom: 2px solid #4a90e2; padding-bottom: 10px;">📈 Check Results Summary</h2>
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
                    <div style="background: #f8f9fa; padding: 20px; margin: 10px; border-radius: 8px; text-align: center; min-width: 150px; border: 1px solid #ddd;">
                        <div style="font-size: 32px; font-weight: bold; color: #28a745;">{len(check_results.get('visual_baselines', []) or check_results.get('latest_snapshots', {}))}</div>
                        <div style="font-size: 14px; color: #666; text-transform: uppercase;">Visual Snapshots</div>
                    </div>
                    <div style="background: #f8f9fa; padding: 20px; margin: 10px; border-radius: 8px; text-align: center; min-width: 150px; border: 1px solid #ddd;">
                        <div style="font-size: 32px; font-weight: bold; color: #17a2b8;">{check_results.get('blur_detection_summary', {}).get('blurry_images', 0)}</div>
                        <div style="font-size: 14px; color: #666; text-transform: uppercase;">Blur Issues</div>
                    </div>
                    <div style="background: #f8f9fa; padding: 20px; margin: 10px; border-radius: 8px; text-align: center; min-width: 150px; border: 1px solid #ddd;">
                        <div style="font-size: 32px; font-weight: bold; color: #6f42c1;">{check_results.get('performance_check', {}).get('performance_check_summary', {}).get('pages_analyzed', 0)}</div>
                        <div style="font-size: 14px; color: #666; text-transform: uppercase;">Performance Checks</div>
                    </div>
                </div>
        """

def _create_content_sections(check_type: str, check_results: dict) -> str:
    """
    Create detailed content sections based on check type.
    """
    if check_type == 'manual_visual':
        return f"""
                <!-- Visual Check Details -->
                <h2 style="color: #333; border-bottom: 2px solid #28a745; padding-bottom: 10px;">🔍 Visual Check Details</h2>
                <div style="background: #f8f9fa; padding: 20px; margin: 15px 0; border-radius: 8px; border-left: 4px solid #28a745;">
                    <h3 style="color: #28a745; margin-top: 0;">📸 Visual Comparison Results</h3>
                    <p><strong>Snapshots Captured:</strong> {len(check_results.get('visual_baselines', []) or check_results.get('latest_snapshots', {}))}</p>
                    <p><strong>Visual Changes Detected:</strong> {'Yes' if check_results.get('significant_change_detected', False) else 'No'}</p>
                    {f'<p><strong>Visual Difference Score:</strong> {check_results.get("visual_diff_percent", 0):.2f}%</p>' if check_results.get('visual_diff_percent') else ''}
                    {f'<p><strong>Baseline Comparison:</strong> {"Completed" if check_results.get("baseline_comparison_completed", False) else "No baseline available"}</p>'}
                </div>
        """
    
    elif check_type == 'manual_crawl':
        broken_links = check_results.get('broken_links', [])
        missing_meta = check_results.get('missing_meta_tags', [])
        return f"""
                <!-- Crawl Check Details -->
                <h2 style="color: #333; border-bottom: 2px solid #4a90e2; padding-bottom: 10px;">🔍 Crawl Check Details</h2>
                <div style="background: #f8f9fa; padding: 20px; margin: 15px 0; border-radius: 8px; border-left: 4px solid #4a90e2;">
                    <h3 style="color: #4a90e2; margin-top: 0;">🌐 Crawl Results</h3>
                    <p><strong>Pages Crawled:</strong> {check_results.get('crawl_stats', {}).get('pages_crawled', 0)}</p>
                    <p><strong>Total Links Found:</strong> {check_results.get('crawl_stats', {}).get('total_links', 0)}</p>
                    <p><strong>Total Images Found:</strong> {check_results.get('crawl_stats', {}).get('total_images', 0)}</p>
                    <p><strong>Sitemap Found:</strong> {'Yes' if check_results.get('crawl_stats', {}).get('sitemap_found', False) else 'No'}</p>
                    {f'<p><strong>Broken Links:</strong> {len(broken_links)} found</p>' if broken_links else ''}
                    {f'<p><strong>Missing Meta Tags:</strong> {len(missing_meta)} found</p>' if missing_meta else ''}
                </div>
        """
    
    elif check_type == 'manual_blur':
        return f"""
                <!-- Blur Check Details -->
                <h2 style="color: #333; border-bottom: 2px solid #17a2b8; padding-bottom: 10px;">🔍 Blur Check Details</h2>
                <div style="background: #f8f9fa; padding: 20px; margin: 15px 0; border-radius: 8px; border-left: 4px solid #17a2b8;">
                    <h3 style="color: #17a2b8; margin-top: 0;">🔍 Blur Detection Results</h3>
                    <p><strong>Images Analyzed:</strong> {check_results.get('blur_detection_summary', {}).get('total_images_processed', 0)}</p>
                    <p><strong>Blur Issues Found:</strong> {check_results.get('blur_detection_summary', {}).get('blurry_images', 0)}</p>
                    {f'<p><strong>Blur Percentage:</strong> {check_results.get("blur_detection_summary", {}).get("blur_percentage", 0)}%</p>' if check_results.get('blur_detection_summary', {}).get('blur_percentage') else ''}
                    {f'<p><strong>Total Images Found:</strong> {check_results.get("blur_detection_summary", {}).get("total_images_found", 0)}</p>' if check_results.get('blur_detection_summary', {}).get('total_images_found') else ''}
                </div>
        """
    
    elif check_type == 'manual_performance':
        return f"""
                <!-- Performance Check Details -->
                <h2 style="color: #333; border-bottom: 2px solid #6f42c1; padding-bottom: 10px;">🔍 Performance Check Details</h2>
                <div style="background: #f8f9fa; padding: 20px; margin: 15px 0; border-radius: 8px; border-left: 4px solid #6f42c1;">
                    <h3 style="color: #6f42c1; margin-top: 0;">⚡ Performance Analysis</h3>
                    <p><strong>Pages Checked:</strong> {check_results.get('performance_check', {}).get('performance_check_summary', {}).get('pages_analyzed', 0)}</p>
                    {f'<p><strong>Average Mobile Score:</strong> {check_results.get("performance_check", {}).get("performance_check_summary", {}).get("avg_mobile_score", 0)}/100</p>' if check_results.get('performance_check', {}).get('performance_check_summary', {}).get('avg_mobile_score') else ''}
                    {f'<p><strong>Average Desktop Score:</strong> {check_results.get("performance_check", {}).get("performance_check_summary", {}).get("avg_desktop_score", 0)}/100</p>' if check_results.get('performance_check', {}).get('performance_check_summary', {}).get('avg_desktop_score') else ''}
                    {f'<p><strong>Slowest Page:</strong> {check_results.get("performance_check", {}).get("performance_check_summary", {}).get("slowest_page", "N/A")}</p>' if check_results.get('performance_check', {}).get('performance_check_summary', {}).get('slowest_page') else ''}
                    {f'<p><strong>Performance Issues:</strong> {check_results.get("performance_check", {}).get("performance_check_summary", {}).get("total_issues", 0)} found</p>' if check_results.get('performance_check', {}).get('performance_check_summary', {}).get('total_issues', 0) > 0 else ''}
                </div>
        """
    
    elif check_type == 'manual_baseline':
        return f"""
                <!-- Baseline Creation Details -->
                <h2 style="color: #333; border-bottom: 2px solid #28a745; padding-bottom: 10px;">🔍 Baseline Creation Details</h2>
                <div style="background: #f8f9fa; padding: 20px; margin: 15px 0; border-radius: 8px; border-left: 4px solid #28a745;">
                    <h3 style="color: #28a745; margin-top: 0;">📸 Baseline Creation Results</h3>
                    <p><strong>Baselines Created:</strong> {len(check_results.get('visual_baselines', []) or check_results.get('latest_snapshots', {}))}</p>
                    <p><strong>Status:</strong> ✅ Successfully completed</p>
                    <p><strong>Next Steps:</strong> You can now run visual checks to compare against these baselines.</p>
                </div>
        """
    
    elif check_type == 'error':
        error_msg = check_results.get('error', 'Unknown error')
        return f"""
                <!-- Error Details -->
                <h2 style="color: #333; border-bottom: 2px solid #dc3545; padding-bottom: 10px;">❌ Error Details</h2>
                <div style="background: #f8f9fa; padding: 20px; margin: 15px 0; border-radius: 8px; border-left: 4px solid #dc3545;">
                    <h3 style="color: #dc3545; margin-top: 0;">❌ Check Failed</h3>
                    <p><strong>Error Message:</strong> {error_msg}</p>
                    <p><strong>Status:</strong> Failed</p>
                    <p><strong>Recommendation:</strong> Please check the website configuration and try again.</p>
                </div>
        """
    
    else:
        # Full check or combined check - show all sections
        return f"""
                <!-- Detailed Check Results -->
                <h2 style="color: #333; border-bottom: 2px solid #4a90e2; padding-bottom: 10px;">🔍 Detailed Check Results</h2>
                
                <!-- Crawl Results -->
                <div style="background: #f8f9fa; padding: 20px; margin: 15px 0; border-radius: 8px; border-left: 4px solid #4a90e2;">
                    <h3 style="color: #4a90e2; margin-top: 0;">🌐 Crawl Check Results</h3>
                    <p><strong>Pages Crawled:</strong> {check_results.get('crawl_stats', {}).get('pages_crawled', 0)}</p>
                    <p><strong>Total Links Found:</strong> {check_results.get('crawl_stats', {}).get('total_links', 0)}</p>
                    <p><strong>Total Images Found:</strong> {check_results.get('crawl_stats', {}).get('total_images', 0)}</p>
                    <p><strong>Sitemap Found:</strong> {'Yes' if check_results.get('crawl_stats', {}).get('sitemap_found', False) else 'No'}</p>
                    {f'<p><strong>Broken Links:</strong> {len(check_results.get("broken_links", []))} found</p>' if len(check_results.get('broken_links', [])) > 0 else ''}
                    {f'<p><strong>Missing Meta Tags:</strong> {len(check_results.get("missing_meta_tags", []))} found</p>' if len(check_results.get('missing_meta_tags', [])) > 0 else ''}
                </div>

                <!-- Visual Check Results -->
                <div style="background: #f8f9fa; padding: 20px; margin: 15px 0; border-radius: 8px; border-left: 4px solid #28a745;">
                    <h3 style="color: #28a745; margin-top: 0;">📸 Visual Check Results</h3>
                    <p><strong>Snapshots Captured:</strong> {len(check_results.get('visual_baselines', []) or check_results.get('latest_snapshots', {}))}</p>
                    <p><strong>Visual Changes Detected:</strong> {'Yes' if check_results.get('significant_change_detected', False) else 'No'}</p>
                    {f'<p><strong>Visual Difference Score:</strong> {check_results.get("visual_diff_percent", 0):.2f}%</p>' if check_results.get('visual_diff_percent') else ''}
                    {f'<p><strong>Baseline Comparison:</strong> {"Completed" if check_results.get("baseline_comparison_completed", False) else "No baseline available"}</p>'}
                </div>

                <!-- Blur Detection Results -->
                <div style="background: #f8f9fa; padding: 20px; margin: 15px 0; border-radius: 8px; border-left: 4px solid #17a2b8;">
                    <h3 style="color: #17a2b8; margin-top: 0;">🔍 Blur Detection Results</h3>
                    <p><strong>Images Analyzed:</strong> {check_results.get('blur_detection_summary', {}).get('total_images_processed', 0)}</p>
                    <p><strong>Blur Issues Found:</strong> {check_results.get('blur_detection_summary', {}).get('blurry_images', 0)}</p>
                    {f'<p><strong>Blur Percentage:</strong> {check_results.get("blur_detection_summary", {}).get("blur_percentage", 0)}%</p>' if check_results.get('blur_detection_summary', {}).get('blur_percentage') else ''}
                    {f'<p><strong>Total Images Found:</strong> {check_results.get("blur_detection_summary", {}).get("total_images_found", 0)}</p>' if check_results.get('blur_detection_summary', {}).get('total_images_found') else ''}
                </div>

                <!-- Performance Check Results -->
                <div style="background: #f8f9fa; padding: 20px; margin: 15px 0; border-radius: 8px; border-left: 4px solid #6f42c1;">
                    <h3 style="color: #6f42c1; margin-top: 0;">⚡ Performance Check Results</h3>
                    <p><strong>Pages Checked:</strong> {check_results.get('performance_check', {}).get('performance_check_summary', {}).get('pages_analyzed', 0)}</p>
                    {f'<p><strong>Average Mobile Score:</strong> {check_results.get("performance_check", {}).get("performance_check_summary", {}).get("avg_mobile_score", 0)}/100</p>' if check_results.get('performance_check', {}).get('performance_check_summary', {}).get('avg_mobile_score') else ''}
                    {f'<p><strong>Average Desktop Score:</strong> {check_results.get("performance_check", {}).get("performance_check_summary", {}).get("avg_desktop_score", 0)}/100</p>' if check_results.get('performance_check', {}).get('performance_check_summary', {}).get('avg_desktop_score') else ''}
                    {f'<p><strong>Slowest Page:</strong> {check_results.get("performance_check", {}).get("performance_check_summary", {}).get("slowest_page", "N/A")}</p>' if check_results.get('performance_check', {}).get('performance_check_summary', {}).get('slowest_page') else ''}
                    {f'<p><strong>Performance Issues:</strong> {check_results.get("performance_check", {}).get("performance_check_summary", {}).get("total_issues", 0)} found</p>' if check_results.get('performance_check', {}).get('performance_check_summary', {}).get('total_issues', 0) > 0 else ''}
                </div>
        """

def _create_text_content(site_name: str, site_url: str, check_type: str, check_results: dict, dashboard_url: str) -> str:
    """
    Create check-type specific text email content.
    """
    # Determine check type text
    if check_type.startswith('manual_'):
        check_type_text = 'Manual Check'
    elif check_type.startswith('scheduled_'):
        check_type_text = 'Scheduled Check'
    elif check_type == 'error':
        check_type_text = 'Check Failed'
    else:
        check_type_text = 'Website Check'
    
    # Create check-specific content
    if check_type == 'manual_visual':
        return f"""
{check_type_text} Report for {site_name}
========================================

Website: {site_url}
Check Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
Status: {check_results.get('status', 'Completed')}

📸 VISUAL CHECK RESULTS:
=======================
- Snapshots Captured: {len(check_results.get('visual_baselines', []) or check_results.get('latest_snapshots', {}))}
- Visual Changes Detected: {'Yes' if check_results.get('significant_change_detected', False) else 'No'}
{f'- Visual Difference Score: {check_results.get("visual_diff_percent", 0):.2f}%' if check_results.get('visual_diff_percent') else ''}
{f'- Baseline Comparison: {"Completed" if check_results.get("baseline_comparison_completed", False) else "No baseline available"}'}

QUICK ACTIONS:
==============
- View History: {dashboard_url}/website/history/{check_results.get('site_id', check_results.get('website_id'))}
- View Dashboard: {dashboard_url}/website/{check_results.get('site_id', check_results.get('website_id'))}

This is an automated report from your Website Monitoring System.
Visit Dashboard: {dashboard_url}
        """
    
    elif check_type == 'manual_crawl':
        broken_links = len(check_results.get('broken_links', []))
        missing_meta = len(check_results.get('missing_meta_tags', []))
        return f"""
{check_type_text} Report for {site_name}
========================================

Website: {site_url}
Check Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
Status: {check_results.get('status', 'Completed')}

🌐 CRAWL CHECK RESULTS:
=======================
- Pages Crawled: {check_results.get('crawl_stats', {}).get('pages_crawled', 0)}
- Total Links Found: {check_results.get('crawl_stats', {}).get('total_links', 0)}
- Total Images Found: {check_results.get('crawl_stats', {}).get('total_images', 0)}
- Sitemap Found: {'Yes' if check_results.get('crawl_stats', {}).get('sitemap_found', False) else 'No'}
{f'- Broken Links: {broken_links} found' if broken_links > 0 else ''}
{f'- Missing Meta Tags: {missing_meta} found' if missing_meta > 0 else ''}

QUICK ACTIONS:
==============
- View History: {dashboard_url}/website/history/{check_results.get('site_id', check_results.get('website_id'))}
- View Dashboard: {dashboard_url}/website/{check_results.get('site_id', check_results.get('website_id'))}

This is an automated report from your Website Monitoring System.
Visit Dashboard: {dashboard_url}
        """
    
    elif check_type == 'manual_blur':
        return f"""
{check_type_text} Report for {site_name}
========================================

Website: {site_url}
Check Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
Status: {check_results.get('status', 'Completed')}

🔍 BLUR DETECTION RESULTS:
==========================
- Images Analyzed: {check_results.get('blur_detection_summary', {}).get('total_images_processed', 0)}
- Blur Issues Found: {check_results.get('blur_detection_summary', {}).get('blurry_images', 0)}
{f'- Blur Percentage: {check_results.get("blur_detection_summary", {}).get("blur_percentage", 0)}%' if check_results.get('blur_detection_summary', {}).get('blur_percentage') else ''}
{f'- Total Images Found: {check_results.get("blur_detection_summary", {}).get("total_images_found", 0)}' if check_results.get('blur_detection_summary', {}).get('total_images_found') else ''}

QUICK ACTIONS:
==============
- View History: {dashboard_url}/website/history/{check_results.get('site_id', check_results.get('website_id'))}
- View Dashboard: {dashboard_url}/website/{check_results.get('site_id', check_results.get('website_id'))}

This is an automated report from your Website Monitoring System.
Visit Dashboard: {dashboard_url}
        """
    
    elif check_type == 'manual_performance':
        return f"""
{check_type_text} Report for {site_name}
========================================

Website: {site_url}
Check Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
Status: {check_results.get('status', 'Completed')}

⚡ PERFORMANCE CHECK RESULTS:
=============================
- Pages Checked: {check_results.get('performance_check', {}).get('performance_check_summary', {}).get('pages_analyzed', 0)}
{f'- Average Mobile Score: {check_results.get("performance_check", {}).get("performance_check_summary", {}).get("avg_mobile_score", 0)}/100' if check_results.get('performance_check', {}).get('performance_check_summary', {}).get('avg_mobile_score') else ''}
{f'- Average Desktop Score: {check_results.get("performance_check", {}).get("performance_check_summary", {}).get("avg_desktop_score", 0)}/100' if check_results.get('performance_check', {}).get('performance_check_summary', {}).get('avg_desktop_score') else ''}
{f'- Slowest Page: {check_results.get("performance_check", {}).get("performance_check_summary", {}).get("slowest_page", "N/A")}' if check_results.get('performance_check', {}).get('performance_check_summary', {}).get('slowest_page') else ''}
{f'- Performance Issues: {check_results.get("performance_check", {}).get("performance_check_summary", {}).get("total_issues", 0)} found' if check_results.get('performance_check', {}).get('performance_check_summary', {}).get('total_issues', 0) > 0 else ''}

QUICK ACTIONS:
==============
- View History: {dashboard_url}/website/history/{check_results.get('site_id', check_results.get('website_id'))}
- View Dashboard: {dashboard_url}/website/{check_results.get('site_id', check_results.get('website_id'))}

This is an automated report from your Website Monitoring System.
Visit Dashboard: {dashboard_url}
        """
    
    elif check_type == 'manual_baseline':
        return f"""
{check_type_text} Report for {site_name}
========================================

Website: {site_url}
Check Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
Status: {check_results.get('status', 'Completed')}

📸 BASELINE CREATION RESULTS:
=============================
- Baselines Created: {len(check_results.get('visual_baselines', []) or check_results.get('latest_snapshots', {}))}
- Status: ✅ Successfully completed
- Next Steps: You can now run visual checks to compare against these baselines.

QUICK ACTIONS:
==============
- View History: {dashboard_url}/website/history/{check_results.get('site_id', check_results.get('website_id'))}
- View Dashboard: {dashboard_url}/website/{check_results.get('site_id', check_results.get('website_id'))}

This is an automated report from your Website Monitoring System.
Visit Dashboard: {dashboard_url}
        """
    
    elif check_type == 'error':
        error_msg = check_results.get('error', 'Unknown error')
        return f"""
{check_type_text} Report for {site_name}
========================================

Website: {site_url}
Check Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
Status: Failed

❌ ERROR DETAILS:
=================
- Error Message: {error_msg}
- Status: Failed
- Recommendation: Please check the website configuration and try again.

QUICK ACTIONS:
==============
- View History: {dashboard_url}/website/history/{check_results.get('site_id', check_results.get('website_id'))}
- View Dashboard: {dashboard_url}/website/{check_results.get('site_id', check_results.get('website_id'))}

This is an automated report from your Website Monitoring System.
Visit Dashboard: {dashboard_url}
        """
    
    else:
        # Full check or combined check - show all results
        return f"""
{check_type_text} Report for {site_name}
========================================

Website: {site_url}
Check Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
Status: {check_results.get('status', 'Completed')}

CHECK RESULTS SUMMARY:
======================
- Pages Crawled: {check_results.get('crawl_stats', {}).get('pages_crawled', 0)}
- Broken Links: {len(check_results.get('broken_links', []))}
- Missing Meta Tags: {len(check_results.get('missing_meta_tags', []))}
- Visual Snapshots: {len(check_results.get('visual_baselines', []) or check_results.get('latest_snapshots', {}))}
- Blur Issues: {check_results.get('blur_detection_summary', {}).get('blurry_images', 0)}
- Performance Checks: {check_results.get('performance_check', {}).get('performance_check_summary', {}).get('pages_analyzed', 0)}

DETAILED CHECK RESULTS:
=======================

🌐 CRAWL CHECK RESULTS:
- Pages Crawled: {check_results.get('crawl_stats', {}).get('pages_crawled', 0)}
- Total Links Found: {check_results.get('crawl_stats', {}).get('total_links', 0)}
- Total Images Found: {check_results.get('crawl_stats', {}).get('total_images', 0)}
- Sitemap Found: {'Yes' if check_results.get('crawl_stats', {}).get('sitemap_found', False) else 'No'}
{f'- Broken Links: {len(check_results.get("broken_links", []))} found' if len(check_results.get('broken_links', [])) > 0 else ''}
{f'- Missing Meta Tags: {len(check_results.get("missing_meta_tags", []))} found' if len(check_results.get('missing_meta_tags', [])) > 0 else ''}

📸 VISUAL CHECK RESULTS:
- Snapshots Captured: {len(check_results.get('visual_baselines', []) or check_results.get('latest_snapshots', {}))}
- Visual Changes Detected: {'Yes' if check_results.get('significant_change_detected', False) else 'No'}
{f'- Visual Difference Score: {check_results.get("visual_diff_percent", 0):.2f}%' if check_results.get('visual_diff_percent') else ''}
{f'- Baseline Comparison: {"Completed" if check_results.get("baseline_comparison_completed", False) else "No baseline available"}'}

🔍 BLUR DETECTION RESULTS:
- Images Analyzed: {check_results.get('blur_detection_summary', {}).get('total_images_processed', 0)}
- Blur Issues Found: {check_results.get('blur_detection_summary', {}).get('blurry_images', 0)}
{f'- Blur Percentage: {check_results.get("blur_detection_summary", {}).get("blur_percentage", 0)}%' if check_results.get('blur_detection_summary', {}).get('blur_percentage') else ''}
{f'- Total Images Found: {check_results.get("blur_detection_summary", {}).get("total_images_found", 0)}' if check_results.get('blur_detection_summary', {}).get('total_images_found') else ''}

⚡ PERFORMANCE CHECK RESULTS:
- Pages Checked: {check_results.get('performance_check', {}).get('performance_check_summary', {}).get('pages_analyzed', 0)}
{f'- Average Mobile Score: {check_results.get("performance_check", {}).get("performance_check_summary", {}).get("avg_mobile_score", 0)}/100' if check_results.get('performance_check', {}).get('performance_check_summary', {}).get('avg_mobile_score') else ''}
{f'- Average Desktop Score: {check_results.get("performance_check", {}).get("performance_check_summary", {}).get("avg_desktop_score", 0)}/100' if check_results.get('performance_check', {}).get('performance_check_summary', {}).get('avg_desktop_score') else ''}
{f'- Slowest Page: {check_results.get("performance_check", {}).get("performance_check_summary", {}).get("slowest_page", "N/A")}' if check_results.get('performance_check', {}).get('performance_check_summary', {}).get('slowest_page') else ''}
{f'- Performance Issues: {check_results.get("performance_check", {}).get("performance_check_summary", {}).get("total_issues", 0)} found' if check_results.get('performance_check', {}).get('performance_check_summary', {}).get('total_issues', 0) > 0 else ''}

QUICK ACTIONS:
==============
- View History: {dashboard_url}/website/history/{check_results.get('site_id', check_results.get('website_id'))}
- View Dashboard: {dashboard_url}/website/{check_results.get('site_id', check_results.get('website_id'))}
- View Crawler Results: {dashboard_url}/website/{check_results.get('site_id', check_results.get('website_id'))}/crawler

This is an automated report from your Website Monitoring System.
Visit Dashboard: {dashboard_url}
    """

def send_report(website: dict, check_results: dict):
    """
    Analyzes check results and sends the appropriate detailed email report.
    Now supports different templates based on check type and includes website name in subject.
    """
    logger.info(f"EMAIL DEBUG - send_report called for {website.get('name', 'N/A')}")
    
    site_name = website.get('name', 'N/A')
    site_url = website.get('url', 'N/A')
    recipient_emails = website.get('notification_emails', [])
    
    # Debug logging to see what data we're working with
    logger.info(f"EMAIL DEBUG - Site: {site_name}")
    logger.info(f"EMAIL DEBUG - Check results keys: {list(check_results.keys())}")
    logger.info(f"EMAIL DEBUG - Crawl stats: {check_results.get('crawl_stats', {})}")
    logger.info(f"EMAIL DEBUG - Broken links count: {len(check_results.get('broken_links', []))}")
    logger.info(f"EMAIL DEBUG - Missing meta tags count: {len(check_results.get('missing_meta_tags', []))}")
    logger.info(f"EMAIL DEBUG - Recipient emails: {recipient_emails}")
    
    # Determine check type and create appropriate subject and content
    check_type = _determine_check_type(check_results)
    is_change_report = check_results.get('significant_change_detected', False)
    
    # Create specific subject based on check type
    subject = _create_subject(site_name, check_type, is_change_report, check_results)

    # Get dashboard URL - prioritize environment variable for Dokploy
    config = get_config_dynamic()
    dashboard_url = os.environ.get('DASHBOARD_URL') or config.get('dashboard_url', 'http://localhost:5001')
    
    # Log the dashboard URL being used for debugging
    logger.info(f"Using dashboard URL: {dashboard_url}")
    
    # Ensure we have a valid dashboard URL
    if not dashboard_url or dashboard_url == 'http://localhost:5001':
        logger.warning("No valid DASHBOARD_URL environment variable set. Using localhost fallback.")
        dashboard_url = 'http://localhost:5001'
    
    # Create check-type specific HTML email body
    html_body = _create_email_content(site_name, site_url, check_type, check_results, dashboard_url)
    
    # Create check-type specific text version
    text_body = _create_text_content(site_name, site_url, check_type, check_results, dashboard_url)

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
    logger.info(f"EMAIL DEBUG - About to send email for {site_name} to {target_recipients}")
    try:
        result = send_email_alert(subject, html_body, text_body, target_recipients)
        logger.info(f"EMAIL DEBUG - Email sending result: {result}")
        return result
    except Exception as e:
        logger.error(f"Failed to send email report for {site_name}: {e}")
        return False

def send_email_alert(subject: str, body_html: str, body_text: str = None, recipient_emails: list = None, attachments: list = None):
    """
    Sends an email alert using SMTP settings from the configuration.
    Simplified version for better reliability.
    """
    logger.info(f"EMAIL DEBUG - send_email_alert called with subject: {subject}")
    logger.info(f"EMAIL DEBUG - Recipients: {recipient_emails}")
    
    try:
        config = get_config_dynamic()
        logger.info(f"EMAIL DEBUG - Config loaded: {bool(config)}")
        
        # Get email configuration with environment variable overrides
        smtp_server = os.environ.get('SMTP_SERVER') or config.get('smtp_server')
        smtp_port = int(os.environ.get('SMTP_PORT', config.get('smtp_port', 587)))
        smtp_username = os.environ.get('SMTP_USERNAME') or config.get('smtp_username')
        smtp_password = os.environ.get('SMTP_PASSWORD') or config.get('smtp_password')
        from_email = os.environ.get('NOTIFICATION_EMAIL_FROM') or config.get('notification_email_from')
        use_tls = os.environ.get('SMTP_USE_TLS', str(config.get('smtp_use_tls', True))).lower() == 'true'
        use_ssl = os.environ.get('SMTP_USE_SSL', str(config.get('smtp_use_ssl', False))).lower() == 'true'
        
        # Log the SMTP configuration being used
        logger.info(f"EMAIL DEBUG - SMTP Server: {smtp_server}:{smtp_port}")
        logger.info(f"EMAIL DEBUG - SMTP Auth: {smtp_username}")
        logger.info(f"EMAIL DEBUG - SMTP TLS: {use_tls}, SSL: {use_ssl}")
        
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

        # Send email with fallback servers
        fallback_servers = [
            (smtp_server, smtp_port, use_tls, use_ssl),  # Primary server
            ('smtp.gmail.com', 587, True, False),        # Gmail fallback
            ('smtp.outlook.com', 587, True, False),       # Outlook fallback
        ]
        
        for server_host, server_port, server_tls, server_ssl in fallback_servers:
            try:
                logger.info(f"EMAIL DEBUG - Attempting connection to {server_host}:{server_port}")
                
                if server_ssl:
                    server = smtplib.SMTP_SSL(server_host, server_port, timeout=10)
                else:
                    server = smtplib.SMTP(server_host, server_port, timeout=10)
                    if server_tls:
                        server.starttls()
                
                # Only try to login if we have credentials for this server
                if server_host == smtp_server:
                    server.login(smtp_username, smtp_password)
                else:
                    logger.warning(f"EMAIL DEBUG - Skipping login for fallback server {server_host} (no credentials)")
                    continue
                
                server.send_message(msg)
                server.quit()
                
                logger.info(f"Email sent successfully to {', '.join(recipient_emails)} via {server_host}:{server_port}")
                return True
                
            except Exception as e:
                logger.warning(f"EMAIL DEBUG - Failed to send via {server_host}:{server_port}: {e}")
                continue
        
        logger.error("Failed to send email via all servers")
        return False
        
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False

# Simplified versions of other email functions
def _send_visual_check_email(website: dict, check_record: dict):
    """Send visual check email with simple HTML."""
    check_record['is_manual'] = True
    return send_report(website, check_record)

def _send_crawl_check_email(website: dict, check_record: dict):
    """Send crawl check email with simple HTML."""
    check_record['is_manual'] = True
    return send_report(website, check_record)

def _send_blur_check_email(website: dict, check_record: dict):
    """Send blur check email with simple HTML."""
    check_record['is_manual'] = True
    return send_report(website, check_record)

def send_performance_email(website: dict, check_record: dict):
    """Send performance email with simple HTML."""
    check_record['is_manual'] = True
    return send_report(website, check_record)

def _send_baseline_check_email(website: dict, check_record: dict):
    """Send baseline check email with simple HTML."""
    check_record['is_manual'] = True
    return send_report(website, check_record)

def _send_full_check_email(website: dict, check_record: dict):
    """Send full check email with simple HTML."""
    check_record['is_manual'] = True
    return send_report(website, check_record)
