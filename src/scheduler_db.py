"""
Scheduler Database Integration Module
Handles database connections and ensures proper database access for the scheduler.
"""

import sqlite3
import threading
import logging
import os
from typing import Optional, Dict, Any
from contextlib import contextmanager
from .path_utils import get_database_path, ensure_directory_exists
from .config_loader import get_config
from .logger_setup import setup_logging

class SchedulerDatabaseManager:
    """Manages database connections for the scheduler."""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.config = get_config(config_path=config_path) if config_path else get_config()
        self.logger = setup_logging(config_path=config_path) if config_path else setup_logging()
        
        # Database path
        self.db_path = get_database_path()
        # Ensure the directory exists (db_path is a string)
        db_dir = os.path.dirname(self.db_path)
        ensure_directory_exists(db_dir)
        
        # Thread-local storage for database connections
        self._local = threading.local()
        
        # Initialize database
        self._initialize_database()
        
    def _initialize_database(self):
        """Initialize the database and ensure tables exist."""
        try:
            self.logger.info(f"SCHEDULER DB: Initializing database at {self.db_path}")
            
            # Create database directory if it doesn't exist
            db_dir = os.path.dirname(self.db_path)
            ensure_directory_exists(db_dir)
            
            # Test database connection
            with self.get_connection() as conn:
                # Check if tables exist
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                self.logger.info(f"SCHEDULER DB: Found {len(tables)} tables: {tables}")
                
                # Ensure required tables exist
                self._ensure_scheduler_tables(conn)
                
        except Exception as e:
            self.logger.error(f"SCHEDULER DB: Failed to initialize database: {e}", exc_info=True)
            raise
    
    def _ensure_scheduler_tables(self, conn: sqlite3.Connection):
        """Ensure scheduler-specific tables exist."""
        try:
            cursor = conn.cursor()
            
            # Create scheduler_log table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scheduler_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    website_id TEXT,
                    check_id TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create scheduler_status table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scheduler_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    status TEXT NOT NULL,
                    enabled BOOLEAN NOT NULL,
                    active_jobs INTEGER NOT NULL,
                    last_run TEXT,
                    next_run TEXT,
                    config_path TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create scheduler_metrics table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scheduler_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    website_id TEXT,
                    check_id TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
            self.logger.info("SCHEDULER DB: Scheduler tables ensured successfully")
            
        except Exception as e:
            self.logger.error(f"SCHEDULER DB: Failed to ensure scheduler tables: {e}", exc_info=True)
            raise
    
    @contextmanager
    def get_connection(self):
        """Get a database connection with proper error handling."""
        conn = None
        try:
            # Get thread-local connection or create new one
            if not hasattr(self._local, 'connection') or self._local.connection is None:
                self._local.connection = sqlite3.connect(str(self.db_path), timeout=30.0)
                self._local.connection.row_factory = sqlite3.Row
                
            conn = self._local.connection
            yield conn
            
        except sqlite3.OperationalError as e:
            self.logger.error(f"SCHEDULER DB: Database operational error: {e}")
            # Close and recreate connection
            if hasattr(self._local, 'connection') and self._local.connection:
                self._local.connection.close()
                self._local.connection = None
            raise
        except Exception as e:
            self.logger.error(f"SCHEDULER DB: Database error: {e}", exc_info=True)
            raise
        finally:
            # Don't close connection here - keep it for reuse
            pass
    
    def log_scheduler_event(self, level: str, message: str, website_id: Optional[str] = None, check_id: Optional[str] = None):
        """Log a scheduler event to the database."""
        try:
            from datetime import datetime, timezone
            timestamp = datetime.now(timezone.utc).isoformat()
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO scheduler_log (timestamp, level, message, website_id, check_id)
                    VALUES (?, ?, ?, ?, ?)
                """, (timestamp, level, message, website_id, check_id))
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"SCHEDULER DB: Failed to log scheduler event: {e}", exc_info=True)
    
    def update_scheduler_status(self, status: str, enabled: bool, active_jobs: int, 
                              last_run: Optional[str] = None, next_run: Optional[str] = None):
        """Update scheduler status in the database."""
        try:
            from datetime import datetime, timezone
            timestamp = datetime.now(timezone.utc).isoformat()
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO scheduler_status (timestamp, status, enabled, active_jobs, last_run, next_run, config_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (timestamp, status, enabled, active_jobs, last_run, next_run, self.config_path))
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"SCHEDULER DB: Failed to update scheduler status: {e}", exc_info=True)
    
    def log_metric(self, metric_name: str, metric_value: float, website_id: Optional[str] = None, check_id: Optional[str] = None):
        """Log a scheduler metric to the database."""
        try:
            from datetime import datetime, timezone
            timestamp = datetime.now(timezone.utc).isoformat()
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO scheduler_metrics (timestamp, metric_name, metric_value, website_id, check_id)
                    VALUES (?, ?, ?, ?, ?)
                """, (timestamp, metric_name, metric_value, website_id, check_id))
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"SCHEDULER DB: Failed to log metric: {e}", exc_info=True)
    
    def get_recent_logs(self, limit: int = 100) -> list:
        """Get recent scheduler logs from the database."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM scheduler_log 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """, (limit,))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            self.logger.error(f"SCHEDULER DB: Failed to get recent logs: {e}", exc_info=True)
            return []
    
    def get_scheduler_status_history(self, limit: int = 50) -> list:
        """Get scheduler status history from the database."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM scheduler_status 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """, (limit,))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            self.logger.error(f"SCHEDULER DB: Failed to get status history: {e}", exc_info=True)
            return []
    
    def cleanup_old_logs(self, days: int = 30):
        """Clean up old scheduler logs."""
        try:
            from datetime import datetime, timezone, timedelta
            cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Clean up old logs
                cursor.execute("DELETE FROM scheduler_log WHERE timestamp < ?", (cutoff_date,))
                logs_deleted = cursor.rowcount
                
                # Clean up old status records
                cursor.execute("DELETE FROM scheduler_status WHERE timestamp < ?", (cutoff_date,))
                status_deleted = cursor.rowcount
                
                # Clean up old metrics
                cursor.execute("DELETE FROM scheduler_metrics WHERE timestamp < ?", (cutoff_date,))
                metrics_deleted = cursor.rowcount
                
                conn.commit()
                
                self.logger.info(f"SCHEDULER DB: Cleaned up {logs_deleted} logs, {status_deleted} status records, {metrics_deleted} metrics")
                
        except Exception as e:
            self.logger.error(f"SCHEDULER DB: Failed to cleanup old logs: {e}", exc_info=True)
    
    def test_connection(self) -> bool:
        """Test database connection."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                return result is not None
        except Exception as e:
            self.logger.error(f"SCHEDULER DB: Database connection test failed: {e}")
            return False
    
    def close_connection(self):
        """Close the database connection."""
        try:
            if hasattr(self._local, 'connection') and self._local.connection:
                self._local.connection.close()
                self._local.connection = None
                self.logger.info("SCHEDULER DB: Database connection closed")
        except Exception as e:
            self.logger.error(f"SCHEDULER DB: Error closing database connection: {e}")


# Global database manager instance
_scheduler_db_manager: Optional[SchedulerDatabaseManager] = None

def get_scheduler_db_manager(config_path: Optional[str] = None) -> SchedulerDatabaseManager:
    """Get or create the global scheduler database manager instance."""
    global _scheduler_db_manager
    if _scheduler_db_manager is None:
        _scheduler_db_manager = SchedulerDatabaseManager(config_path=config_path)
    return _scheduler_db_manager

def test_scheduler_database(config_path: Optional[str] = None) -> bool:
    """Test scheduler database connection."""
    try:
        db_manager = get_scheduler_db_manager(config_path=config_path)
        return db_manager.test_connection()
    except Exception:
        return False 