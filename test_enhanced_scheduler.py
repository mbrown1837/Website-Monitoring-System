#!/usr/bin/env python3
"""
Test script for Enhanced Scheduler
"""

import sys
import os
sys.path.append('src')

from src.enhanced_scheduler import EnhancedScheduler, get_enhanced_scheduler_status
import time
import json

def test_enhanced_scheduler():
    """Test the enhanced scheduler"""
    
    print("=== ENHANCED SCHEDULER TEST ===")
    print()
    
    # 1. Test scheduler creation
    print("1. TESTING SCHEDULER CREATION:")
    try:
        scheduler = EnhancedScheduler()
        print("   ✅ Enhanced Scheduler created successfully")
    except Exception as e:
        print(f"   ❌ Failed to create scheduler: {e}")
        return
    
    print()
    
    # 2. Test scheduler start
    print("2. TESTING SCHEDULER START:")
    try:
        success = scheduler.start()
        if success:
            print("   ✅ Enhanced Scheduler started successfully")
        else:
            print("   ❌ Failed to start scheduler")
            return
    except Exception as e:
        print(f"   ❌ Error starting scheduler: {e}")
        return
    
    print()
    
    # 3. Test status
    print("3. TESTING SCHEDULER STATUS:")
    try:
        status = scheduler.get_status()
        print(f"   Status: {json.dumps(status, indent=2)}")
        
        if status['running']:
            print("   ✅ Scheduler is running")
        else:
            print("   ❌ Scheduler is not running")
            
        if status['scheduled_websites'] > 0:
            print(f"   ✅ {status['scheduled_websites']} websites scheduled")
        else:
            print("   ❌ No websites scheduled")
            
    except Exception as e:
        print(f"   ❌ Error getting status: {e}")
    
    print()
    
    # 4. Test force reschedule
    print("4. TESTING FORCE RESCHEDULE:")
    try:
        success = scheduler.force_reschedule()
        if success:
            print("   ✅ Force reschedule successful")
        else:
            print("   ❌ Force reschedule failed")
    except Exception as e:
        print(f"   ❌ Error during force reschedule: {e}")
    
    print()
    
    # 5. Test status after reschedule
    print("5. TESTING STATUS AFTER RESCHEDULE:")
    try:
        status = scheduler.get_status()
        print(f"   Active jobs: {status['active_jobs']}")
        print(f"   Scheduled websites: {status['scheduled_websites']}")
        if status['next_run']:
            print(f"   Next run: {status['next_run']}")
    except Exception as e:
        print(f"   ❌ Error getting status after reschedule: {e}")
    
    print()
    
    # 6. Test scheduler stop
    print("6. TESTING SCHEDULER STOP:")
    try:
        scheduler.stop()
        print("   ✅ Enhanced Scheduler stopped successfully")
    except Exception as e:
        print(f"   ❌ Error stopping scheduler: {e}")
    
    print()
    print("=== ENHANCED SCHEDULER TEST COMPLETE ===")

if __name__ == "__main__":
    test_enhanced_scheduler()
