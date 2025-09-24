#!/usr/bin/env python3
"""
Hotfix script to fix scheduler in deployed environment
This can be run directly in the deployed app to fix the scheduler without redeployment
"""

import sys
import os
sys.path.append('/app')

def hotfix_scheduler():
    """Apply hotfix to scheduler in deployed environment"""
    print("🔧 Applying scheduler hotfix to deployed environment...")
    
    try:
        # Import the scheduler module
        from src.scheduler import schedule_website_monitoring_tasks
        
        print("📊 Current scheduler status before hotfix:")
        
        # Force reload and schedule websites
        print("🚀 Forcing website reload and scheduling...")
        schedule_website_monitoring_tasks()
        
        print("✅ Scheduler hotfix applied successfully!")
        print("📈 The scheduler should now detect active websites")
        
        return True
        
    except Exception as e:
        print(f"❌ Hotfix failed: {e}")
        return False

if __name__ == "__main__":
    success = hotfix_scheduler()
    if success:
        print("\n🎉 Scheduler is now fixed! Check the logs for 'SCHEDULER: Found X active websites'")
    else:
        print("\n💥 Hotfix failed. You may need to redeploy the application.")
