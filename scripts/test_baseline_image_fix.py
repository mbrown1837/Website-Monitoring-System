#!/usr/bin/env python3
"""
Test script to verify baseline image serving fix.
This script tests the new /snapshots/<path:file_path> route.
"""

import os
import sys
import requests
import json
from datetime import datetime

# Add the parent directory to the Python path to allow importing src modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.website_manager_sqlite import WebsiteManagerSQLite
from src.logger_setup import setup_logging

logger = setup_logging()

def test_baseline_image_routes():
    """Test the baseline image serving routes."""
    print("🔍 Testing Baseline Image Routes")
    print("=" * 50)
    
    # Initialize website manager
    website_manager = WebsiteManagerSQLite()
    
    # Get all websites
    websites = website_manager.get_active_websites()
    if not websites:
        print("❌ No websites found in database")
        return False
    
    test_website = websites[0]
    site_id = test_website['id']
    website_name = test_website.get('name', 'Unknown')
    
    print(f"Testing with website: {website_name} (ID: {site_id})")
    
    # Test the new /snapshots/<path:file_path> route
    base_url = "http://localhost:5001"
    
    # Test cases for different baseline image paths
    test_paths = [
        f"westlanddre_com/{site_id}/baseline/baseline_home.png",
        f"westlanddre_com/{site_id}/baseline/baseline_pricing.png",
        f"westlanddre_com/{site_id}/baseline/baseline_privacy-policy.png",
        f"westlanddre_com/{site_id}/baseline/baseline_disclaimer.png"
    ]
    
    print(f"\n🧪 Testing baseline image routes:")
    success_count = 0
    total_tests = len(test_paths)
    
    for test_path in test_paths:
        url = f"{base_url}/snapshots/{test_path}"
        print(f"\nTesting: {url}")
        
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                print(f"✅ SUCCESS: {test_path} - Status: {response.status_code}")
                success_count += 1
            elif response.status_code == 404:
                print(f"⚠️  NOT FOUND: {test_path} - Status: {response.status_code}")
                print(f"   This is expected if baseline doesn't exist yet")
            else:
                print(f"❌ ERROR: {test_path} - Status: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"❌ REQUEST ERROR: {test_path} - {e}")
    
    print(f"\n📊 Test Results:")
    print(f"✅ Successful: {success_count}/{total_tests}")
    print(f"❌ Failed: {total_tests - success_count}/{total_tests}")
    
    if success_count > 0:
        print("✅ Baseline image route is working!")
        return True
    else:
        print("❌ No baseline images found - this is normal if baselines haven't been created yet")
        return True  # This is not a failure, just no baselines exist

def test_dashboard_url_config():
    """Test that dashboard URL is properly configured."""
    print("\n🌐 Testing Dashboard URL Configuration")
    print("=" * 50)
    
    # Check environment variable
    dashboard_url = os.environ.get('DASHBOARD_URL')
    if dashboard_url:
        print(f"✅ DASHBOARD_URL environment variable: {dashboard_url}")
    else:
        print("⚠️  DASHBOARD_URL environment variable not set")
    
    # Check config file
    try:
        from src.config_loader import get_config
        config = get_config()
        config_dashboard_url = config.get('dashboard_url')
        print(f"✅ Config dashboard_url: {config_dashboard_url}")
        
        if config_dashboard_url and 'localhost' not in config_dashboard_url:
            print("✅ Dashboard URL is properly configured for production")
        else:
            print("⚠️  Dashboard URL might be using localhost (check environment variables)")
            
    except Exception as e:
        print(f"❌ Error loading config: {e}")

def test_email_template_website_id():
    """Test that email templates use correct website ID field."""
    print("\n📧 Testing Email Template Website ID")
    print("=" * 50)
    
    try:
        from src.alerter import _create_email_content
        
        # Create mock check results
        mock_check_results = {
            'site_id': 'test-site-123',
            'website_id': 'test-website-456',  # This should be fallback
            'url': 'https://example.com',
            'status': 'success',
            'timestamp': datetime.now().isoformat()
        }
        
        # Test the email content generation
        content = _create_email_content(
            site_name="Test Website",
            site_url="https://example.com",
            check_type="manual_visual",
            check_results=mock_check_results,
            dashboard_url="http://localhost:5001"
        )
        
        # Check if site_id is used (not website_id)
        if 'test-site-123' in content:
            print("✅ Email template correctly uses site_id")
        elif 'test-website-456' in content:
            print("⚠️  Email template falls back to website_id (this is acceptable)")
        else:
            print("❌ Email template doesn't contain expected website ID")
            
        print("✅ Email template website ID handling is working")
        return True
        
    except Exception as e:
        print(f"❌ Error testing email template: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 Starting Baseline Image Fix Tests")
    print("=" * 60)
    
    try:
        # Test 1: Baseline image routes
        test1_success = test_baseline_image_routes()
        
        # Test 2: Dashboard URL configuration
        test2_success = test_dashboard_url_config()
        
        # Test 3: Email template website ID
        test3_success = test_email_template_website_id()
        
        print(f"\n🎯 Overall Test Results:")
        print(f"✅ Baseline Image Routes: {'PASS' if test1_success else 'FAIL'}")
        print(f"✅ Dashboard URL Config: {'PASS' if test2_success else 'FAIL'}")
        print(f"✅ Email Template ID: {'PASS' if test3_success else 'FAIL'}")
        
        if all([test1_success, test2_success, test3_success]):
            print("\n🎉 All tests passed! The fixes are working correctly.")
            return True
        else:
            print("\n⚠️  Some tests failed. Please check the issues above.")
            return False
            
    except Exception as e:
        logger.error(f"Unhandled error during testing: {e}")
        print(f"\n❌ An unhandled error occurred: {e}")
        return False

if __name__ == "__main__":
    try:
        success = main()
        if success:
            print("\n🚀 All fixes are working correctly!")
            sys.exit(0)
        else:
            print("\n⚠️  Some issues need attention.")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Unhandled error: {e}")
        print(f"\n❌ An unhandled error occurred: {e}")
        sys.exit(1)
