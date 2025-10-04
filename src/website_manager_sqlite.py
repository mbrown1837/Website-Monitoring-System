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
from src.path_utils import get_project_root, resolve_path, clean_path_for_logging

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
                
                # Add exclude_pages_keywords field for per-site exclude pages configuration
                if 'exclude_pages_keywords' not in columns:
                    self.logger.info("Adding 'exclude_pages_keywords' column to websites table.")
                    cursor.execute("ALTER TABLE websites ADD COLUMN exclude_pages_keywords TEXT DEFAULT NULL")
                    conn.commit()
                
                conn.commit()
        except Exception as e:
            self.logger.error(f"An error occurred during schema migration: {e}", exc_info=True)

    def _create_websites_table(self):
        """Create the websites table if it doesn't exist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create websites table
                
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
                        baseline_visual_path_web TEXT,
                        exclude_pages_keywords TEXT  -- JSON string for per-site exclude pages
                    )
                """)
                
                # Create indexes for better performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_websites_url ON websites(url)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_websites_active ON websites(is_active)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_websites_created ON websites(created_utc)")
                
                # Create manual check queue table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS manual_check_queue (
                        id TEXT PRIMARY KEY,
                        website_id TEXT NOT NULL,
                        check_type TEXT NOT NULL,  -- 'crawl', 'visual', 'blur', 'performance', 'full'
                        status TEXT NOT NULL DEFAULT 'pending',  -- 'pending', 'processing', 'completed', 'failed'
                        priority INTEGER DEFAULT 1,  -- 1 = high (manual), 0 = normal (scheduled)
                        created_utc TEXT NOT NULL,
                        started_utc TEXT,
                        completed_utc TEXT,
                        error_message TEXT,
                        result_data TEXT,  -- JSON string for results
                        user_id TEXT,  -- Optional user identifier
                        FOREIGN KEY (website_id) REFERENCES websites(id) ON DELETE CASCADE
                    )
                """)
                
                # Create indexes for queue performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_queue_status ON manual_check_queue(status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_queue_priority ON manual_check_queue(priority DESC, created_utc ASC)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_queue_website ON manual_check_queue(website_id)")
                
                conn.commit()
                self.logger.info("Websites and queue tables created successfully")
                
        except Exception as e:
            self.logger.error(f"Error creating tables: {e}")
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
                            self.logger.info(f"DEBUG: Loading all_baselines from database: {website['all_baselines']}")
                            website['all_baselines'] = json.loads(website['all_baselines'])
                            self.logger.info(f"DEBUG: Parsed all_baselines: {website['all_baselines']}")
                        except json.JSONDecodeError as e:
                            self.logger.error(f"DEBUG: Failed to parse all_baselines: {e}")
                            website['all_baselines'] = {}
                    else:
                        self.logger.info(f"DEBUG: No all_baselines found in database for website {website.get('id')}")
                        website['all_baselines'] = {}
                    
                    if website.get('exclude_pages_keywords'):
                        try:
                            website['exclude_pages_keywords'] = json.loads(website['exclude_pages_keywords'])
                        except json.JSONDecodeError:
                            website['exclude_pages_keywords'] = []
                    else:
                        website['exclude_pages_keywords'] = []
                    
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
                    
                    # Add last checked information
                    try:
                        from src.history_manager_sqlite import HistoryManager
                        history_manager = HistoryManager()
                        latest_check = history_manager.get_latest_check_for_site(website['id'])
                        if latest_check and latest_check.get('timestamp'):
                            # Convert timestamp to readable format
                            from datetime import datetime
                            try:
                                check_time = datetime.fromisoformat(latest_check['timestamp'].replace('Z', '+00:00'))
                                website['last_checked_simple'] = check_time.strftime('%Y-%m-%d %H:%M UTC')
                            except:
                                website['last_checked_simple'] = 'Recently'
                        else:
                            website['last_checked_simple'] = 'Never'
                    except Exception as e:
                        self.logger.debug(f"Could not get last check time for website {website['id']}: {e}")
                        website['last_checked_simple'] = 'Never'
                    
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
                all_baselines_data = website.get('all_baselines', {})
                self.logger.info(f"DEBUG: Saving all_baselines to database: {all_baselines_data}")
                self.logger.info(f"DEBUG: all_baselines type: {type(all_baselines_data)}")
                
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
                    json.dumps(all_baselines_data),
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
                    website.get('baseline_visual_path_web'),
                    json.dumps(website.get('exclude_pages_keywords', []))
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
                        auto_full_check_enabled, baseline_visual_path_web, exclude_pages_keywords
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        # First try to get from cache without reloading
        if self._websites_loaded and website_id in self._websites_cache:
            return self._websites_cache.get(website_id)
        
        # If not in cache, force reload and try again
        websites = self._load_websites(force_reload=True)
        return websites.get(website_id)

    def add_website(self, website_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new website."""
        # Generate ID if not provided
        if 'id' not in website_data:
            website_data['id'] = str(uuid.uuid4())
        
        # Ensure new websites are active by default
        if 'is_active' not in website_data:
            website_data['is_active'] = True
        
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
            # Sync JSON file to keep everything in sync
            self._sync_json_file()
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
        
        # Debug logging for all_baselines updates
        if 'all_baselines' in updates:
            self.logger.info(f"DEBUG: Updating all_baselines for {website_id}: {updates['all_baselines']}")
            self.logger.info(f"DEBUG: Website all_baselines after update: {website.get('all_baselines')}")
        
        # Save to database
        if self._save_website(website):
            # Update cache
            self._websites_cache[website_id] = website
            self.logger.info(f"Updated website: {website.get('name')} ({website_id})")
            # Sync JSON file to keep everything in sync
            self._sync_json_file()
            return True
        else:
            return False

    def remove_website(self, website_id: str) -> bool:
        """Remove a website and all its associated data."""
        try:
            # Get website details before deletion for cleanup
            website = self.get_website(website_id)
            if not website:
                self.logger.warning(f"Website {website_id} not found for removal")
                return False
            
            website_name = website.get('name', 'Unknown')
            website_url = website.get('url', 'Unknown')
            
            self.logger.info(f"Starting comprehensive cleanup for website: {website_name} ({website_url})")
            
            # 1. Clean up database records
            cleanup_success = self._cleanup_website_database_records(website_id)
            
            # 2. Clean up snapshot files and directories
            snapshot_cleanup_success = self._cleanup_website_snapshots(website_id, website)
            
            # 3. Clean up scheduler task
            scheduler_cleanup_success = self._cleanup_website_scheduler_task(website_id)
            
            # 4. Remove from cache
            if website_id in self._websites_cache:
                del self._websites_cache[website_id]
            
            # 5. Remove from websites table
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM websites WHERE id = ?", (website_id,))
                conn.commit()
            
            # 6. Sync JSON file to keep everything in sync
            self._sync_json_file()
            
            # Log cleanup results
            self.logger.info(f"Website cleanup completed for {website_name}:")
            self.logger.info(f"  - Database records: {'✅' if cleanup_success else '❌'}")
            self.logger.info(f"  - Snapshot files: {'✅' if snapshot_cleanup_success else '❌'}")
            self.logger.info(f"  - Scheduler task: {'✅' if scheduler_cleanup_success else '❌'}")
            self.logger.info(f"  - JSON file sync: ✅")
            
            self.logger.info(f"Successfully removed website {website_name} and all associated data")
            return True
                    
        except Exception as e:
            self.logger.error(f"Error removing website {website_id}: {e}", exc_info=True)
            return False

    def _cleanup_website_database_records(self, website_id: str) -> bool:
        """Clean up all database records associated with a website."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # List of tables to clean up with their website ID column names
                cleanup_tables = {
                    'check_history': 'site_id',
                    'crawl_history': 'site_id', 
                    'crawl_results': 'site_id',
                    'broken_links': 'site_id',
                    'missing_meta_tags': 'site_id',
                    'manual_check_queue': 'website_id',
                    'scheduler_log': 'website_id',
                    'scheduler_status': 'website_id',  # This table doesn't have website_id column
                    'scheduler_metrics': 'website_id',
                    'blur_detection_results': 'site_id',
                    'performance_results': 'site_id'
                }
                
                total_deleted = 0
                for table, id_column in cleanup_tables.items():
                    try:
                        # Check if table exists
                        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
                        if cursor.fetchone():
                            # Check if the ID column exists in this table
                            cursor.execute(f"PRAGMA table_info({table})")
                            columns = [col[1] for col in cursor.fetchall()]
                            
                            if id_column in columns:
                            # Delete records for this website
                                cursor.execute(f"DELETE FROM {table} WHERE {id_column} = ?", (website_id,))
                            deleted_count = cursor.rowcount
                            total_deleted += deleted_count
                            if deleted_count > 0:
                                self.logger.info(f"Deleted {deleted_count} records from {table}")
                            else:
                                self.logger.debug(f"Table {table} does not have column {id_column}, skipping")
                    except Exception as table_error:
                        self.logger.warning(f"Could not clean up table {table}: {table_error}")
                
                    conn.commit()
                self.logger.info(f"Database cleanup completed: {total_deleted} total records deleted")
                return True
                
        except Exception as e:
            self.logger.error(f"Error cleaning up database records for website {website_id}: {e}")
            return False

    def _cleanup_website_snapshots(self, website_id: str, website: Dict[str, Any]) -> bool:
        """Clean up all snapshot files and directories for a website."""
        try:
            import shutil
            import os
            from pathlib import Path
            
            # Get snapshot directory from config
            snapshot_base_dir = self.config.get('snapshot_directory', 'data/snapshots')
            if not os.path.isabs(snapshot_base_dir):
                # Make it relative to project root
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                snapshot_base_dir = os.path.join(project_root, snapshot_base_dir)
            
            # Find website-specific directories
            website_name = website.get('name', 'Unknown')
            website_url = website.get('url', 'Unknown')
            
            # Try different directory naming patterns
            domain_patterns = []
            
            # Extract domain from URL
            if website_url and website_url != 'Unknown':
                from urllib.parse import urlparse
                parsed_url = urlparse(website_url)
                domain = parsed_url.netloc.replace('.', '_').replace(':', '_')
                domain_patterns.append(domain)
            
            # Also try website name as directory name
            if website_name and website_name != 'Unknown':
                safe_name = website_name.replace('.', '_').replace(':', '_').replace('/', '_')
                domain_patterns.append(safe_name)
            
            # Look for directories containing the website_id
            snapshot_path = Path(snapshot_base_dir)
            if snapshot_path.exists():
                deleted_dirs = []
                deleted_files = 0
                
                # Find all directories that might contain this website's data
                for item in snapshot_path.iterdir():
                    if item.is_dir():
                        # Check if this directory contains our website_id
                        website_id_dir = item / website_id
                        if website_id_dir.exists():
                            # This directory contains our website's data
                            try:
                                # Count files before deletion (including all subdirectories)
                                file_count = sum(1 for f in website_id_dir.rglob('*') if f.is_file())
                                deleted_files += file_count
                                
                                # Remove the entire website_id directory (includes baseline, visual, blur_images, etc.)
                                shutil.rmtree(website_id_dir)
                                deleted_dirs.append(str(website_id_dir))
                                self.logger.info(f"Deleted directory: {website_id_dir} ({file_count} files)")
                            except Exception as dir_error:
                                self.logger.warning(f"Could not delete directory {website_id_dir}: {dir_error}")
                        
                        # Also check for blur_images directory pattern
                        blur_images_dir = item / f"{website_id}_blur_images"
                        if blur_images_dir.exists():
                            try:
                                file_count = sum(1 for f in blur_images_dir.rglob('*') if f.is_file())
                                deleted_files += file_count
                                shutil.rmtree(blur_images_dir)
                                deleted_dirs.append(str(blur_images_dir))
                                self.logger.info(f"Deleted blur images directory: {blur_images_dir} ({file_count} files)")
                            except Exception as dir_error:
                                self.logger.warning(f"Could not delete blur images directory {blur_images_dir}: {dir_error}")
                
                # Also check for domain-based directories
                for domain_pattern in domain_patterns:
                    domain_dir = snapshot_path / domain_pattern
                    if domain_dir.exists():
                        website_id_dir = domain_dir / website_id
                        if website_id_dir.exists():
                            try:
                                file_count = sum(1 for f in website_id_dir.rglob('*') if f.is_file())
                                deleted_files += file_count
                                shutil.rmtree(website_id_dir)
                                deleted_dirs.append(str(website_id_dir))
                                self.logger.info(f"Deleted domain directory: {website_id_dir} ({file_count} files)")
                            except Exception as dir_error:
                                self.logger.warning(f"Could not delete domain directory {website_id_dir}: {dir_error}")
                
                # Clean up empty parent directories
                for deleted_dir in deleted_dirs:
                    parent_dir = Path(deleted_dir).parent
                    try:
                        if parent_dir.exists() and not any(parent_dir.iterdir()):
                            parent_dir.rmdir()
                            self.logger.info(f"Removed empty parent directory: {parent_dir}")
                    except Exception as parent_error:
                        self.logger.debug(f"Could not remove empty parent directory {parent_dir}: {parent_error}")
                
                self.logger.info(f"Snapshot cleanup completed: {len(deleted_dirs)} directories, {deleted_files} files deleted")
                return True
            else:
                self.logger.info("Snapshot directory does not exist, nothing to clean up")
                return True
                
        except Exception as e:
            self.logger.error(f"Error cleaning up snapshots for website {website_id}: {e}")
            return False
                    
    def _cleanup_website_scheduler_task(self, website_id: str) -> bool:
        """Clean up scheduler task for a website."""
        try:
            # Try enhanced scheduler first
            try:
                from .enhanced_scheduler import remove_website_from_scheduler
                if remove_website_from_scheduler(website_id):
                    self.logger.info(f"Removed website {website_id} from enhanced scheduler")
                    return True
            except ImportError:
                pass
            
            # Fallback to old scheduler integration
            try:
                from .scheduler_integration import remove_site_scheduler_task
                remove_site_scheduler_task(website_id)
                self.logger.info(f"Removed scheduler task for website {website_id}")
                return True
            except ImportError:
                pass
                
            return True
        except Exception as e:
            self.logger.warning(f"Could not remove scheduler task for website {website_id}: {e}")
            return False

    def _sync_json_file(self):
        """Sync the JSON file with the current database state."""
        try:
            import json
            import os
            
            # Get current websites from database
            websites = self.list_websites()
            
            # Convert to list format for JSON
            websites_list = []
            for site_id, website in websites.items():
                websites_list.append(website)
            
            # Write to JSON file
            json_path = 'data/websites.json'
            with open(json_path, 'w') as f:
                json.dump(websites_list, f, indent=2)
            
            self.logger.info(f"Synced JSON file with {len(websites_list)} websites")
            
        except Exception as e:
            self.logger.warning(f"Could not sync JSON file: {e}")

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
    
    def invalidate_website_cache(self, website_id: str = None):
        """Invalidate website cache to force reload of latest data (including last checked time)."""
        try:
            if website_id:
                # Invalidate specific website from cache
                if website_id in self._websites_cache:
                    del self._websites_cache[website_id]
                    self.logger.debug(f"Invalidated cache for website {website_id}")
            else:
                # Invalidate entire cache
                self._websites_cache = {}
                self._websites_loaded = False
                self.logger.debug("Invalidated entire website cache")
        except Exception as e:
            self.logger.error(f"Error invalidating website cache: {e}")

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
    
    def get_manual_check_config(self, website_id, check_type):
        """Get manual check configuration based on button pressed and website settings."""
        # Get website configuration to check if specific checks are enabled
        website = self.get_website(website_id)
        if not website:
            self.logger.warning(f"Website {website_id} not found for manual check config")
            # Return default config if website not found
            return {'crawl_enabled': True, 'visual_enabled': True, 'blur_enabled': True, 'performance_enabled': True}
        
        # Base configurations for each check type
        base_configs = {
            'full': {'crawl_enabled': True, 'visual_enabled': True, 'blur_enabled': True, 'performance_enabled': True},
            'visual': {'crawl_enabled': False, 'visual_enabled': True, 'blur_enabled': False, 'performance_enabled': False},
            'crawl': {'crawl_enabled': True, 'visual_enabled': False, 'blur_enabled': False, 'performance_enabled': False},
            'blur': {'crawl_enabled': False, 'visual_enabled': False, 'blur_enabled': True, 'performance_enabled': False},
            'performance': {'crawl_enabled': False, 'visual_enabled': False, 'blur_enabled': False, 'performance_enabled': True},
            'baseline': {'crawl_enabled': False, 'visual_enabled': True, 'blur_enabled': False, 'performance_enabled': False}  # Baseline only creates visual snapshots
        }
        
        # Get base config for the check type
        config = base_configs.get(check_type, base_configs['full']).copy()
        
        # For manual checks, respect website-specific settings
        # If a specific check is disabled for the website, disable it in the config
        if not website.get('auto_crawl_enabled', True):
            config['crawl_enabled'] = False
        if not website.get('auto_visual_enabled', True):
            config['visual_enabled'] = False
        if not website.get('auto_blur_enabled', False):
            config['blur_enabled'] = False
        if not website.get('auto_performance_enabled', False):
            config['performance_enabled'] = False
        
        self.logger.debug(f"Manual check config for website {website_id}, type {check_type}: {config}")
        return config
    
    # ==================== QUEUE MANAGEMENT METHODS ====================
    
    def add_to_queue(self, website_id, check_type, user_id=None):
        """Add a manual check to the queue with high priority and duplicate prevention."""
        try:
            # Check for existing pending/processing items for the same website and check type
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id FROM manual_check_queue 
                    WHERE website_id = ? AND check_type = ? AND status IN ('pending', 'processing')
                    ORDER BY created_utc DESC
                    LIMIT 1
                """, (website_id, check_type))
                
                existing_item = cursor.fetchone()
                if existing_item:
                    existing_id = existing_item[0]
                    self.logger.warning(f"Duplicate check prevented: {check_type} check for website {website_id} already exists (ID: {existing_id})")
                    return existing_id  # Return existing ID instead of creating duplicate
            
            # No duplicate found, create new queue item
            queue_id = str(uuid.uuid4())
            created_utc = datetime.now(timezone.utc).isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO manual_check_queue 
                    (id, website_id, check_type, status, priority, created_utc, user_id)
                    VALUES (?, ?, ?, 'pending', 1, ?, ?)
                """, (queue_id, website_id, check_type, created_utc, user_id))
                conn.commit()
                
            self.logger.info(f"Added {check_type} check for website {website_id} to queue (ID: {queue_id})")
            return queue_id
            
        except Exception as e:
            self.logger.error(f"Error adding check to queue: {e}")
            raise
    
    def get_queue_status(self, queue_id=None, website_id=None):
        """Get queue status for a specific check or all pending checks."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if queue_id:
                    cursor.execute("""
                        SELECT q.*, w.name as website_name, w.url as website_url
                        FROM manual_check_queue q
                        JOIN websites w ON q.website_id = w.id
                        WHERE q.id = ?
                    """, (queue_id,))
                elif website_id:
                    cursor.execute("""
                        SELECT q.*, w.name as website_name, w.url as website_url
                        FROM manual_check_queue q
                        JOIN websites w ON q.website_id = w.id
                        WHERE q.website_id = ? AND q.status IN ('pending', 'processing')
                        ORDER BY q.priority DESC, q.created_utc ASC
                    """, (website_id,))
                else:
                    cursor.execute("""
                        SELECT q.*, w.name as website_name, w.url as website_url
                        FROM manual_check_queue q
                        JOIN websites w ON q.website_id = w.id
                        WHERE q.status IN ('pending', 'processing')
                        ORDER BY q.priority DESC, q.created_utc ASC
                    """)
                
                rows = cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                
                return [dict(zip(columns, row)) for row in rows]
                
        except Exception as e:
            self.logger.error(f"Error getting queue status: {e}")
            return []
    
    def update_queue_status(self, queue_id, status, error_message=None, result_data=None):
        """Update the status of a queued check."""
        try:
            now = datetime.now(timezone.utc).isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if status == 'processing':
                    cursor.execute("""
                        UPDATE manual_check_queue 
                        SET status = ?, started_utc = ?
                        WHERE id = ?
                    """, (status, now, queue_id))
                elif status in ['completed', 'failed']:
                    cursor.execute("""
                        UPDATE manual_check_queue 
                        SET status = ?, completed_utc = ?, error_message = ?, result_data = ?
                        WHERE id = ?
                    """, (status, now, error_message, json.dumps(result_data) if result_data else None, queue_id))
                else:
                    cursor.execute("""
                        UPDATE manual_check_queue 
                        SET status = ?
                        WHERE id = ?
                    """, (status, queue_id))
                
                conn.commit()
                self.logger.info(f"Updated queue item {queue_id} status to {status}")
                
        except Exception as e:
            self.logger.error(f"Error updating queue status: {e}")
            raise
    
    def get_next_queue_item(self):
        """Get the next item from the queue (highest priority, oldest first)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT q.*, w.name as website_name, w.url as website_url
                    FROM manual_check_queue q
                    JOIN websites w ON q.website_id = w.id
                    WHERE q.status = 'pending'
                    ORDER BY q.priority DESC, q.created_utc ASC
                    LIMIT 1
                """)
                
                row = cursor.fetchone()
                if row:
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, row))
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting next queue item: {e}")
            return None
    
    def clear_old_queue_items(self, days_old=7):
        """Clear old completed/failed queue items to keep database clean."""
        try:
            cutoff_date = datetime.now(timezone.utc).replace(day=datetime.now().day - days_old).isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM manual_check_queue 
                    WHERE status IN ('completed', 'failed') 
                    AND completed_utc < ?
                """, (cutoff_date,))
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                if deleted_count > 0:
                    self.logger.info(f"Cleared {deleted_count} old queue items")
                    
        except Exception as e:
            self.logger.error(f"Error clearing old queue items: {e}")
    
    def clear_pending_queue_items(self):
        """Clear all pending and processing items from the queue."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM manual_check_queue 
                    WHERE status IN ('pending', 'processing')
                """)
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                self.logger.info(f"Cleared {deleted_count} pending/processing queue items")
                return deleted_count
                
        except Exception as e:
            self.logger.error(f"Error clearing pending queue items: {e}")
            raise

# For backward compatibility, provide the same interface
WebsiteManager = WebsiteManagerSQLite
