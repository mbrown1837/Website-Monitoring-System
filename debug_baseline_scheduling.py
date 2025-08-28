#!/usr/bin/env python3
"""Debug script to check baseline and scheduling issues"""

import sys
import os

# Add src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.website_manager_sqlite import WebsiteManager
from src.config_loader import get_config

def debug_baseline_and_scheduling():
    """Check baseline and scheduling status"""
    print("🔍 DEBUGGING BASELINE & SCHEDULING ISSUES")
    print("=" * 50)
    
    config = get_config(config_path='config/config.yaml')
    website_manager = WebsiteManager(config_path='config/config.yaml')
    
    # Get all websites
    websites = website_manager.list_websites()
    
    if not websites:
        print("❌ No websites found!")
        return
    
    print(f"📊 Found {len(websites)} website(s):")
    print()
    
    for website_id, website_data in websites.items():
        name = website_data.get('name', 'Unnamed')
        is_active = website_data.get('is_active', False)
        baseline_visual_path = website_data.get('baseline_visual_path')
        baseline_captured_utc = website_data.get('baseline_captured_utc')
        check_interval_minutes = website_data.get('check_interval_minutes', 60)
        
        print(f"🌐 Website: {name}")
        print(f"   📋 ID: {website_id}")
        print(f"   🟢 Active: {is_active}")
        print(f"   ⏰ Interval: {check_interval_minutes} minutes")
        print(f"   📸 Baseline Path: {baseline_visual_path}")
        print(f"   📅 Baseline Captured: {baseline_captured_utc}")
        
        # Check if baseline file exists
        if baseline_visual_path:
            full_path = os.path.join(os.getcwd(), baseline_visual_path)
            file_exists = os.path.exists(full_path)
            print(f"   📁 Baseline File Exists: {file_exists}")
            if file_exists:
                file_size = os.path.getsize(full_path) / 1024  # KB
                print(f"   💾 File Size: {file_size:.1f} KB")
        else:
            print(f"   ❌ No baseline path recorded in database")
        
        print()
    
    # Check scheduling configuration
    print("⚙️ SCHEDULING CONFIGURATION:")
    print(f"   Default Interval: {config.get('default_monitoring_interval_minutes', 60)} minutes")
    print()
    
    # Check if sites would be scheduled
    active_websites = [site for site in websites.values() if site.get('is_active', True)]
    print(f"📈 SCHEDULING STATUS:")
    print(f"   Active websites for scheduling: {len(active_websites)}")
    
    if active_websites:
        print("   ✅ Scheduling should work")
        for site in active_websites:
            interval = site.get('check_interval_minutes', 60)
            print(f"   • {site.get('name')}: Every {interval} minutes")
    else:
        print("   ❌ No active websites - scheduling disabled")
        print("   💡 Websites need 'is_active': True to be scheduled")
    
    print()

if __name__ == '__main__':
    debug_baseline_and_scheduling()
