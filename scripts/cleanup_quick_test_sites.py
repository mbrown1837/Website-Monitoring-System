#!/usr/bin/env python3
"""
Clean up 'Quick Test' sites from the database.
This script removes all websites with 'Quick Test' in the name.
"""

import sqlite3
import os
import sys

def cleanup_quick_test_sites():
    """Remove all 'Quick Test' sites from the database."""
    
    # Database path
    db_path = "data/website_monitor.db"
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found at: {db_path}")
        return False
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Find all 'Quick Test' sites
        cursor.execute("SELECT id, name, url FROM websites WHERE name LIKE '%Quick Test%'")
        quick_test_sites = cursor.fetchall()
        
        if not quick_test_sites:
            print("✅ No 'Quick Test' sites found in database")
            return True
        
        print(f"🔍 Found {len(quick_test_sites)} 'Quick Test' sites:")
        for site_id, name, url in quick_test_sites:
            print(f"   - {name} ({url}) - ID: {site_id}")
        
        # Confirm deletion
        print(f"\n🗑️  Deleting {len(quick_test_sites)} 'Quick Test' sites...")
        
        # Delete from all related tables
        for site_id, name, url in quick_test_sites:
            print(f"   Deleting: {name}")
            
            # Delete from websites table
            cursor.execute("DELETE FROM websites WHERE id = ?", (site_id,))
            
            # Delete from check_history
            cursor.execute("DELETE FROM check_history WHERE site_id = ?", (site_id,))
            
            # Delete from crawl_history
            cursor.execute("DELETE FROM crawl_history WHERE site_id = ?", (site_id,))
            
            # Delete from crawl_results
            cursor.execute("DELETE FROM crawl_results WHERE site_id = ?", (site_id,))
            
            # Delete from broken_links
            cursor.execute("DELETE FROM broken_links WHERE site_id = ?", (site_id,))
            
            # Delete from missing_meta_tags
            cursor.execute("DELETE FROM missing_meta_tags WHERE site_id = ?", (site_id,))
            
            # Delete from blur_detection_results
            cursor.execute("DELETE FROM blur_detection_results WHERE site_id = ?", (site_id,))
            
            # Delete from performance_results
            cursor.execute("DELETE FROM performance_results WHERE site_id = ?", (site_id,))
        
        # Commit changes
        conn.commit()
        
        # Verify deletion
        cursor.execute("SELECT COUNT(*) FROM websites WHERE name LIKE '%Quick Test%'")
        remaining_count = cursor.fetchone()[0]
        
        if remaining_count == 0:
            print("✅ All 'Quick Test' sites successfully deleted!")
        else:
            print(f"⚠️  Warning: {remaining_count} 'Quick Test' sites still remain")
        
        # Show remaining sites
        cursor.execute("SELECT name, url FROM websites ORDER BY name")
        remaining_sites = cursor.fetchall()
        
        print(f"\n📋 Remaining websites ({len(remaining_sites)}):")
        for name, url in remaining_sites:
            print(f"   - {name} ({url})")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error cleaning up Quick Test sites: {e}")
        return False

if __name__ == "__main__":
    print("🧹 Quick Test Sites Cleanup")
    print("=" * 40)
    
    success = cleanup_quick_test_sites()
    
    if success:
        print("\n✅ Cleanup completed successfully!")
    else:
        print("\n❌ Cleanup failed!")
        sys.exit(1)
