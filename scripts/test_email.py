#!/usr/bin/env python3
"""
Test email functionality with current configuration.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.alerter import send_email_alert
from src.config_loader import get_config
from src.logger_setup import setup_logging

logger = setup_logging()

def test_email():
    """Test email sending functionality."""
    print("🧪 Testing Email Functionality")
    print("=" * 50)
    
    # Test data
    test_website = {
        'name': 'Test Website',
        'url': 'https://example.com',
        'notification_emails': []  # Empty to test default email
    }
    
    test_results = {
        'website_id': 'test-123',
        'url': 'https://example.com',
        'timestamp': '2025-09-26T05:00:00',
        'broken_links': [],
        'missing_meta_tags': [],
        'crawl_stats': {
            'pages_crawled': 1,
            'total_links': 1,
            'total_images': 0
        },
        'blur_detection_summary': {
            'blurry_images': 0
        },
        'performance_check': {
            'performance_check_summary': {
                'pages_analyzed': 1
            }
        }
    }
    
    # Test 1: Send via alerter module
    print("\n📧 Test 1: Sending test email via alerter module...")
    try:
        from src.alerter import send_report
        success = send_report(test_website, test_results)
        if success:
            print("✅ Email sent successfully!")
        else:
            print("❌ Email sending failed")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 2: Test SMTP connection directly
    print("\n🔌 Test 2: Testing SMTP connection...")
    try:
        import smtplib
        config = get_config()
        
        smtp_server = config.get('smtp_server')
        smtp_port = config.get('smtp_port', 587)
        smtp_username = config.get('smtp_username')
        
        print(f"SMTP Server: {smtp_server}:{smtp_port}")
        print(f"SMTP Username: {smtp_username}")
        
        # Test connection
        if config.get('smtp_use_ssl'):
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=10)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
            if config.get('smtp_use_tls'):
                server.starttls()
        
        print("✅ SMTP connection successful")
        server.quit()
        
    except Exception as e:
        print(f"❌ SMTP connection failed: {e}")
    
    # Test 3: Show configuration
    print("\n⚙️ Test 3: Current email configuration...")
    config = get_config()
    print(f"SMTP Server: {config.get('smtp_server')}")
    print(f"SMTP Port: {config.get('smtp_port')}")
    print(f"SMTP Username: {config.get('smtp_username')}")
    print(f"SMTP TLS: {config.get('smtp_use_tls')}")
    print(f"SMTP SSL: {config.get('smtp_use_ssl')}")
    print(f"From Email: {config.get('notification_email_from')}")
    print(f"Default Email: {config.get('default_notification_email')}")
    
    print("\n" + "=" * 50)
    print("🏁 Email test completed!")

if __name__ == "__main__":
    test_email()
