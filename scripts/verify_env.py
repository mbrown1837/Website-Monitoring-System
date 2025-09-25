#!/usr/bin/env python3
"""
Script to verify environment variables in Dokploy deployment.
This helps debug the DASHBOARD_URL issue.
"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def verify_environment():
    """Verify environment variables are set correctly."""
    print("🔍 Environment Variable Verification")
    print("=" * 50)
    
    # Check DASHBOARD_URL
    dashboard_url = os.environ.get('DASHBOARD_URL')
    print(f"DASHBOARD_URL: {dashboard_url}")
    
    if not dashboard_url:
        print("❌ DASHBOARD_URL not set!")
        print("   Set it in Dokploy environment variables")
    elif dashboard_url == 'http://localhost:5001':
        print("⚠️  DASHBOARD_URL is using localhost fallback")
        print("   This means the environment variable is not set in Dokploy")
    else:
        print("✅ DASHBOARD_URL is set correctly")
    
    # Check other important variables
    print(f"\nSCHEDULER_ENABLED: {os.environ.get('SCHEDULER_ENABLED', 'Not set')}")
    print(f"FLASK_ENV: {os.environ.get('FLASK_ENV', 'Not set')}")
    print(f"LOG_LEVEL: {os.environ.get('LOG_LEVEL', 'Not set')}")
    
    # Check if we can import the config
    try:
        from config_loader import get_config_dynamic
        config = get_config_dynamic()
        print(f"\nConfig dashboard_url: {config.get('dashboard_url', 'Not set')}")
    except Exception as e:
        print(f"\nError loading config: {e}")
    
    print("\n" + "=" * 50)
    print("📝 To fix the email URL issue:")
    print("1. Go to Dokploy dashboard")
    print("2. Find your website-monitor project")
    print("3. Go to Environment Variables")
    print("4. Set DASHBOARD_URL to your actual domain")
    print("5. Redeploy the application")

if __name__ == "__main__":
    verify_environment()