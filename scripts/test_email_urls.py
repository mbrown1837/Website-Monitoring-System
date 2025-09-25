#!/usr/bin/env python3
"""
Test script to verify email URL generation is working correctly.
"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_email_urls():
    """Test email URL generation with different environment configurations."""
    
    print("🧪 Testing Email URL Generation")
    print("=" * 50)
    
    # Test 1: With DASHBOARD_URL environment variable
    print("\n1. Testing with DASHBOARD_URL environment variable:")
    os.environ['DASHBOARD_URL'] = 'http://167.86.123.94:5001'
    
    from src.alerter import get_config_dynamic
    config = get_config_dynamic()
    dashboard_url = os.environ.get('DASHBOARD_URL') or config.get('dashboard_url', 'http://localhost:5001')
    print(f"   DASHBOARD_URL env: {os.environ.get('DASHBOARD_URL')}")
    print(f"   Final dashboard_url: {dashboard_url}")
    
    # Test 2: Without DASHBOARD_URL environment variable
    print("\n2. Testing without DASHBOARD_URL environment variable:")
    if 'DASHBOARD_URL' in os.environ:
        del os.environ['DASHBOARD_URL']
    
    config = get_config_dynamic()
    dashboard_url = os.environ.get('DASHBOARD_URL') or config.get('dashboard_url', 'http://localhost:5001')
    print(f"   DASHBOARD_URL env: {os.environ.get('DASHBOARD_URL')}")
    print(f"   Config dashboard_url: {config.get('dashboard_url')}")
    print(f"   Final dashboard_url: {dashboard_url}")
    
    # Test 3: Generate sample email URLs
    print("\n3. Sample email URLs:")
    website_id = "262f98e0-9381-4a0a-ab2a-b8c2d396de1b"
    print(f"   History URL: {dashboard_url}/website/history/{website_id}")
    print(f"   Dashboard URL: {dashboard_url}/website/{website_id}")
    print(f"   Crawler URL: {dashboard_url}/website/{website_id}/crawler")
    
    print("\n✅ Email URL test completed!")

if __name__ == "__main__":
    test_email_urls()
