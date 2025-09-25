#!/usr/bin/env python3
"""
Fix baseline image issues in the database and file system.
This script addresses the 'No baseline found' and missing image file issues.
"""

import sqlite3
import os
import sys
import json
from pathlib import Path

def fix_baseline_images():
    """Fix baseline image issues."""
    
    # Database path
    db_path = "data/website_monitor.db"
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found at: {db_path}")
        return False
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("🔍 Analyzing baseline image issues...")
        
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
                full_path = os.path.join('data', baseline_path)
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
                        alt_full_path = os.path.join('data', alt_path)
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

def check_snapshot_directory():
    """Check the snapshot directory structure."""
    print("\n🔍 Checking snapshot directory structure...")
    
    snapshot_dir = "data/snapshots"
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

if __name__ == "__main__":
    print("🔧 Baseline Images Fix")
    print("=" * 40)
    
    # Check snapshot directory first
    check_snapshot_directory()
    
    # Fix baseline images
    success = fix_baseline_images()
    
    if success:
        print("\n✅ Baseline image fix completed!")
    else:
        print("\n❌ Baseline image fix failed!")
        sys.exit(1)
