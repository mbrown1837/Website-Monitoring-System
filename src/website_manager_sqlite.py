"""
SQLite-based Website Manager

This module provides website management functionality using SQLite database
instead of JSON files for better data consistency and performance.
"""

import sqlite3
import json
import os
import uuid
import shutil
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from src.config_loader import get_config
from src.logger_setup import setup_logging
import src.content_retriever as content_retriever
import src.snapshot_tool as snapshot_tool
from urllib.parse import urlparse
from .path_utils import get_project_root, resolve_path, clean_path_for_logging

class WebsiteManagerSQLite:
    def __init__(self, config_path=None):
        # Set up basics
        if config_path:
            self.config = get_config(config_path=config_path)
            self.logger = setup_logging(config_path=config_path)
        else:
            self.config = get_config()
            self.logger = setup_logging()
        
        self.db_path = self._initialize_database_path()
        self._websites_cache = {}  # Cache
        self._websites_loaded = False
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
        """Ensure the websites table exists in the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if websites table exists
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='websites'
                """)
                
                if not cursor.fetchone():
                    self.logger.info("Websites table not found, creating it...")
                    self._create_websites_table()
                else:
                    self.logger.debug("Websites table already exists")
                    self._migrate_schema()
                    
        except Exception as e:
            self.logger.error(f"Error ensuring tables exist: {e}")
            raise

    def _migrate_schema(self):
        """Check for schema updates and apply them."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(websites)")
                columns = [col[1] for col in cursor.fetchall()]
                
                if 'check_interval_minutes' not in columns:
                    self.logger.info("Adding 'check_interval_minutes' column to websites table.")
                    cursor.execute("ALTER TABLE websites ADD COLUMN check_interval_minutes INTEGER DEFAULT 60 NOT NULL")
                    
                    if 'interval' in columns:
                        self.logger.info("Migrating data from deprecated 'interval' column to 'check_interval_minutes'.")
                        cursor.execute("UPDATE websites SET check_interval_minutes = interval * 60")
                        conn.commit()
                
                conn.commit()
        except Exception as e:
            self.logger.error(f"An error occurred during schema migration: {e}", exc_info=True)

    def _create_websites_table(self):
        """Create the websites table if it doesn't exist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS websites (
                        id TEXT PRIMARY KEY,
                        url TEXT NOT NULL,
                        name TEXT NOT NULL,
                        check_interval_minutes INTEGER DEFAULT 60 NOT NULL,
                        is_active BOOLEAN DEFAULT 1,
                        tags TEXT,  -- JSON string
                        notification_emails TEXT,  -- JSON string
                        created_utc TEXT NOT NULL,
                        last_updated_utc TEXT NOT NULL,
                        render_delay INTEGER DEFAULT 6,
                        max_crawl_depth INTEGER DEFAULT 2,
                        visual_diff_threshold INTEGER DEFAULT 5,
                        capture_subpages BOOLEAN DEFAULT 1,
                        all_baselines TEXT,  -- JSON string
                        has_subpage_baselines BOOLEAN DEFAULT 0,
                        baseline_visual_path TEXT,
                        enable_blur_detection BOOLEAN DEFAULT 0,
                        blur_detection_scheduled BOOLEAN DEFAULT 0,
                        blur_detection_manual BOOLEAN DEFAULT 1,
                        auto_crawl_enabled BOOLEAN DEFAULT 1,
                        auto_visual_enabled BOOLEAN DEFAULT 1,
                        auto_blur_enabled BOOLEAN DEFAULT 1,
                        auto_performance_enabled BOOLEAN DEFAULT 1,
                        auto_full_check_enabled BOOLEAN DEFAULT 1,
                        baseline_visual_path_web TEXT
                    )
                """)
                
                # Create indexes for better performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_websites_url ON websites(url)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_websites_active ON websites(is_active)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_websites_created ON websites(created_utc)")
                
                conn.commit()
                self.logger.info("Websites table created successfully")
                
        except Exception as e:
            self.logger.error(f"Error creating websites table: {e}")
            raise

    def _load_websites(self, force_reload=False):
        """Load websites from SQLite database into cache."""
        if self._websites_loaded and not force_reload:
            return self._websites_cache
            
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM websites")
                rows = cursor.fetchall()
                
                # Get column names
                columns = [description[0] for description in cursor.description]
                
                # Convert rows to dictionaries
                websites = []
                for row in rows:
                    website = dict(zip(columns, row))
                    
                    # Parse JSON fields
                    if website.get('tags'):
                        try:
                            website['tags'] = json.loads(website['tags'])
                        except json.JSONDecodeError:
                            website['tags'] = []
                    
                    if website.get('notification_emails'):
                        try:
                            website['notification_emails'] = json.loads(website['notification_emails'])
                        except json.JSONDecodeError:
                            website['notification_emails'] = []
                    
                    if website.get('all_baselines'):
                        try:
                            website['all_baselines'] = json.loads(website['all_baselines'])
                        except json.JSONDecodeError:
                            website['all_baselines'] = {}
                    
                    # Convert boolean fields
                    website['is_active'] = bool(website['is_active'])
                    website['capture_subpages'] = bool(website['capture_subpages'])
                    website['has_subpage_baselines'] = bool(website['has_subpage_baselines'])
                    website['enable_blur_detection'] = bool(website['enable_blur_detection'])
                    website['blur_detection_scheduled'] = bool(website['blur_detection_scheduled'])
                    website['blur_detection_manual'] = bool(website['blur_detection_manual'])
                    website['auto_crawl_enabled'] = bool(website['auto_crawl_enabled'])
                    website['auto_visual_enabled'] = bool(website['auto_visual_enabled'])
                    website['auto_blur_enabled'] = bool(website['auto_blur_enabled'])
                    website['auto_performance_enabled'] = bool(website['auto_performance_enabled'])
                    website['auto_full_check_enabled'] = bool(website['auto_full_check_enabled'])
                    
                    websites.append(website)
                
                self._websites_cache = {website['id']: website for website in websites}
                self._websites_loaded = True
                
                self.logger.debug(f"Successfully loaded {len(websites)} websites from SQLite database")
                return self._websites_cache
                
        except Exception as e:
            self.logger.error(f"Error loading websites from SQLite database: {e}")
            self._websites_cache = {}
            self._websites_loaded = True
            return self._websites_cache

    def _save_website(self, website: Dict[str, Any]) -> bool:
        """Save a single website to SQLite database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Prepare data for insertion/update
                data = (
                    website.get('id'),
                    website.get('url'),
                    website.get('name'),
                    website.get('check_interval_minutes', 60),
                    1 if website.get('is_active', True) else 0,
                    json.dumps(website.get('tags', [])),
                    json.dumps(website.get('notification_emails', [])),
                    website.get('created_utc'),
                    website.get('last_updated_utc'),
                    website.get('render_delay', 6),
                    website.get('max_crawl_depth', 2),
                    website.get('visual_diff_threshold', 5),
                    1 if website.get('capture_subpages', True) else 0,
                    json.dumps(website.get('all_baselines', {})),
                    1 if website.get('has_subpage_baselines', False) else 0,
                    website.get('baseline_visual_path'),
                    1 if website.get('enable_blur_detection', False) else 0,
                    1 if website.get('blur_detection_scheduled', False) else 0,
                    1 if website.get('blur_detection_manual', True) else 0,
                    1 if website.get('auto_crawl_enabled', True) else 0,
                    1 if website.get('auto_visual_enabled', True) else 0,
                    1 if website.get('auto_blur_enabled', True) else 0,
                    1 if website.get('auto_performance_enabled', True) else 0,
                    1 if website.get('auto_full_check_enabled', True) else 0,
                    website.get('baseline_visual_path_web')
                )
                
                # Use UPSERT (INSERT OR REPLACE) for simplicity
                cursor.execute("""
                    INSERT OR REPLACE INTO websites (
                        id, url, name, check_interval_minutes, is_active, tags, notification_emails,
                        created_utc, last_updated_utc, render_delay, max_crawl_depth,
                        visual_diff_threshold, capture_subpages, all_baselines,
                        has_subpage_baselines, baseline_visual_path, enable_blur_detection,
                        blur_detection_scheduled, blur_detection_manual, auto_crawl_enabled,
                        auto_visual_enabled, auto_blur_enabled, auto_performance_enabled,
                        auto_full_check_enabled, baseline_visual_path_web
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, data)
                
                conn.commit()
                self.logger.debug(f"Successfully saved website {website.get('id')} to SQLite database")
                return True
                
        except Exception as e:
            self.logger.error(f"Error saving website to SQLite database: {e}")
            return False

    def list_websites(self) -> Dict[str, Dict[str, Any]]:
        """List all websites."""
        return self._load_websites()

    def get_website(self, website_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific website by ID."""
        websites = self._load_websites()
        return websites.get(website_id)

    def add_website(self, website_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new website."""
        # Generate ID if not provided
        if 'id' not in website_data:
            website_data['id'] = str(uuid.uuid4())
        
        # Set timestamps
        now = datetime.now(timezone.utc).isoformat()
        if 'created_utc' not in website_data:
            website_data['created_utc'] = now
        website_data['last_updated_utc'] = now
        
        # Save to database
        if self._save_website(website_data):
            # Update cache
            self._websites_cache[website_data['id']] = website_data
            self.logger.info(f"Added new website: {website_data.get('name')} ({website_data['id']})")
            return website_data
        else:
            raise Exception("Failed to save website to database")

    def update_website(self, website_id: str, updates: Dict[str, Any]) -> bool:
        """Update an existing website."""
        website = self.get_website(website_id)
        if not website:
            self.logger.warning(f"Website {website_id} not found for update")
            return False
        
        # Update fields
        website.update(updates)
        website['last_updated_utc'] = datetime.now(timezone.utc).isoformat()
        
        # Save to database
        if self._save_website(website):
            # Update cache
            self._websites_cache[website_id] = website
            self.logger.info(f"Updated website: {website.get('name')} ({website_id})")
            return True
        else:
            return False

    def remove_website(self, website_id: str) -> bool:
        """Remove a website."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM websites WHERE id = ?", (website_id,))
                
                if cursor.rowcount > 0:
                    conn.commit()
                    # Remove from cache
                    if website_id in self._websites_cache:
                        del self._websites_cache[website_id]
                    
                    # Clean up scheduler task for this website
                    try:
                        from .scheduler_integration import remove_site_scheduler_task
                        remove_site_scheduler_task(website_id)
                        self.logger.info(f"Removed scheduler task for website {website_id}")
                    except Exception as scheduler_error:
                        self.logger.warning(f"Could not remove scheduler task for website {website_id}: {scheduler_error}")
                    
                    self.logger.info(f"Removed website {website_id}")
                    return True
                else:
                    self.logger.warning(f"Website {website_id} not found for removal")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Error removing website {website_id}: {e}")
            return False

    def get_active_websites(self) -> List[Dict[str, Any]]:
        """Get all active websites."""
        websites = self._load_websites()
        return [website for website in websites.values() if website.get('is_active', False)]

    def get_websites_by_tag(self, tag: str) -> List[Dict[str, Any]]:
        """Get websites by tag."""
        websites = self._load_websites()
        return [website for website in websites.values() 
                if tag in website.get('tags', [])]

    def search_websites(self, query: str) -> List[Dict[str, Any]]:
        """Search websites by name or URL."""
        websites = self._load_websites()
        query_lower = query.lower()
        
        results = []
        for website in websites.values():
            if (query_lower in website.get('name', '').lower() or 
                query_lower in website.get('url', '').lower()):
                results.append(website)
        
        return results

    def get_website_count(self) -> int:
        """Get total number of websites."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM websites")
                return cursor.fetchone()[0]
        except Exception as e:
            self.logger.error(f"Error getting website count: {e}")
            return 0

    def get_websites_created_since(self, since_date: datetime) -> List[Dict[str, Any]]:
        """Get websites created since a specific date."""
        websites = self._load_websites()
        since_iso = since_date.isoformat()
        
        return [website for website in websites.values() 
                if website.get('created_utc', '') >= since_iso]

    def backup_websites(self, backup_path: str) -> bool:
        """Create a backup of all websites data."""
        try:
            websites = self._load_websites()
            
            # Ensure backup directory exists
            backup_dir = os.path.dirname(backup_path)
            if backup_dir and not os.path.exists(backup_dir):
                os.makedirs(backup_dir, exist_ok=True)
            
            # Write backup file
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(list(websites.values()), f, indent=2)
            
            self.logger.info(f"Created websites backup at: {clean_path_for_logging(backup_path)}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error creating websites backup: {e}")
            return False

    def restore_websites_from_backup(self, backup_path: str) -> bool:
        """Restore websites from a backup file."""
        try:
            if not os.path.exists(backup_path):
                self.logger.error(f"Backup file not found: {backup_path}")
                return False
            
            with open(backup_path, 'r', encoding='utf-8') as f:
                websites_data = json.load(f)
            
            # Clear existing data
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM websites")
                conn.commit()
            
            # Restore websites
            for website in websites_data:
                if not self._save_website(website):
                    self.logger.error(f"Failed to restore website: {website.get('id')}")
                    return False
            
            # Clear cache and reload
            self._websites_cache = {}
            self._websites_loaded = False
            self._load_websites(force_reload=True)
            
            self.logger.info(f"Successfully restored {len(websites_data)} websites from backup")
            return True
            
        except Exception as e:
            self.logger.error(f"Error restoring websites from backup: {e}")
            return False

    def get_automated_check_config(self, website_id):
        """Get automated monitoring configuration for a website."""
        website = self.get_website(website_id)
        if not website:
            return None
        
        # Check if Full Check is enabled
        if website.get('auto_full_check_enabled', False):
            # If Full Check is enabled, enable all monitoring types
            return {
                'crawl_enabled': True,
                'visual_enabled': True,
                'blur_enabled': True,
                'performance_enabled': True
            }
        else:
            # Otherwise, use individual settings
            return {
                'crawl_enabled': website.get('auto_crawl_enabled', True),
                'visual_enabled': website.get('auto_visual_enabled', True),
                'blur_enabled': website.get('auto_blur_enabled', False),
                'performance_enabled': website.get('auto_performance_enabled', False)
            }
    
    def get_manual_check_config(self, check_type):
        """Get manual check configuration based on button pressed."""
        configs = {
            'full': {'crawl_enabled': True, 'visual_enabled': True, 'blur_enabled': True, 'performance_enabled': True},
            'visual': {'crawl_enabled': False, 'visual_enabled': True, 'blur_enabled': False, 'performance_enabled': False},
            'crawl': {'crawl_enabled': True, 'visual_enabled': False, 'blur_enabled': False, 'performance_enabled': False},
            'blur': {'crawl_enabled': False, 'visual_enabled': False, 'blur_enabled': True, 'performance_enabled': False},
            'performance': {'crawl_enabled': False, 'visual_enabled': False, 'blur_enabled': False, 'performance_enabled': True}
        }
        return configs.get(check_type, configs['full'])

# For backward compatibility, provide the same interface
WebsiteManager = WebsiteManagerSQLite
