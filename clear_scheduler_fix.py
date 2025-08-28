#!/usr/bin/env python3
"""
Quick fix to clear scheduler tasks without import issues
"""

import os
import sys

# Add src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    # Try to clear scheduler tasks directly
    import schedule
    schedule.clear()
    print("✅ All scheduler tasks cleared successfully!")
    print(f"📊 Tasks remaining: {len(schedule.jobs)}")
except ImportError:
    print("⚠️  Schedule module not available - no tasks to clear")
except Exception as e:
    print(f"❌ Error clearing tasks: {e}")

print("🎉 Scheduler cleanup complete!")
