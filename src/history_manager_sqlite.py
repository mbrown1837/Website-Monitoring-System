"""
SQLite-based History Manager

This module provides check history management functionality using SQLite database
instead of JSON files for better data consistency and performance.
"""

import sqlite3
import json
import os
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from src.config_loader import get_config
from src.logger_setup import setup_logging
from .path_utils import resolve_path, clean_path_for_logging

class HistoryManagerSQLite:
    def __init__(self, config_path=None):
        # Set up basics
        if config_path:
            self.config = get_config(config_path=config_path)
            self.logger = setup_logging(config_path=config_path)
        else:
            self.config = get_config()
            self.logger = setup_logging()
        
        self.db_path = self._initialize_database_path()
        self._ensure_tables_exist()

    def _initialize_database_path(self):
        """Initialize path to the SQLite database."""
        path = self.config.get("database_path", "data/website_monitor.db")
        
        # Use environment-agnostic path resolution
        resolved_path = resolve_path(path)
        
        # Ensure directory exists
        directory = os.path.dirname(resolved_path)
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory, exist_ok=True)
                self.logger.info(f"Created directory for database: {clean_path_for_logging(directory)}")
            except OSError as e:
                self.logger.error(f"Error creating directory {clean_path_for_logging(directory)} for database: {e}")
                raise
                
        return resolved_path

    def _ensure_tables_exist(self):
        """Ensure the check_history table exists in the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if check_history table exists
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='check_history'
                """)
                
                if not cursor.fetchone():
                    self.logger.info("Check history table not found, creating it...")
                    self._create_check_history_table()
                else:
                    self.logger.debug("Check history table already exists")
                    
        except Exception as e:
            self.logger.error(f"Error ensuring tables exist: {e}")
            raise

    def _create_check_history_table(self):
        """Create the check_history table if it doesn't exist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS check_history (
                        check_id TEXT PRIMARY KEY,
                        site_id TEXT NOT NULL,
                        timestamp_utc TEXT NOT NULL,
                        timestamp_readable TEXT,
                        status TEXT NOT NULL,
                        html_snapshot_path TEXT,
                        html_content_hash TEXT,
                        visual_snapshot_path TEXT,
                        url TEXT,
                        significant_change_detected BOOLEAN DEFAULT 0,
                        website_id TEXT,
                        timestamp TEXT,
                        broken_links TEXT,  -- JSON string
                        missing_meta_tags TEXT,  -- JSON string
                        all_pages TEXT,  -- JSON string
                        visual_diff_score REAL,
                        visual_diff_image_path TEXT,
                        performance_metrics TEXT,  -- JSON string
                        blur_detection_results TEXT,  -- JSON string
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes for better performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_check_history_site_id ON check_history(site_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_check_history_timestamp ON check_history(timestamp_utc)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_check_history_status ON check_history(status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_check_history_website_id ON check_history(website_id)")
                
                conn.commit()
                self.logger.info("Check history table created successfully")
                
        except Exception as e:
            self.logger.error(f"Error creating check history table: {e}")
            raise

    def add_check_record(self, site_id: str, status: str, **details) -> str:
        """Add a new check record to the database."""
        try:
            # Generate unique check_id with microsecond precision and random component
            import time
            import random
            timestamp_ms = int(time.time() * 1000000)  # Microsecond precision
            random_suffix = random.randint(1000, 9999)
            check_id = details.get('check_id') or f"check_{timestamp_ms}_{random_suffix}_{site_id[:8]}"
            
            # Prepare data for insertion
            data = (
                check_id,
                site_id,
                details.get('timestamp_utc', datetime.now(timezone.utc).isoformat()),
                details.get('timestamp_readable'),
                status,
                details.get('html_snapshot_path'),
                details.get('html_content_hash'),
                details.get('visual_snapshot_path'),
                details.get('url'),
                1 if details.get('significant_change_detected', False) else 0,
                details.get('website_id', site_id),
                details.get('timestamp'),
                json.dumps(details.get('broken_links', [])),
                json.dumps(details.get('missing_meta_tags', [])),
                json.dumps(details.get('all_pages', [])),
                details.get('visual_diff_score'),
                details.get('visual_diff_image_path'),
                json.dumps(details.get('performance_metrics', {})),
                json.dumps(details.get('blur_detection_results', {}))
            )
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO check_history (
                        check_id, site_id, timestamp_utc, timestamp_readable, status,
                        html_snapshot_path, html_content_hash, visual_snapshot_path, url,
                        significant_change_detected, website_id, timestamp, broken_links,
                        missing_meta_tags, all_pages, visual_diff_score, visual_diff_image_path,
                        performance_metrics, blur_detection_results
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, data)
                
                conn.commit()
                self.logger.info(f"Added check record {check_id} for site {site_id}")
                return check_id
                
        except Exception as e:
            self.logger.error(f"Error adding check record for site {site_id}: {e}")
            raise

    def get_check_by_id(self, check_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific check record by ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM check_history WHERE check_id = ?", (check_id,))
                row = cursor.fetchone()
                
                if row:
                    # Get column names
                    columns = [description[0] for description in cursor.description]
                    check_record = dict(zip(columns, row))
                    
                    # Parse JSON fields
                    if check_record.get('broken_links'):
                        try:
                            check_record['broken_links'] = json.loads(check_record['broken_links'])
                        except json.JSONDecodeError:
                            check_record['broken_links'] = []
                    
                    if check_record.get('missing_meta_tags'):
                        try:
                            check_record['missing_meta_tags'] = json.loads(check_record['missing_meta_tags'])
                        except json.JSONDecodeError:
                            check_record['missing_meta_tags'] = []
                    
                    if check_record.get('all_pages'):
                        try:
                            check_record['all_pages'] = json.loads(check_record['all_pages'])
                        except json.JSONDecodeError:
                            check_record['all_pages'] = []
                    
                    if check_record.get('performance_metrics'):
                        try:
                            check_record['performance_metrics'] = json.loads(check_record['performance_metrics'])
                        except json.JSONDecodeError:
                            check_record['performance_metrics'] = {}
                    
                    if check_record.get('blur_detection_results'):
                        try:
                            check_record['blur_detection_results'] = json.loads(check_record['blur_detection_results'])
                        except json.JSONDecodeError:
                            check_record['blur_detection_results'] = {}
                    
                    # Convert boolean fields
                    check_record['significant_change_detected'] = bool(check_record['significant_change_detected'])
                    
                    return check_record
                
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting check record {check_id}: {e}")
            return None

    def get_history_for_site(self, site_id: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get check history for a specific site."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM check_history 
                    WHERE site_id = ? 
                    ORDER BY timestamp_utc DESC 
                    LIMIT ? OFFSET ?
                """, (site_id, limit, offset))
                
                rows = cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                
                history = []
                for row in rows:
                    check_record = dict(zip(columns, row))
                    
                    # Parse JSON fields
                    if check_record.get('broken_links'):
                        try:
                            check_record['broken_links'] = json.loads(check_record['broken_links'])
                        except json.JSONDecodeError:
                            check_record['broken_links'] = []
                    
                    if check_record.get('missing_meta_tags'):
                        try:
                            check_record['missing_meta_tags'] = json.loads(check_record['missing_meta_tags'])
                        except json.JSONDecodeError:
                            check_record['missing_meta_tags'] = []
                    
                    if check_record.get('all_pages'):
                        try:
                            check_record['all_pages'] = json.loads(check_record['all_pages'])
                        except json.JSONDecodeError:
                            check_record['all_pages'] = []
                    
                    if check_record.get('performance_metrics'):
                        try:
                            check_record['performance_metrics'] = json.loads(check_record['performance_metrics'])
                        except json.JSONDecodeError:
                            check_record['performance_metrics'] = {}
                    
                    if check_record.get('blur_detection_results'):
                        try:
                            check_record['blur_detection_results'] = json.loads(check_record['blur_detection_results'])
                        except json.JSONDecodeError:
                            check_record['blur_detection_results'] = {}
                    
                    # Convert boolean fields
                    check_record['significant_change_detected'] = bool(check_record['significant_change_detected'])
                    
                    history.append(check_record)
                
                return history
                
        except Exception as e:
            self.logger.error(f"Error getting history for site {site_id}: {e}")
            return []

    def get_latest_check_for_site(self, site_id: str) -> Optional[Dict[str, Any]]:
        """Get the latest check record for a specific site."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM check_history 
                    WHERE site_id = ? 
                    ORDER BY timestamp_utc DESC 
                    LIMIT 1
                """, (site_id,))
                
                row = cursor.fetchone()
                if row:
                    columns = [description[0] for description in cursor.description]
                    check_record = dict(zip(columns, row))
                    
                    # Parse JSON fields
                    if check_record.get('broken_links'):
                        try:
                            check_record['broken_links'] = json.loads(check_record['broken_links'])
                        except json.JSONDecodeError:
                            check_record['broken_links'] = []
                    
                    if check_record.get('missing_meta_tags'):
                        try:
                            check_record['missing_meta_tags'] = json.loads(check_record['missing_meta_tags'])
                        except json.JSONDecodeError:
                            check_record['missing_meta_tags'] = []
                    
                    if check_record.get('all_pages'):
                        try:
                            check_record['all_pages'] = json.loads(check_record['all_pages'])
                        except json.JSONDecodeError:
                            check_record['all_pages'] = []
                    
                    if check_record.get('performance_metrics'):
                        try:
                            check_record['performance_metrics'] = json.loads(check_record['performance_metrics'])
                        except json.JSONDecodeError:
                            check_record['performance_metrics'] = {}
                    
                    if check_record.get('blur_detection_results'):
                        try:
                            check_record['blur_detection_results'] = json.loads(check_record['blur_detection_results'])
                        except json.JSONDecodeError:
                            check_record['blur_detection_results'] = {}
                    
                    # Convert boolean fields
                    check_record['significant_change_detected'] = bool(check_record['significant_change_detected'])
                    
                    return check_record
                
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting latest check for site {site_id}: {e}")
            return None

    def get_all_history(self, limit: int = 1000, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all check history records."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM check_history 
                    ORDER BY timestamp_utc DESC 
                    LIMIT ? OFFSET ?
                """, (limit, offset))
                
                rows = cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                
                history = []
                for row in rows:
                    check_record = dict(zip(columns, row))
                    
                    # Parse JSON fields
                    if check_record.get('broken_links'):
                        try:
                            check_record['broken_links'] = json.loads(check_record['broken_links'])
                        except json.JSONDecodeError:
                            check_record['broken_links'] = []
                    
                    if check_record.get('missing_meta_tags'):
                        try:
                            check_record['missing_meta_tags'] = json.loads(check_record['missing_meta_tags'])
                        except json.JSONDecodeError:
                            check_record['missing_meta_tags'] = []
                    
                    if check_record.get('all_pages'):
                        try:
                            check_record['all_pages'] = json.loads(check_record['all_pages'])
                        except json.JSONDecodeError:
                            check_record['all_pages'] = []
                    
                    if check_record.get('performance_metrics'):
                        try:
                            check_record['performance_metrics'] = json.loads(check_record['performance_metrics'])
                        except json.JSONDecodeError:
                            check_record['performance_metrics'] = {}
                    
                    if check_record.get('blur_detection_results'):
                        try:
                            check_record['blur_detection_results'] = json.loads(check_record['blur_detection_results'])
                        except json.JSONDecodeError:
                            check_record['blur_detection_results'] = {}
                    
                    # Convert boolean fields
                    check_record['significant_change_detected'] = bool(check_record['significant_change_detected'])
                    
                    history.append(check_record)
                
                return history
                
        except Exception as e:
            self.logger.error(f"Error getting all history: {e}")
            return []

    def get_history_by_status(self, status: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get check history records by status."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM check_history 
                    WHERE status = ? 
                    ORDER BY timestamp_utc DESC 
                    LIMIT ?
                """, (status, limit))
                
                rows = cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                
                history = []
                for row in rows:
                    check_record = dict(zip(columns, row))
                    
                    # Parse JSON fields (same as above)
                    for json_field in ['broken_links', 'missing_meta_tags', 'all_pages', 'performance_metrics', 'blur_detection_results']:
                        if check_record.get(json_field):
                            try:
                                check_record[json_field] = json.loads(check_record[json_field])
                            except json.JSONDecodeError:
                                check_record[json_field] = [] if json_field in ['broken_links', 'missing_meta_tags', 'all_pages'] else {}
                    
                    # Convert boolean fields
                    check_record['significant_change_detected'] = bool(check_record['significant_change_detected'])
                    
                    history.append(check_record)
                
                return history
                
        except Exception as e:
            self.logger.error(f"Error getting history by status {status}: {e}")
            return []

    def get_history_count(self, site_id: str = None) -> int:
        """Get the count of check history records."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if site_id:
                    cursor.execute("SELECT COUNT(*) FROM check_history WHERE site_id = ?", (site_id,))
                else:
                    cursor.execute("SELECT COUNT(*) FROM check_history")
                
                return cursor.fetchone()[0]
                
        except Exception as e:
            self.logger.error(f"Error getting history count: {e}")
            return 0

    def update_check_record(self, check_id: str, updates: Dict[str, Any]) -> bool:
        """Update an existing check record."""
        try:
            # Build dynamic UPDATE query
            set_clauses = []
            values = []
            
            for key, value in updates.items():
                if key in ['broken_links', 'missing_meta_tags', 'all_pages', 'performance_metrics', 'blur_detection_results']:
                    # JSON fields
                    set_clauses.append(f"{key} = ?")
                    values.append(json.dumps(value))
                elif key == 'significant_change_detected':
                    # Boolean field
                    set_clauses.append(f"{key} = ?")
                    values.append(1 if value else 0)
                else:
                    # Regular fields
                    set_clauses.append(f"{key} = ?")
                    values.append(value)
            
            if not set_clauses:
                return False
            
            values.append(check_id)  # For WHERE clause
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                query = f"UPDATE check_history SET {', '.join(set_clauses)} WHERE check_id = ?"
                cursor.execute(query, values)
                
                if cursor.rowcount > 0:
                    conn.commit()
                    self.logger.info(f"Updated check record {check_id}")
                    return True
                else:
                    self.logger.warning(f"Check record {check_id} not found for update")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Error updating check record {check_id}: {e}")
            return False

    def delete_check_record(self, check_id: str) -> bool:
        """Delete a check record."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM check_history WHERE check_id = ?", (check_id,))
                
                if cursor.rowcount > 0:
                    conn.commit()
                    self.logger.info(f"Deleted check record {check_id}")
                    return True
                else:
                    self.logger.warning(f"Check record {check_id} not found for deletion")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Error deleting check record {check_id}: {e}")
            return False

    def cleanup_old_records(self, days_to_keep: int = 90) -> int:
        """Clean up old check history records."""
        try:
            cutoff_date = datetime.now(timezone.utc).replace(tzinfo=timezone.utc)
            cutoff_date = cutoff_date.replace(day=cutoff_date.day - days_to_keep)
            cutoff_iso = cutoff_date.isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM check_history WHERE timestamp_utc < ?", (cutoff_iso,))
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                if deleted_count > 0:
                    self.logger.info(f"Cleaned up {deleted_count} old check history records")
                
                return deleted_count
                
        except Exception as e:
            self.logger.error(f"Error cleaning up old records: {e}")
            return 0

    def backup_history(self, backup_path: str) -> bool:
        """Create a backup of all check history data."""
        try:
            history = self.get_all_history(limit=1000000)  # Get all records
            
            # Ensure backup directory exists
            backup_dir = os.path.dirname(backup_path)
            if backup_dir and not os.path.exists(backup_dir):
                os.makedirs(backup_dir, exist_ok=True)
            
            # Write backup file
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2)
            
            self.logger.info(f"Created history backup at: {clean_path_for_logging(backup_path)}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error creating history backup: {e}")
            return False

# For backward compatibility, provide the same interface
HistoryManager = HistoryManagerSQLite
