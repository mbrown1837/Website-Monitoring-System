#!/usr/bin/env python3
"""
Script to remove all websites from the Website Monitoring System

This script will:
1. List all current websites
2. Remove each website (including its scheduler tasks)
3. Provide confirmation of removal
"""

import os
import sys

# Add src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.website_manager_sqlite import WebsiteManager
from src.scheduler_integration import clear_all_scheduler_tasks
from src.logger_setup import setup_logging

def main():
    """Remove all websites from the monitoring system."""
    print("=" * 60)
    print("REMOVE ALL WEBSITES FROM MONITORING SYSTEM")
    print("=" * 60)
    print()
    
    # Initialize components
    logger = setup_logging()
    website_manager = WebsiteManager()
    
    # Get all websites
    print("🔍 Checking current websites...")
    websites = website_manager.list_websites()
    
    if not websites:
        print("✅ No websites found in the system.")
        print("✅ System is already clean!")
        return
    
    print(f"📋 Found {len(websites)} website(s) to remove:")
    print()
    
    # List all websites
    for website_id, website_data in websites.items():
        name = website_data.get('name', 'Unnamed Website')
        url = website_data.get('url', 'No URL')
        is_active = website_data.get('is_active', False)
        status = "🟢 Active" if is_active else "🔴 Inactive"
        print(f"  • {name} - {url} ({status})")
    
    print()
    
    # Confirmation
    response = input("⚠️  Are you sure you want to remove ALL websites? This cannot be undone! (yes/no): ")
    
    if response.lower() not in ['yes', 'y']:
        print("❌ Operation cancelled.")
        return
    
    print()
    print("🗑️  Starting removal process...")
    print()
    
    # Remove all websites
    removed_count = 0
    failed_count = 0
    
    # Create a list of website IDs to avoid dictionary changing during iteration
    website_list = list(websites.items())
    
    for website_id, website_data in website_list:
        name = website_data.get('name', 'Unnamed Website')
        print(f"🗑️  Removing: {name} (ID: {website_id})")
        
        try:
            success = website_manager.remove_website(website_id)
            if success:
                print(f"   ✅ Successfully removed {name}")
                removed_count += 1
            else:
                print(f"   ❌ Failed to remove {name}")
                failed_count += 1
        except Exception as e:
            print(f"   ❌ Error removing {name}: {str(e)}")
            failed_count += 1
    
    print()
    
    # Clear all scheduler tasks
    print("🧹 Clearing all scheduler tasks...")
    try:
        success = clear_all_scheduler_tasks()
        if success:
            print("   ✅ All scheduler tasks cleared")
        else:
            print("   ⚠️  Could not clear scheduler tasks (scheduler may not be running)")
    except Exception as e:
        print(f"   ⚠️  Error clearing scheduler tasks: {str(e)}")
    
    print()
    print("=" * 60)
    print("REMOVAL SUMMARY")
    print("=" * 60)
    print(f"✅ Successfully removed: {removed_count} website(s)")
    if failed_count > 0:
        print(f"❌ Failed to remove: {failed_count} website(s)")
    print("🧹 Scheduler tasks cleared")
    print()
    
    if removed_count > 0:
        print("🎉 All websites have been removed from the monitoring system!")
        print("💡 You can now add new websites through the web interface or CLI.")
    else:
        print("⚠️  No websites were removed. Please check the logs for errors.")
    
    print()

if __name__ == '__main__':
    main()
