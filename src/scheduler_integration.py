"""
Scheduler Integration Module
Handles starting and managing the scheduler as a background thread within the Flask application.
"""

import threading
import time
import logging
from typing import Optional
from .scheduler import run_scheduler, schedule_website_monitoring_tasks
from .config_loader import get_config
from .logger_setup import setup_logging
from .scheduler_db import get_scheduler_db_manager

class SchedulerManager:
    """Manages the scheduler as a background thread within the Flask application."""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.config = get_config(config_path=config_path) if config_path else get_config()
        self.logger = setup_logging(config_path=config_path) if config_path else setup_logging()
        
        self.scheduler_thread: Optional[threading.Thread] = None
        self.scheduler_running = False
        self.scheduler_stop_event = threading.Event()
        
        # Scheduler configuration
        self.enabled = self.config.get('scheduler_enabled', True)
        self.startup_delay = self.config.get('scheduler_startup_delay_seconds', 10)
        self.check_interval = self.config.get('scheduler_check_interval_seconds', 60)
        
        # Initialize database manager
        self.db_manager = get_scheduler_db_manager(config_path=config_path)
        
    def start_scheduler(self):
        """Start the scheduler in a background thread."""
        if not self.enabled:
            self.logger.info("SCHEDULER: Scheduler is disabled in configuration.")
            return False
            
        if self.scheduler_running:
            self.logger.warning("SCHEDULER: Scheduler is already running.")
            return False
            
        try:
            self.logger.info("SCHEDULER: Starting scheduler in background thread...")
            
            # Test database connection
            if not self.db_manager.test_connection():
                self.logger.error("SCHEDULER: Database connection test failed")
                return False
            
            # Log scheduler start event
            self.db_manager.log_scheduler_event("INFO", "Scheduler starting", None, None)
            
            # Create and start the scheduler thread
            self.scheduler_thread = threading.Thread(
                target=self._scheduler_worker,
                name="WebsiteMonitorScheduler",
                daemon=True  # Daemon thread so it doesn't prevent app shutdown
            )
            self.scheduler_thread.start()
            
            self.scheduler_running = True
            self.logger.info("SCHEDULER: Scheduler started successfully in background thread.")
            
            # Update status in database
            self.db_manager.update_scheduler_status("running", True, 0)
            
            return True
            
        except Exception as e:
            self.logger.error(f"SCHEDULER: Failed to start scheduler: {e}", exc_info=True)
            return False
    
    def stop_scheduler(self):
        """Stop the scheduler gracefully."""
        if not self.scheduler_running:
            self.logger.info("SCHEDULER: Scheduler is not running.")
            return
            
        try:
            self.logger.info("SCHEDULER: Stopping scheduler...")
            
            # Log scheduler stop event
            self.db_manager.log_scheduler_event("INFO", "Scheduler stopping", None, None)
            
            self.scheduler_stop_event.set()
            
            if self.scheduler_thread and self.scheduler_thread.is_alive():
                self.scheduler_thread.join(timeout=30)  # Wait up to 30 seconds
                
            self.scheduler_running = False
            self.logger.info("SCHEDULER: Scheduler stopped successfully.")
            
            # Update status in database
            self.db_manager.update_scheduler_status("stopped", False, 0)
            
            # Close database connection
            self.db_manager.close_connection()
            
        except Exception as e:
            self.logger.error(f"SCHEDULER: Error stopping scheduler: {e}", exc_info=True)
    
    def _scheduler_worker(self):
        """Worker function that runs the scheduler in a background thread."""
        try:
            self.logger.info(f"SCHEDULER: Scheduler worker starting (startup delay: {self.startup_delay}s)...")
            
            # Log worker start event
            self.db_manager.log_scheduler_event("INFO", f"Scheduler worker starting with {self.startup_delay}s delay", None, None)
            
            # Wait for startup delay to allow Flask app to fully initialize
            time.sleep(self.startup_delay)
            
            # Initialize and schedule tasks with proper configuration
            schedule_website_monitoring_tasks(config_path=self.config_path)
            
            # Log tasks scheduled event
            import schedule
            active_jobs = len(schedule.jobs)
            self.db_manager.log_scheduler_event("INFO", f"Scheduled {active_jobs} monitoring tasks", None, None)
            self.db_manager.update_scheduler_status("running", True, active_jobs)
            
            self.logger.info("SCHEDULER: Starting main scheduling loop in background thread.")
            
            # Main scheduling loop
            while not self.scheduler_stop_event.is_set():
                try:
                    # Import schedule here to avoid circular imports
                    import schedule
                    
                    # Run pending tasks
                    tasks_run = schedule.run_pending()
                    
                    # Log metrics
                    active_jobs = len(schedule.jobs)
                    self.db_manager.log_metric("active_jobs", active_jobs)
                    
                    if tasks_run:
                        self.db_manager.log_scheduler_event("INFO", f"Executed {len(tasks_run)} scheduled tasks", None, None)
                    
                    # Calculate wait time (minimum 1 second, maximum check_interval)
                    wait_time = min(schedule.idle_seconds() or self.check_interval, self.check_interval)
                    wait_time = max(wait_time, 1)  # Minimum 1 second
                    
                    # Update status periodically
                    self.db_manager.update_scheduler_status("running", True, active_jobs)
                    
                    # Wait for next check or stop signal
                    if self.scheduler_stop_event.wait(timeout=wait_time):
                        break
                        
                except Exception as e:
                    self.logger.error(f"SCHEDULER: Error in scheduling loop: {e}", exc_info=True)
                    self.db_manager.log_scheduler_event("ERROR", f"Scheduling loop error: {str(e)}", None, None)
                    # Wait before retrying
                    if self.scheduler_stop_event.wait(timeout=60):
                        break
            
            self.logger.info("SCHEDULER: Scheduler worker stopped.")
            
        except Exception as e:
            self.logger.error(f"SCHEDULER: Fatal error in scheduler worker: {e}", exc_info=True)
        finally:
            self.scheduler_running = False
    
    def is_running(self) -> bool:
        """Check if the scheduler is currently running."""
        return self.scheduler_running and self.scheduler_thread and self.scheduler_thread.is_alive()
    
    def get_status(self) -> dict:
        """Get the current status of the scheduler."""
        return {
            'enabled': self.enabled,
            'running': self.is_running(),
            'thread_alive': self.scheduler_thread.is_alive() if self.scheduler_thread else False,
            'startup_delay': self.startup_delay,
            'check_interval': self.check_interval
        }
    
    def reload_config(self, config_path: str = None) -> bool:
        """Reload scheduler configuration."""
        try:
            if config_path:
                self.config_path = config_path
            
            # Reload configuration
            self.config = get_config(config_path=self.config_path)
            
            # Update scheduler settings
            self.enabled = self.config.get('scheduler_enabled', True)
            self.startup_delay = self.config.get('scheduler_startup_delay_seconds', 10)
            self.check_interval = self.config.get('scheduler_check_interval_seconds', 60)
            
            self.logger.info(f"SCHEDULER: Configuration reloaded from {self.config_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"SCHEDULER: Failed to reload configuration: {e}", exc_info=True)
            return False

    def clear_all_tasks(self):
        """Clear all scheduled tasks from the scheduler."""
        try:
            import schedule
            self.logger.info("SCHEDULER: Clearing all scheduled tasks...")
            
            # Clear all jobs
            schedule.clear()
            
            self.db_manager.log_scheduler_event("INFO", "All scheduled tasks cleared", None, None)
            self.db_manager.update_scheduler_status("running", True, 0)
            
            self.logger.info("SCHEDULER: All scheduled tasks cleared successfully.")
            return True
        except Exception as e:
            self.logger.error(f"SCHEDULER: Error clearing all tasks: {e}", exc_info=True)
            return False

    def remove_site_task(self, site_id: str):
        """Remove scheduler task for a specific website."""
        try:
            import schedule
            self.logger.info(f"SCHEDULER: Removing scheduler task for site {site_id}...")
            
            # Find and remove jobs that match this site_id
            jobs_to_remove = []
            for job in schedule.jobs:
                # Check if this job is for the specific site
                if hasattr(job.job_func, 'keywords') and job.job_func.keywords.get('site_id') == site_id:
                    jobs_to_remove.append(job)
                elif hasattr(job.job_func, 'args') and len(job.job_func.args) > 0 and job.job_func.args[0] == site_id:
                    jobs_to_remove.append(job)
            
            # Remove the identified jobs
            for job in jobs_to_remove:
                schedule.cancel_job(job)
                self.logger.info(f"SCHEDULER: Removed scheduled task for site {site_id}")
            
            if jobs_to_remove:
                active_jobs = len(schedule.jobs)
                self.db_manager.log_scheduler_event("INFO", f"Removed scheduler task for site {site_id}. {active_jobs} tasks remaining.", None, None)
                self.db_manager.update_scheduler_status("running", True, active_jobs)
            else:
                self.logger.warning(f"SCHEDULER: No scheduled tasks found for site {site_id}")
                
            return True
        except Exception as e:
            self.logger.error(f"SCHEDULER: Error removing task for site {site_id}: {e}", exc_info=True)
            return False

    def reschedule_tasks(self):
        """Reschedule all monitoring tasks by clearing existing tasks and re-running the scheduling function."""
        try:
            self.logger.info("SCHEDULER: Rescheduling all monitoring tasks...")
            
            # First clear all existing tasks
            self.clear_all_tasks()
            
            # Then reschedule all tasks
            schedule_website_monitoring_tasks(config_path=self.config_path)
            
            import schedule
            active_jobs = len(schedule.jobs)
            self.db_manager.log_scheduler_event("INFO", f"Rescheduled tasks. Now managing {active_jobs} jobs.", None, None)
            self.db_manager.update_scheduler_status("running", True, active_jobs)
            
            self.logger.info(f"SCHEDULER: Rescheduling complete. Now managing {active_jobs} jobs.")
            return True
        except Exception as e:
            self.logger.error(f"SCHEDULER: An error occurred during task rescheduling: {e}", exc_info=True)
            return False


# Global scheduler manager instance
_scheduler_manager: Optional[SchedulerManager] = None
_scheduler_lock = threading.Lock()

def get_scheduler_manager(config_path: Optional[str] = None) -> SchedulerManager:
    """Get or create the global scheduler manager instance."""
    global _scheduler_manager
    if _scheduler_manager is None:
        with _scheduler_lock:
            if _scheduler_manager is None:
                _scheduler_manager = SchedulerManager(config_path=config_path)
    return _scheduler_manager

def start_scheduler(config_path: Optional[str] = None) -> bool:
    """Start the scheduler with the given configuration."""
    manager = get_scheduler_manager(config_path=config_path)
    return manager.start_scheduler()

def stop_scheduler():
    """Stop the scheduler gracefully."""
    global _scheduler_manager
    if _scheduler_manager:
        _scheduler_manager.stop_scheduler()

def get_scheduler_status() -> dict:
    """Get the current status of the scheduler."""
    global _scheduler_manager
    if _scheduler_manager:
        status = _scheduler_manager.get_status()
        # Add configuration info
        status.update({
            'config_path': _scheduler_manager.config_path,
            'config_loaded': _scheduler_manager.config is not None
        })
        return status
    return {'enabled': False, 'running': False, 'thread_alive': False, 'config_loaded': False}

def reload_scheduler_config(config_path: str = None) -> bool:
    """Reload scheduler configuration."""
    global _scheduler_manager
    if _scheduler_manager:
        return _scheduler_manager.reload_config(config_path)
    return False

def reschedule_tasks():
    """Trigger a full reschedule of all website monitoring tasks."""
    manager = get_scheduler_manager()
    if manager and manager.is_running():
        return manager.reschedule_tasks()
    elif manager:
        manager.logger.warning("SCHEDULER: Reschedule requested, but scheduler is not running.")
    return False

def clear_all_scheduler_tasks():
    """Clear all scheduled tasks from the scheduler."""
    manager = get_scheduler_manager()
    if manager and manager.is_running():
        return manager.clear_all_tasks()
    elif manager:
        manager.logger.warning("SCHEDULER: Clear all tasks requested, but scheduler is not running.")
    return False

def remove_site_scheduler_task(site_id: str):
    """Remove scheduler task for a specific website."""
    manager = get_scheduler_manager()
    if manager and manager.is_running():
        return manager.remove_site_task(site_id)
    elif manager:
        manager.logger.warning(f"SCHEDULER: Remove task for site {site_id} requested, but scheduler is not running.")
    return False 