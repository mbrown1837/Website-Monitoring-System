#!/usr/bin/env python3
"""
Enhanced Scheduler with State Persistence and Error Recovery
"""

import schedule
import time
import json
import os
import threading
import signal
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import sqlite3

from src.website_manager_sqlite import WebsiteManagerSQLite
from src.history_manager_sqlite import HistoryManager
from src.config_loader import get_config
from src.logger_setup import setup_logging
from src.crawler_module import CrawlerModule
from src.alerter import send_report

logger = setup_logging()
config = get_config()

class EnhancedScheduler:
    """Enhanced scheduler with state persistence and error recovery"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.config = get_config(config_path) if config_path else get_config()
        self.logger = setup_logging(config_path) if config_path else setup_logging()
        
        # State persistence file
        self.state_file = "data/scheduler_state.json"
        self.lock_file = "data/scheduler.lock"
        
        # Managers
        self.website_manager = None
        self.history_manager = None
        self.crawler_module = None
        
        # Scheduler state
        self.scheduler_running = False
        self.scheduler_thread = None
        self.shutdown_event = threading.Event()
        self.last_schedule_time = None
        self.scheduled_websites = {}
        
        # Error recovery
        self.max_consecutive_errors = 5
        self.consecutive_errors = 0
        self.last_error_time = None
        
        # Initialize managers
        self._initialize_managers()
        
        # Load previous state
        self._load_state()
        
        # Setup signal handlers
        self._setup_signal_handlers()
    
    def _initialize_managers(self):
        """Initialize all required managers"""
        try:
            self.website_manager = WebsiteManagerSQLite()
            self.history_manager = HistoryManager()
            self.crawler_module = CrawlerModule()
            self.logger.info("Enhanced Scheduler: Managers initialized successfully")
        except Exception as e:
            self.logger.error(f"Enhanced Scheduler: Failed to initialize managers: {e}")
            raise
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        try:
            # Check if we're in the main thread
            import threading
            if threading.current_thread() is not threading.main_thread():
                self.logger.info("Enhanced Scheduler: Not in main thread, skipping signal handler setup")
                return
            
            def signal_handler(signum, frame):
                self.logger.info(f"Enhanced Scheduler: Received signal {signum}, initiating shutdown...")
                self.stop()
            
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            self.logger.info("Enhanced Scheduler: Signal handlers set up successfully")
        except ValueError as e:
            # Signal handlers can only be set in the main thread
            self.logger.warning(f"Enhanced Scheduler: Cannot set signal handlers in current thread: {e}")
        except Exception as e:
            self.logger.warning(f"Enhanced Scheduler: Failed to set up signal handlers: {e}")
    
    def _load_state(self):
        """Load scheduler state from file"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    self.last_schedule_time = state.get('last_schedule_time')
                    self.scheduled_websites = state.get('scheduled_websites', {})
                    self.consecutive_errors = state.get('consecutive_errors', 0)
                    self.last_error_time = state.get('last_error_time')
                self.logger.info("Enhanced Scheduler: State loaded from file")
            else:
                self.logger.info("Enhanced Scheduler: No previous state found, starting fresh")
        except Exception as e:
            self.logger.warning(f"Enhanced Scheduler: Failed to load state: {e}")
    
    def _save_state(self):
        """Save scheduler state to file"""
        try:
            state = {
                'last_schedule_time': self.last_schedule_time,
                'scheduled_websites': self.scheduled_websites,
                'consecutive_errors': self.consecutive_errors,
                'last_error_time': self.last_error_time,
                'scheduler_running': self.scheduler_running
            }
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2, default=str)
            
            self.logger.debug("Enhanced Scheduler: State saved to file")
        except Exception as e:
            self.logger.warning(f"Enhanced Scheduler: Failed to save state: {e}")
    
    def _acquire_lock(self) -> bool:
        """Acquire scheduler lock to prevent multiple instances"""
        try:
            if os.path.exists(self.lock_file):
                # Check if lock is stale (older than 2 minutes)
                lock_age = time.time() - os.path.getmtime(self.lock_file)
                if lock_age > 120:  # 2 minutes
                    self.logger.warning("Enhanced Scheduler: Removing stale lock file")
                    os.remove(self.lock_file)
                else:
                    # Check if the process is still running
                    try:
                        with open(self.lock_file, 'r') as f:
                            pid = int(f.read().strip())
                        # Check if process exists (Windows)
                        import subprocess
                        result = subprocess.run(['tasklist', '/FI', f'PID eq {pid}'], 
                                              capture_output=True, text=True)
                        if str(pid) not in result.stdout:
                            self.logger.warning("Enhanced Scheduler: Process not running, removing stale lock")
                            os.remove(self.lock_file)
                        else:
                            self.logger.error("Enhanced Scheduler: Another instance is already running")
                            return False
                    except:
                        # If we can't check the process, remove the lock
                        self.logger.warning("Enhanced Scheduler: Cannot verify process, removing lock")
                        os.remove(self.lock_file)
            
            # Create lock file
            with open(self.lock_file, 'w') as f:
                f.write(str(os.getpid()))
            return True
        except Exception as e:
            self.logger.error(f"Enhanced Scheduler: Failed to acquire lock: {e}")
            return False
    
    def _release_lock(self):
        """Release scheduler lock"""
        try:
            if os.path.exists(self.lock_file):
                os.remove(self.lock_file)
        except Exception as e:
            self.logger.warning(f"Enhanced Scheduler: Failed to release lock: {e}")
    
    def _get_active_websites(self) -> List[Dict[str, Any]]:
        """Get active websites from database"""
        try:
            # Force reload from database to ensure we have the latest data
            self.website_manager._load_websites(force_reload=True)
            all_websites = self.website_manager.list_websites()
            
            active_websites = []
            for site in all_websites.values():
                if isinstance(site, dict) and site.get('is_active', True):
                    active_websites.append(site)
            
            self.logger.info(f"Enhanced Scheduler: Found {len(active_websites)} active websites")
            
            # Log website details for debugging
            for site in active_websites:
                self.logger.debug(f"Active website: {site.get('name', 'Unknown')} (ID: {site.get('id', 'Unknown')}) - Interval: {site.get('check_interval_minutes', 60)} minutes")
            
            return active_websites
        except Exception as e:
            self.logger.error(f"Enhanced Scheduler: Failed to get active websites: {e}")
            return []
    
    def _schedule_website_checks(self):
        """Schedule website monitoring tasks"""
        try:
            self.logger.info("Enhanced Scheduler: Setting up website monitoring schedules...")
            
            # Clear existing schedules more thoroughly
            schedule.clear()
            
            # Clear our internal tracking
            self.scheduled_websites.clear()
            
            # Get active websites
            active_websites = self._get_active_websites()
            
            if not active_websites:
                self.logger.warning("Enhanced Scheduler: No active websites found")
                # Save empty state
                self.last_schedule_time = datetime.now(timezone.utc).isoformat()
                self._save_state()
                return False
            
            # Schedule each website
            scheduled_count = 0
            for site in active_websites:
                try:
                    site_id = site.get('id')
                    site_name = site.get('name', site.get('url', 'Unknown'))
                    interval_minutes = site.get('check_interval_minutes', 60)
                    
                    if not site_id:
                        self.logger.error(f"Enhanced Scheduler: Skipping site with missing ID: {site_name}")
                        continue
                    
                    # Schedule the check with a tag for easy removal
                    job = schedule.every(interval_minutes).minutes.do(
                        self._perform_website_check,
                        site_id=site_id,
                        site_name=site_name
                    )
                    job.tag(site_id)  # Tag the job with site_id for easy removal
                    
                    # Track scheduled website
                    self.scheduled_websites[site_id] = {
                        'name': site_name,
                        'url': site.get('url'),
                        'interval': interval_minutes,
                        'scheduled_at': datetime.now(timezone.utc).isoformat()
                    }
                    
                    scheduled_count += 1
                    self.logger.info(f"Enhanced Scheduler: Scheduled {site_name} every {interval_minutes} minutes")
                    
                except Exception as e:
                    self.logger.error(f"Enhanced Scheduler: Failed to schedule {site.get('name', 'Unknown')}: {e}")
                    continue
            
            # Update state
            self.last_schedule_time = datetime.now(timezone.utc).isoformat()
            self._save_state()
            
            self.logger.info(f"Enhanced Scheduler: Successfully scheduled {scheduled_count} websites")
            return scheduled_count > 0
            
        except Exception as e:
            self.logger.error(f"Enhanced Scheduler: Failed to schedule website checks: {e}")
            self.consecutive_errors += 1
            self.last_error_time = datetime.now(timezone.utc).isoformat()
            return False
    
    def _perform_website_check(self, site_id: str, site_name: str):
        """Perform a website check"""
        try:
            self.logger.info(f"Enhanced Scheduler: Performing check for {site_name} (ID: {site_id})")
            
            # First check if this website is still in our tracking
            if site_id not in self.scheduled_websites:
                self.logger.warning(f"Enhanced Scheduler: Website {site_id} not in scheduled websites, skipping check")
                return
            
            # Get website details with force reload to ensure we have latest data
            website = self.website_manager.get_website(site_id)
            if not website:
                self.logger.warning(f"Enhanced Scheduler: Website {site_id} not found in database, removing from schedule")
                # Remove from our tracking
                if site_id in self.scheduled_websites:
                    del self.scheduled_websites[site_id]
                # Cancel this specific job by tag
                schedule.clear(site_id)
                # Save updated state
                self._save_state()
                return
            
            # Perform the check using crawler module
            check_results = self.crawler_module.crawl_website(
                website_id=site_id,
                url=website.get('url'),  # Add the required URL parameter
                create_baseline=False,  # Don't create baselines for scheduled checks
                capture_subpages=website.get('capture_subpages', True),
                max_depth=website.get('max_crawl_depth', 2)
            )
            
            # Mark as scheduled check
            if check_results:
                check_results['is_manual'] = False
                check_results['is_scheduled'] = True
                
                # Send email report
                try:
                    send_report(website, check_results)
                    self.logger.info(f"Enhanced Scheduler: Email sent for {site_name}")
                except Exception as e:
                    self.logger.error(f"Enhanced Scheduler: Failed to send email for {site_name}: {e}")
            
            # Reset error counter on success
            self.consecutive_errors = 0
            self.logger.info(f"Enhanced Scheduler: Check completed for {site_name}")
            
        except Exception as e:
            self.logger.error(f"Enhanced Scheduler: Error checking {site_name}: {e}")
            self.consecutive_errors += 1
            self.last_error_time = datetime.now(timezone.utc).isoformat()
    
    def _scheduler_worker(self):
        """Main scheduler worker thread"""
        try:
            self.logger.info("Enhanced Scheduler: Worker thread starting...")
            
            # Initial setup
            if not self._schedule_website_checks():
                self.logger.error("Enhanced Scheduler: Failed to setup initial schedules")
                return
            
            # Main loop
            while not self.shutdown_event.is_set():
                try:
                    # Run pending tasks
                    tasks_run = schedule.run_pending()
                    
                    if tasks_run:
                        self.logger.info(f"Enhanced Scheduler: Executed {len(tasks_run)} scheduled tasks")
                        
                        # Log which tasks were executed for debugging
                        for task in tasks_run:
                            self.logger.debug(f"Enhanced Scheduler: Executed task: {task}")
                    
                    # Check for errors
                    if self.consecutive_errors >= self.max_consecutive_errors:
                        self.logger.error(f"Enhanced Scheduler: Too many consecutive errors ({self.consecutive_errors}), rescheduling...")
                        if self._schedule_website_checks():
                            self.consecutive_errors = 0
                    
                    # Calculate wait time
                    wait_time = min(schedule.idle_seconds() or 60, 60)
                    wait_time = max(wait_time, 1)
                    
                    # Wait for next check or shutdown
                    if self.shutdown_event.wait(timeout=wait_time):
                        break
                        
                except Exception as e:
                    self.logger.error(f"Enhanced Scheduler: Error in worker loop: {e}")
                    self.consecutive_errors += 1
                    self.last_error_time = datetime.now(timezone.utc).isoformat()
                    
                    # Wait before retrying
                    if self.shutdown_event.wait(timeout=60):
                        break
            
            self.logger.info("Enhanced Scheduler: Worker thread stopped")
            
        except Exception as e:
            self.logger.error(f"Enhanced Scheduler: Fatal error in worker thread: {e}")
        finally:
            self.scheduler_running = False
            self._release_lock()
    
    def start(self) -> bool:
        """Start the enhanced scheduler"""
        try:
            if self.scheduler_running:
                self.logger.warning("Enhanced Scheduler: Already running")
                return False
            
            # Acquire lock
            if not self._acquire_lock():
                self.logger.error("Enhanced Scheduler: Another instance is already running")
                return False
            
            # Start worker thread
            self.scheduler_thread = threading.Thread(
                target=self._scheduler_worker,
                name="EnhancedScheduler",
                daemon=True
            )
            self.scheduler_thread.start()
            
            self.scheduler_running = True
            self.logger.info("Enhanced Scheduler: Started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Enhanced Scheduler: Failed to start: {e}")
            self._release_lock()
            return False
    
    def stop(self):
        """Stop the enhanced scheduler"""
        try:
            if not self.scheduler_running:
                self.logger.info("Enhanced Scheduler: Not running")
                return
            
            self.logger.info("Enhanced Scheduler: Stopping...")
            
            # Signal shutdown
            self.shutdown_event.set()
            
            # Wait for thread to finish
            if self.scheduler_thread and self.scheduler_thread.is_alive():
                self.scheduler_thread.join(timeout=30)
            
            # Clear schedules
            schedule.clear()
            
            # Update state
            self.scheduler_running = False
            self._save_state()
            self._release_lock()
            
            self.logger.info("Enhanced Scheduler: Stopped successfully")
            
        except Exception as e:
            self.logger.error(f"Enhanced Scheduler: Error stopping: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get scheduler status"""
        try:
            # Get current active websites count for comparison
            current_active_count = len(self._get_active_websites())
            
            return {
                'running': self.scheduler_running,
                'thread_alive': self.scheduler_thread.is_alive() if self.scheduler_thread else False,
                'scheduled_websites': len(self.scheduled_websites),
                'database_active_websites': current_active_count,
                'consecutive_errors': self.consecutive_errors,
                'last_schedule_time': self.last_schedule_time,
                'last_error_time': self.last_error_time,
                'active_jobs': len(schedule.jobs),
                'next_run': schedule.next_run().isoformat() if schedule.jobs else None,
                'sync_status': 'in_sync' if len(self.scheduled_websites) == current_active_count else 'out_of_sync'
            }
        except Exception as e:
            self.logger.error(f"Enhanced Scheduler: Error getting status: {e}")
            return {
                'running': self.scheduler_running,
                'thread_alive': False,
                'error': str(e)
            }
    
    def force_reschedule(self) -> bool:
        """Force reschedule all websites"""
        try:
            self.logger.info("Enhanced Scheduler: Force rescheduling all websites...")
            
            # Clear all schedules and state first
            schedule.clear()
            self.scheduled_websites.clear()
            
            # Reinitialize managers to ensure fresh data
            self._initialize_managers()
            
            # Force reload websites from database
            self.website_manager._load_websites(force_reload=True)
            
            # Schedule websites
            success = self._schedule_website_checks()
            
            if success:
                self.logger.info("Enhanced Scheduler: Force reschedule completed successfully")
            else:
                self.logger.warning("Enhanced Scheduler: Force reschedule completed but no websites were scheduled")
            
            return success
        except Exception as e:
            self.logger.error(f"Enhanced Scheduler: Failed to force reschedule: {e}")
            return False
    
    def remove_website(self, site_id: str) -> bool:
        """Remove a specific website from the scheduler"""
        try:
            self.logger.info(f"Enhanced Scheduler: Removing website {site_id} from schedule")
            
            # Remove from our tracking first
            if site_id in self.scheduled_websites:
                website_name = self.scheduled_websites[site_id].get('name', 'Unknown')
                del self.scheduled_websites[site_id]
                self.logger.info(f"Enhanced Scheduler: Removed {website_name} from scheduled websites tracking")
            else:
                self.logger.warning(f"Enhanced Scheduler: Website {site_id} was not in scheduled websites tracking")
            
            # Clear the specific job by tag
            schedule.clear(site_id)
            
            # Also clear any jobs that might be queued for execution
            # This is a more aggressive approach to prevent race conditions
            for job in schedule.jobs[:]:  # Create a copy to avoid modification during iteration
                if site_id in job.tags:
                    schedule.jobs.remove(job)
                    self.logger.info(f"Enhanced Scheduler: Removed queued job for website {site_id}")
            
            # Save updated state
            self._save_state()
            
            self.logger.info(f"Enhanced Scheduler: Successfully removed website {site_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Enhanced Scheduler: Failed to remove website {site_id}: {e}")
            return False

# Global instance
_enhanced_scheduler = None
_scheduler_lock = threading.Lock()

def get_enhanced_scheduler(config_path: Optional[str] = None) -> EnhancedScheduler:
    """Get or create the global enhanced scheduler instance"""
    global _enhanced_scheduler
    if _enhanced_scheduler is None:
        with _scheduler_lock:
            if _enhanced_scheduler is None:
                _enhanced_scheduler = EnhancedScheduler(config_path=config_path)
    return _enhanced_scheduler

def start_enhanced_scheduler(config_path: Optional[str] = None) -> bool:
    """Start the enhanced scheduler"""
    scheduler = get_enhanced_scheduler(config_path)
    return scheduler.start()

def stop_enhanced_scheduler():
    """Stop the enhanced scheduler"""
    global _enhanced_scheduler
    if _enhanced_scheduler:
        _enhanced_scheduler.stop()

def get_enhanced_scheduler_status() -> Dict[str, Any]:
    """Get enhanced scheduler status"""
    global _enhanced_scheduler
    if _enhanced_scheduler:
        return _enhanced_scheduler.get_status()
    return {'running': False, 'error': 'Scheduler not initialized'}

def force_reschedule_enhanced_scheduler() -> bool:
    """Force reschedule all websites"""
    global _enhanced_scheduler
    if _enhanced_scheduler:
        return _enhanced_scheduler.force_reschedule()
    return False

def reset_enhanced_scheduler():
    """Reset the global enhanced scheduler instance"""
    global _enhanced_scheduler
    if _enhanced_scheduler:
        _enhanced_scheduler.stop()
    _enhanced_scheduler = None

def remove_website_from_scheduler(site_id: str) -> bool:
    """Remove a website from the scheduler"""
    global _enhanced_scheduler
    if _enhanced_scheduler:
        return _enhanced_scheduler.remove_website(site_id)
    return False

if __name__ == '__main__':
    # Test the enhanced scheduler
    logger.info("=== Enhanced Scheduler Test ===")
    
    scheduler = EnhancedScheduler()
    
    try:
        # Start scheduler
        if scheduler.start():
            logger.info("Enhanced Scheduler: Started successfully")
            
            # Show status
            status = scheduler.get_status()
            logger.info(f"Enhanced Scheduler Status: {status}")
            
            # Keep running for a bit
            time.sleep(10)
            
        else:
            logger.error("Enhanced Scheduler: Failed to start")
    
    except KeyboardInterrupt:
        logger.info("Enhanced Scheduler: Received interrupt signal")
    
    finally:
        scheduler.stop()
        logger.info("Enhanced Scheduler: Test completed")
