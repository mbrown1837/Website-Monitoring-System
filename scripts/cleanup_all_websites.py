#!/usr/bin/env python3
"""
Script to remove all websites from the application, keeping it fresh for deployment.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.website_manager_sqlite import WebsiteManagerSQLite
from src.logger_setup import setup_logging

logger = setup_logging()

def cleanup_all_websites():
    """Remove all websites from the application."""
    
    print("🧹 Starting Website Cleanup")
    print("=" * 50)
    
    # Initialize website manager
    website_manager = WebsiteManagerSQLite()
    
    # Get all websites (both active and inactive)
    all_websites_dict = website_manager._load_websites()
    all_websites = list(all_websites_dict.values())
    
    active_websites = [w for w in all_websites if w.get('is_active', False)]
    inactive_websites = [w for w in all_websites if not w.get('is_active', False)]
    
    print(f"Found {len(all_websites)} websites to remove")
    print(f"  - Active websites: {len(active_websites)}")
    print(f"  - Inactive websites: {len(inactive_websites)}")
    
    if not all_websites:
        print("✅ No websites found - application is already clean!")
        return True
    
    # Remove all websites
    success_count = 0
    error_count = 0
    
    for website in all_websites:
        website_id = website['id']
        website_name = website.get('name', 'Unknown')
        website_status = "Active" if website.get('is_active', True) else "Inactive"
        print(f"Removing {website_status} website: {website_name} (ID: {website_id})")
        
        try:
            success = website_manager.remove_website(website_id)
            if success:
                print(f"✅ Successfully removed {website_name}")
                success_count += 1
            else:
                print(f"❌ Failed to remove {website_name}")
                error_count += 1
        except Exception as e:
            print(f"❌ Error removing {website_name}: {e}")
            error_count += 1
    
    print(f"\n🎯 Website cleanup completed!")
    print(f"✅ Successfully removed: {success_count}")
    print(f"❌ Failed to remove: {error_count}")
    
    # Verify cleanup
    remaining_websites_dict = website_manager._load_websites()
    remaining_total = len(remaining_websites_dict)
    if remaining_total == 0:
        print("✅ Application is now clean - no websites remaining!")
        return True
    else:
        print(f"⚠️ Warning: {remaining_total} websites still remain")
        return False

if __name__ == "__main__":
    try:
        success = cleanup_all_websites()
        if success:
            print("\n🚀 Application is ready for fresh deployment!")
        else:
            print("\n⚠️ Some websites could not be removed. Check the errors above.")
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        import traceback
        traceback.print_exc()
