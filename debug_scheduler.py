#!/usr/bin/env python3
"""
Debug script to investigate scheduler issues
"""

import sys
import os
sys.path.append('src')

from src.website_manager_sqlite import WebsiteManagerSQLite
from src.scheduler import schedule_website_monitoring_tasks
import schedule
import json

def debug_scheduler():
    """Debug the scheduler issue"""
    
    print("=== SCHEDULER DEBUG ANALYSIS ===")
    print()
    
    # 1. Check website manager
    print("1. CHECKING WEBSITE MANAGER:")
    wm = WebsiteManagerSQLite()
    
    # Force reload websites
    print("   - Forcing website reload...")
    wm._load_websites(force_reload=True)
    
    # Get all websites
    all_websites = wm.list_websites()
    print(f"   - Total websites loaded: {len(all_websites)}")
    
    # Check active websites
    active_websites = [site for site in all_websites.values() if site.get('is_active', True)]
    print(f"   - Active websites: {len(active_websites)}")
    
    for site in active_websites:
        print(f"     * {site.get('name')} (ID: {site.get('id')}) - Active: {site.get('is_active')} - Interval: {site.get('check_interval_minutes')} min")
    
    print()
    
    # 2. Check current schedule jobs
    print("2. CHECKING CURRENT SCHEDULE JOBS:")
    print(f"   - Current jobs: {len(schedule.jobs)}")
    
    for i, job in enumerate(schedule.jobs):
        print(f"     Job {i+1}: {job.job_func.__name__} - Next run: {job.next_run}")
    
    print()
    
    # 3. Test scheduler setup
    print("3. TESTING SCHEDULER SETUP:")
    print("   - Clearing existing schedules...")
    schedule.clear()
    
    print("   - Setting up new schedules...")
    try:
        schedule_website_monitoring_tasks()
        print(f"   - Jobs after setup: {len(schedule.jobs)}")
        
        for i, job in enumerate(schedule.jobs):
            print(f"     Job {i+1}: {job.job_func.__name__} - Next run: {job.next_run}")
            
    except Exception as e:
        print(f"   - ERROR setting up scheduler: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    
    # 4. Check database directly
    print("4. CHECKING DATABASE DIRECTLY:")
    import sqlite3
    
    try:
        with sqlite3.connect('data/website_monitor.db') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, url, is_active, check_interval_minutes FROM websites")
            rows = cursor.fetchall()
            
            print(f"   - Database rows: {len(rows)}")
            for row in rows:
                print(f"     * ID: {row[0]}, Name: {row[1]}, URL: {row[2]}, Active: {row[3]}, Interval: {row[4]}")
                
    except Exception as e:
        print(f"   - ERROR accessing database: {e}")
    
    print()
    print("=== DEBUG COMPLETE ===")

if __name__ == "__main__":
    debug_scheduler()
