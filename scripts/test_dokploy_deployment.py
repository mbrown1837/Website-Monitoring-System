#!/usr/bin/env python3
"""
Dokploy Deployment Test Script
Tests if the application is running correctly in Dokploy
"""

import requests
import sys
import time
import os

def test_deployment():
    """Test if the application is accessible and working"""
    
    print("🔍 Testing Dokploy Deployment")
    print("=" * 50)
    
    # Test URLs to try
    test_urls = [
        "http://localhost:5001",
        "http://127.0.0.1:5001", 
        "http://167.86.123.94:5001",
        "https://websitemonitor.digitalclics.com"
    ]
    
    for url in test_urls:
        print(f"\n🌐 Testing: {url}")
        try:
            # Test health endpoint
            health_url = f"{url}/health"
            response = requests.get(health_url, timeout=10)
            
            if response.status_code == 200:
                print(f"✅ Health check passed: {response.json()}")
                
                # Test main page
                main_response = requests.get(url, timeout=10)
                if main_response.status_code == 200:
                    print(f"✅ Main page accessible")
                    print(f"🎉 Application is working at: {url}")
                    return True
                else:
                    print(f"❌ Main page failed: {main_response.status_code}")
            else:
                print(f"❌ Health check failed: {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print(f"❌ Connection refused - service not running")
        except requests.exceptions.Timeout:
            print(f"❌ Request timeout - service not responding")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print(f"\n❌ All tests failed - application not accessible")
    return False

def check_environment():
    """Check environment variables"""
    print(f"\n🔧 Environment Check")
    print("=" * 30)
    
    env_vars = [
        'DASHBOARD_URL',
        'SMTP_SERVER', 
        'SMTP_PORT',
        'SMTP_USERNAME',
        'SECRET_KEY',
        'SCHEDULER_ENABLED'
    ]
    
    for var in env_vars:
        value = os.environ.get(var, 'NOT SET')
        if var in ['SMTP_PASSWORD']:
            value = '***HIDDEN***' if value != 'NOT SET' else 'NOT SET'
        print(f"{var}: {value}")

if __name__ == "__main__":
    print("🚀 Dokploy Deployment Test")
    print("=" * 50)
    
    check_environment()
    
    success = test_deployment()
    
    if success:
        print(f"\n🎉 Deployment test PASSED!")
        sys.exit(0)
    else:
        print(f"\n❌ Deployment test FAILED!")
        print(f"\n📋 Troubleshooting steps:")
        print(f"1. Check container logs: docker logs <container_name>")
        print(f"2. Verify port mapping in Dokploy")
        print(f"3. Check DNS configuration")
        print(f"4. Review environment variables")
        sys.exit(1)
