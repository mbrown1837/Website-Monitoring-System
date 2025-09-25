#!/usr/bin/env python3
"""
Comprehensive fix for Dokploy baseline image issues.
This script addresses the 'No baseline found' warnings and missing image files.
"""

import sqlite3
import os
import sys
import json
from pathlib import Path

def fix_dokploy_baseline_images():
    """Fix baseline image issues in Dokploy deployment."""
    
    # Database path (Dokploy uses /app/data/)
    db_path = "/app/data/website_monitor.db"
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found at: {db_path}")
        print("   This script should be run inside the Dokploy container")
        return False
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("🔍 Analyzing Dokploy baseline image issues...")
        
        # Get all websites with baseline data
        cursor.execute("""
            SELECT id, name, url, all_baselines 
            FROM websites 
            WHERE all_baselines IS NOT NULL AND all_baselines != '{}'
        """)
        websites = cursor.fetchall()
        
        print(f"📊 Found {len(websites)} websites with baseline data")
        
        fixed_count = 0
        missing_count = 0
        
        for site_id, name, url, all_baselines_json in websites:
            print(f"\n🔍 Processing: {name} ({url})")
            
            try:
                all_baselines = json.loads(all_baselines_json) if all_baselines_json else {}
            except json.JSONDecodeError:
                print(f"   ⚠️  Invalid JSON in all_baselines for {name}")
                continue
            
            if not all_baselines:
                print(f"   ℹ️  No baseline data for {name}")
                continue
            
            # Check each baseline
            updated_baselines = {}
            for baseline_url, baseline_info in all_baselines.items():
                baseline_path = baseline_info.get('path', '')
                
                if not baseline_path:
                    print(f"   ⚠️  No path for baseline: {baseline_url}")
                    continue
                
                # Check if file exists
                full_path = os.path.join('/app/data', baseline_path)
                if os.path.exists(full_path):
                    print(f"   ✅ Baseline exists: {baseline_path}")
                    updated_baselines[baseline_url] = baseline_info
                else:
                    print(f"   ❌ Missing baseline: {baseline_path}")
                    
                    # Try to find alternative paths
                    alternative_paths = [
                        baseline_path,
                        baseline_path.replace('/baseline_', '/baseline/baseline_'),
                        baseline_path.replace('/baseline/', '/'),
                        baseline_path.replace('baseline.png', 'home.png'),
                        baseline_path.replace('baseline.png', 'homepage.png'),
                        baseline_path.replace('baseline.jpg', 'home.jpg'),
                        baseline_path.replace('baseline.jpg', 'homepage.jpg')
                    ]
                    
                    found_alternative = False
                    for alt_path in alternative_paths:
                        alt_full_path = os.path.join('/app/data', alt_path)
                        if os.path.exists(alt_full_path):
                            print(f"   🔄 Found alternative: {alt_path}")
                            baseline_info['path'] = alt_path
                            updated_baselines[baseline_url] = baseline_info
                            found_alternative = True
                            break
                    
                    if not found_alternative:
                        print(f"   🗑️  No alternative found, removing baseline: {baseline_url}")
                        missing_count += 1
            
            # Update the database if we found alternatives
            if updated_baselines != all_baselines:
                updated_json = json.dumps(updated_baselines)
                cursor.execute("""
                    UPDATE websites 
                    SET all_baselines = ? 
                    WHERE id = ?
                """, (updated_json, site_id))
                
                print(f"   ✅ Updated baseline data for {name}")
                fixed_count += 1
        
        # Commit changes
        conn.commit()
        
        # Show summary
        print(f"\n📊 Summary:")
        print(f"   ✅ Fixed: {fixed_count} websites")
        print(f"   ❌ Missing: {missing_count} baselines")
        
        # Show remaining websites
        cursor.execute("SELECT name, url FROM websites ORDER BY name")
        remaining_sites = cursor.fetchall()
        
        print(f"\n📋 Remaining websites ({len(remaining_sites)}):")
        for name, url in remaining_sites:
            print(f"   - {name} ({url})")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error fixing baseline images: {e}")
        return False

def check_dokploy_snapshot_directory():
    """Check the Dokploy snapshot directory structure."""
    print("\n🔍 Checking Dokploy snapshot directory structure...")
    
    snapshot_dir = "/app/data/snapshots"
    if not os.path.exists(snapshot_dir):
        print(f"❌ Snapshot directory not found: {snapshot_dir}")
        return False
    
    # List all snapshot directories
    for site_dir in os.listdir(snapshot_dir):
        site_path = os.path.join(snapshot_dir, site_dir)
        if os.path.isdir(site_path):
            print(f"\n📁 Site: {site_dir}")
            
            # List all website IDs in this site
            for website_id in os.listdir(site_path):
                website_path = os.path.join(site_path, website_id)
                if os.path.isdir(website_path):
                    print(f"   📁 Website ID: {website_id}")
                    
                    # Check for baseline directory
                    baseline_dir = os.path.join(website_path, 'baseline')
                    if os.path.exists(baseline_dir):
                        baseline_files = os.listdir(baseline_dir)
                        print(f"      📸 Baseline files: {len(baseline_files)}")
                        for file in baseline_files[:5]:  # Show first 5 files
                            print(f"         - {file}")
                        if len(baseline_files) > 5:
                            print(f"         ... and {len(baseline_files) - 5} more")
                    else:
                        print(f"      ❌ No baseline directory")
    
    return True

def remove_quick_test_sites():
    """Remove Quick Test sites from Dokploy database."""
    print("\n🧹 Removing Quick Test sites from Dokploy database...")
    
    db_path = "/app/data/website_monitor.db"
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found at: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Find all 'Quick Test' sites
        cursor.execute("SELECT id, name, url FROM websites WHERE name LIKE '%Quick Test%'")
        quick_test_sites = cursor.fetchall()
        
        if not quick_test_sites:
            print("✅ No 'Quick Test' sites found in Dokploy database")
            return True
        
        print(f"🔍 Found {len(quick_test_sites)} 'Quick Test' sites:")
        for site_id, name, url in quick_test_sites:
            print(f"   - {name} ({url}) - ID: {site_id}")
        
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
            print("✅ All 'Quick Test' sites successfully deleted from Dokploy!")
        else:
            print(f"⚠️  Warning: {remaining_count} 'Quick Test' sites still remain")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error removing Quick Test sites: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Dokploy Baseline Images Fix")
    print("=" * 50)
    
    # Check snapshot directory first
    check_dokploy_snapshot_directory()
    
    # Remove Quick Test sites
    remove_quick_test_sites()
    
    # Fix baseline images
    success = fix_dokploy_baseline_images()
    
    if success:
        print("\n✅ Dokploy baseline image fix completed!")
    else:
        print("\n❌ Dokploy baseline image fix failed!")
        sys.exit(1)
