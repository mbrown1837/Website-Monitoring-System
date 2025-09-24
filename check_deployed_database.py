#!/usr/bin/env python3
"""
Script to check deployed database status
"""

import sys
import os
sys.path.append('/app')

def check_deployed_database():
    """Check what's in the deployed database"""
    print("🔍 Checking deployed database status...")
    
    try:
        from src.website_manager_sqlite import WebsiteManagerSQLite
        
        wm = WebsiteManagerSQLite()
        websites = wm.list_websites()
        
        print(f"📊 Total websites in database: {len(websites)}")
        
        active_count = 0
        for site_id, website in websites.items():
            is_active = website.get('is_active', False)
            if is_active:
                active_count += 1
                print(f"  ✅ {website.get('name', 'Unknown')} - Active")
            else:
                print(f"  ❌ {website.get('name', 'Unknown')} - Inactive")
        
        print(f"\n📈 Active websites: {active_count}/{len(websites)}")
        
        # Check intervals
        print("\n⏰ Website intervals:")
        for site_id, website in websites.items():
            if website.get('is_active', False):
                interval = website.get('interval')
                check_interval_minutes = website.get('check_interval_minutes')
                print(f"  - {website.get('name', 'Unknown')}: interval={interval}, check_interval_minutes={check_interval_minutes}")
        
        return True
        
    except Exception as e:
        print(f"❌ Database check failed: {e}")
        return False

if __name__ == "__main__":
    check_deployed_database()
