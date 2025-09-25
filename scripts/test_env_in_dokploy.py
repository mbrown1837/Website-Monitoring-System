#!/usr/bin/env python3
"""
Quick test to verify environment variables in Dokploy.
Run this in your Dokploy container to check if DASHBOARD_URL is being read correctly.
"""

import os
import sys

def test_environment():
    """Test environment variables."""
    print("🔍 Environment Variable Test")
    print("=" * 40)
    
    # Check DASHBOARD_URL
    dashboard_url = os.environ.get('DASHBOARD_URL')
    print(f"DASHBOARD_URL: {dashboard_url}")
    
    if dashboard_url == 'http://167.86.123.94:5001':
        print("✅ DASHBOARD_URL is correct!")
    else:
        print("❌ DASHBOARD_URL is not set correctly")
        print(f"   Expected: http://167.86.123.94:5001")
        print(f"   Got: {dashboard_url}")
    
    # Check other variables
    print(f"\nSCHEDULER_ENABLED: {os.environ.get('SCHEDULER_ENABLED')}")
    print(f"LOG_LEVEL: {os.environ.get('LOG_LEVEL')}")
    print(f"SECRET_KEY: {os.environ.get('SECRET_KEY', 'Not set')[:20]}...")
    
    # Test email URL generation
    print(f"\n📧 Email URL Test:")
    website_id = "262f98e0-9381-4a0a-ab2a-b8c2d396de1b"
    history_url = f"{dashboard_url}/website/history/{website_id}"
    print(f"History URL: {history_url}")
    
    return dashboard_url == 'http://167.86.123.94:5001'

if __name__ == "__main__":
    success = test_environment()
    if success:
        print("\n✅ Environment variables are correct!")
        print("If emails still show wrong URLs, the issue might be:")
        print("1. App needs to be restarted after env var change")
        print("2. Cached email templates")
        print("3. Old check results in database")
    else:
        print("\n❌ Environment variables need to be fixed!")
