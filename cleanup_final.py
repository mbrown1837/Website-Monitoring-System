#!/usr/bin/env python3
"""
Final cleanup script to remove all test websites and prepare for production
"""

import os
import sys

# Add src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.website_manager_sqlite import WebsiteManager
from src.scheduler_integration import clear_all_scheduler_tasks

def cleanup_system():
    """Remove all test websites and clear scheduler."""
    print("🧹 FINAL SYSTEM CLEANUP")
    print("=" * 40)
    print()
    
    website_manager = WebsiteManager(config_path='config/config.yaml')
    
    # Get all websites
    websites = website_manager.list_websites()
    
    if not websites:
        print("✅ No websites found - system is already clean!")
        return
    
    print(f"🗑️  Found {len(websites)} website(s) to remove:")
    
    for website_id, website_data in websites.items():
        name = website_data.get('name', 'Unnamed')
        url = website_data.get('url', 'No URL')
        print(f"   • {name} - {url}")
    
    print()
    
    # Remove all websites
    removed_count = 0
    for website_id, website_data in list(websites.items()):
        name = website_data.get('name', 'Unnamed')
        print(f"🗑️  Removing: {name}")
        
        success = website_manager.remove_website(website_id)
        if success:
            print(f"   ✅ Removed")
            removed_count += 1
        else:
            print(f"   ❌ Failed")
    
    print()
    
    # Clear scheduler tasks
    print("🧹 Clearing scheduler tasks...")
    try:
        clear_all_scheduler_tasks()
        print("   ✅ Scheduler cleared")
    except Exception as e:
        print(f"   ⚠️  {e}")
    
    print()
    print("=" * 40)
    print(f"✅ Cleanup complete! Removed {removed_count} website(s)")
    print("🚀 System is now ready for production!")
    print()

if __name__ == '__main__':
    cleanup_system()
