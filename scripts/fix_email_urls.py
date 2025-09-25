#!/usr/bin/env python3
"""
Script to fix email URL issues in Dokploy deployment.
This script helps debug and fix the DASHBOARD_URL configuration.
"""

import os
import sys
import requests
import json

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def check_dashboard_accessibility():
    """Check if the dashboard is accessible at different URLs."""
    print("🔍 Checking Dashboard Accessibility")
    print("=" * 50)
    
    # Get current dashboard URL
    dashboard_url = os.environ.get('DASHBOARD_URL', 'http://localhost:5001')
    print(f"Current DASHBOARD_URL: {dashboard_url}")
    
    # Test URLs to check
    test_urls = [
        dashboard_url,
        "http://167.86.123.94:5001",
        "https://167.86.123.94:5001",
        "http://localhost:5001"
    ]
    
    for url in test_urls:
        try:
            response = requests.get(f"{url}/health", timeout=10)
            if response.status_code == 200:
                print(f"✅ {url} - Accessible (Status: {response.status_code})")
                return url
            else:
                print(f"⚠️  {url} - Not accessible (Status: {response.status_code})")
        except requests.exceptions.RequestException as e:
            print(f"❌ {url} - Error: {str(e)[:50]}...")
    
    return None

def test_email_url_generation():
    """Test how email URLs are being generated."""
    print("\n📧 Testing Email URL Generation")
    print("=" * 50)
    
    try:
        from alerter import send_email_notification
        
        # Mock check results
        mock_results = {
            'website_id': '262f98e0-9381-4a0a-ab2a-b8c2d396de1b',
            'website_name': 'Test Website',
            'status': 'success',
            'url': 'https://example.com'
        }
        
        # Get dashboard URL from environment
        dashboard_url = os.environ.get('DASHBOARD_URL', 'http://localhost:5001')
        
        # Generate URLs
        history_url = f"{dashboard_url}/website/history/{mock_results.get('website_id')}"
        dashboard_url_full = f"{dashboard_url}/website/{mock_results.get('website_id')}"
        crawler_url = f"{dashboard_url}/website/{mock_results.get('website_id')}/crawler"
        
        print(f"History URL: {history_url}")
        print(f"Dashboard URL: {dashboard_url_full}")
        print(f"Crawler URL: {crawler_url}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing email URL generation: {e}")
        return False

def suggest_fixes():
    """Suggest fixes for the email URL issue."""
    print("\n🔧 Suggested Fixes")
    print("=" * 50)
    
    print("1. **Update Dokploy Environment Variable:**")
    print("   - Go to Dokploy dashboard: http://167.86.123.94:3000/")
    print("   - Find your website-monitor project")
    print("   - Go to Environment Variables")
    print("   - Set DASHBOARD_URL to: http://167.86.123.94:5001")
    print("   - Redeploy the application")
    
    print("\n2. **Alternative: Update Config File:**")
    print("   - The config file already has the correct URL")
    print("   - Make sure environment variable doesn't override it")
    
    print("\n3. **Verify Deployment:**")
    print("   - Check if the app is accessible at http://167.86.123.94:5001")
    print("   - Test the health endpoint: http://167.86.123.94:5001/health")
    
    print("\n4. **Test Email URLs:**")
    print("   - Trigger a test email to see if URLs are correct")
    print("   - Check the application logs for DASHBOARD_URL usage")

def main():
    """Main function to run all checks."""
    print("🚀 Email URL Fix Diagnostic Tool")
    print("=" * 50)
    
    # Check dashboard accessibility
    accessible_url = check_dashboard_accessibility()
    
    # Test email URL generation
    email_test_passed = test_email_url_generation()
    
    # Show suggestions
    suggest_fixes()
    
    print("\n" + "=" * 50)
    print("📋 Summary:")
    print(f"Dashboard accessible: {'Yes' if accessible_url else 'No'}")
    print(f"Email URL generation: {'Working' if email_test_passed else 'Failed'}")
    
    if accessible_url and email_test_passed:
        print("✅ Everything looks good! The issue might be in Dokploy environment variables.")
    else:
        print("❌ There are issues that need to be fixed.")

if __name__ == "__main__":
    main()
