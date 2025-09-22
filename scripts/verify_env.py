#!/usr/bin/env python3
"""
Environment Variables Verification Script
Run this in your Coolify environment to verify all required variables are set.
"""

import os
import sys

def verify_environment_variables():
    """Verify all required environment variables are set."""
    print("🔍 Verifying Environment Variables...")
    print("=" * 50)
    
    required_vars = {
        'DASHBOARD_URL': 'Dashboard URL for email links',
        'SMTP_SERVER': 'SMTP server for email sending',
        'SMTP_PORT': 'SMTP port number',
        'SMTP_USERNAME': 'SMTP username/email',
        'SMTP_PASSWORD': 'SMTP password/app password',
        'SMTP_USE_SSL': 'Use SSL for SMTP (true/false)',
        'NOTIFICATION_EMAIL_FROM': 'From email address',
        'NOTIFICATION_EMAIL_TO': 'To email address',
        'FLASK_ENV': 'Flask environment (production/development)'
    }
    
    missing_vars = []
    present_vars = []
    
    for var, description in required_vars.items():
        value = os.environ.get(var)
        if value:
            # Mask sensitive values
            if 'PASSWORD' in var or 'USERNAME' in var:
                display_value = f"{'*' * (len(value) - 4)}{value[-4:]}" if len(value) > 4 else "***"
            else:
                display_value = value
            print(f"✅ {var}: {display_value}")
            present_vars.append(var)
        else:
            print(f"❌ {var}: NOT SET - {description}")
            missing_vars.append(var)
    
    print("=" * 50)
    print(f"📊 Summary: {len(present_vars)}/{len(required_vars)} variables set")
    
    if missing_vars:
        print(f"⚠️  Missing variables: {', '.join(missing_vars)}")
        print("\n🔧 Please add these variables in Coolify:")
        for var in missing_vars:
            print(f"   - {var}")
        return False
    else:
        print("🎉 All required environment variables are set!")
        return True

def test_smtp_connection():
    """Test SMTP connection if all variables are present."""
    try:
        import smtplib
        from email.mime.text import MIMEText
        
        smtp_server = os.environ.get('SMTP_SERVER')
        smtp_port = int(os.environ.get('SMTP_PORT', 587))
        smtp_username = os.environ.get('SMTP_USERNAME')
        smtp_password = os.environ.get('SMTP_PASSWORD')
        use_ssl = os.environ.get('SMTP_USE_SSL', 'false').lower() == 'true'
        
        print("\n🔗 Testing SMTP Connection...")
        print(f"Server: {smtp_server}:{smtp_port}")
        print(f"SSL: {use_ssl}")
        
        if use_ssl:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
        
        server.login(smtp_username, smtp_password)
        server.quit()
        
        print("✅ SMTP connection successful!")
        return True
        
    except Exception as e:
        print(f"❌ SMTP connection failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Website Monitoring System - Environment Verification")
    print("=" * 60)
    
    # Verify environment variables
    env_ok = verify_environment_variables()
    
    if env_ok:
        # Test SMTP connection
        smtp_ok = test_smtp_connection()
        
        if smtp_ok:
            print("\n🎉 All systems ready! Your application should work correctly.")
            sys.exit(0)
        else:
            print("\n⚠️  Environment variables are set, but SMTP connection failed.")
            print("   Please check your SMTP credentials.")
            sys.exit(1)
    else:
        print("\n❌ Please set the missing environment variables in Coolify.")
        sys.exit(1)
