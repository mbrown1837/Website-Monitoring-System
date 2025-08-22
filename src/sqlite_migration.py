"""
SQLite Migration Module

This module handles the migration of data from JSON files to SQLite database
for better data consistency and performance.
"""

import sqlite3
import json
import os
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class SQLiteMigrationManager:
    """Manages migration from JSON files to SQLite database."""
    
    def __init__(self, db_path: str = "data/website_monitor.db"):
        self.db_path = db_path
        self.websites_file = "data/websites.json"
        self.check_history_file = "data/check_history.json"
        
    def create_websites_table(self) -> bool:
        """Create the websites table in SQLite."""
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
                        baseline_visual_path_web TEXT
                    )
                """)
                
                # Create indexes for better performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_websites_url ON websites(url)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_websites_active ON websites(is_active)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_websites_created ON websites(created_utc)")
                
                conn.commit()
                logger.info("Websites table created successfully")
                return True
                
        except Exception as e:
            logger.error(f"Error creating websites table: {e}")
            return False
    
    def create_check_history_table(self) -> bool:
        """Create the check history table in SQLite."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create check_history table
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
                logger.info("Check history table created successfully")
                return True
                
        except Exception as e:
            logger.error(f"Error creating check history table: {e}")
            return False
    
    def migrate_websites_to_sqlite(self) -> bool:
        """Migrate websites data from JSON to SQLite."""
        try:
            if not os.path.exists(self.websites_file):
                logger.warning(f"Websites file not found: {self.websites_file}")
                return False
            
            with open(self.websites_file, 'r', encoding='utf-8') as f:
                websites_data = json.load(f)
            
            if not websites_data:
                logger.info("No websites data to migrate")
                return True
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Clear existing data
                cursor.execute("DELETE FROM websites")
                
                # Insert websites data
                for website in websites_data:
                    cursor.execute("""
                        INSERT INTO websites (
                            id, url, name, check_interval_minutes, is_active, tags, notification_emails,
                            created_utc, last_updated_utc, render_delay, max_crawl_depth,
                            visual_diff_threshold, capture_subpages, all_baselines,
                            has_subpage_baselines, baseline_visual_path, enable_blur_detection,
                            blur_detection_scheduled, blur_detection_manual, auto_crawl_enabled,
                            auto_visual_enabled, auto_blur_enabled, auto_performance_enabled,
                            auto_full_check_enabled, baseline_visual_path_web
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        website.get('id'),
                        website.get('url'),
                        website.get('name'),
                        website.get('interval', 24) * 60,  # Convert hours to minutes
                        website.get('is_active', True),
                        json.dumps(website.get('tags', [])),
                        json.dumps(website.get('notification_emails', [])),
                        website.get('created_utc'),
                        website.get('last_updated_utc'),
                        website.get('render_delay', 6),
                        website.get('max_crawl_depth', 2),
                        website.get('visual_diff_threshold', 5),
                        website.get('capture_subpages', True),
                        json.dumps(website.get('all_baselines', {})),
                        website.get('has_subpage_baselines', False),
                        website.get('baseline_visual_path'),
                        website.get('enable_blur_detection', False),
                        website.get('blur_detection_scheduled', False),
                        website.get('blur_detection_manual', True),
                        website.get('auto_crawl_enabled', True),
                        website.get('auto_visual_enabled', True),
                        website.get('auto_blur_enabled', True),
                        website.get('auto_performance_enabled', True),
                        website.get('auto_full_check_enabled', True),
                        website.get('baseline_visual_path_web')
                    ))
                
                conn.commit()
                logger.info(f"Successfully migrated {len(websites_data)} websites to SQLite")
                return True
                
        except Exception as e:
            logger.error(f"Error migrating websites to SQLite: {e}")
            return False
    
    def migrate_check_history_to_sqlite(self) -> bool:
        """Migrate check history data from JSON to SQLite."""
        try:
            if not os.path.exists(self.check_history_file):
                logger.warning(f"Check history file not found: {self.check_history_file}")
                return False
            
            with open(self.check_history_file, 'r', encoding='utf-8') as f:
                check_history_data = json.load(f)
            
            if not check_history_data:
                logger.info("No check history data to migrate")
                return True
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Clear existing data
                cursor.execute("DELETE FROM check_history")
                
                # Insert check history data
                for check_record in check_history_data:
                    cursor.execute("""
                        INSERT INTO check_history (
                            check_id, site_id, timestamp_utc, timestamp_readable, status,
                            html_snapshot_path, html_content_hash, visual_snapshot_path, url,
                            significant_change_detected, website_id, timestamp, broken_links,
                            missing_meta_tags, all_pages, visual_diff_score, visual_diff_image_path,
                            performance_metrics, blur_detection_results
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        check_record.get('check_id'),
                        check_record.get('site_id'),
                        check_record.get('timestamp_utc'),
                        check_record.get('timestamp_readable'),
                        check_record.get('status'),
                        check_record.get('html_snapshot_path'),
                        check_record.get('html_content_hash'),
                        check_record.get('visual_snapshot_path'),
                        check_record.get('url'),
                        check_record.get('significant_change_detected', False),
                        check_record.get('website_id'),
                        check_record.get('timestamp'),
                        json.dumps(check_record.get('broken_links', [])),
                        json.dumps(check_record.get('missing_meta_tags', [])),
                        json.dumps(check_record.get('all_pages', [])),
                        check_record.get('visual_diff_score'),
                        check_record.get('visual_diff_image_path'),
                        json.dumps(check_record.get('performance_metrics', {})),
                        json.dumps(check_record.get('blur_detection_results', {}))
                    ))
                
                conn.commit()
                logger.info(f"Successfully migrated {len(check_history_data)} check history records to SQLite")
                return True
                
        except Exception as e:
            logger.error(f"Error migrating check history to SQLite: {e}")
            return False
    
    def run_full_migration(self) -> Dict[str, bool]:
        """Run the complete migration process."""
        logger.info("Starting SQLite migration process...")
        
        results = {
            'websites_table_created': False,
            'check_history_table_created': False,
            'websites_migrated': False,
            'check_history_migrated': False
        }
        
        try:
            # Create tables
            results['websites_table_created'] = self.create_websites_table()
            results['check_history_table_created'] = self.create_check_history_table()
            
            if not (results['websites_table_created'] and results['check_history_table_created']):
                logger.error("Failed to create required tables")
                return results
            
            # Migrate data
            results['websites_migrated'] = self.migrate_websites_to_sqlite()
            results['check_history_migrated'] = self.migrate_check_history_to_sqlite()
            
            if results['websites_migrated'] and results['check_history_migrated']:
                logger.info("SQLite migration completed successfully!")
            else:
                logger.error("SQLite migration failed for some components")
            
            return results
            
        except Exception as e:
            logger.error(f"Error during migration: {e}")
            return results
    
    def verify_migration(self) -> Dict[str, Any]:
        """Verify that the migration was successful."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check websites count
                cursor.execute("SELECT COUNT(*) FROM websites")
                websites_count = cursor.fetchone()[0]
                
                # Check check_history count
                cursor.execute("SELECT COUNT(*) FROM check_history")
                check_history_count = cursor.fetchone()[0]
                
                # Check JSON file sizes
                websites_json_size = os.path.getsize(self.websites_file) if os.path.exists(self.websites_file) else 0
                check_history_json_size = os.path.getsize(self.check_history_file) if os.path.exists(self.check_history_file) else 0
                
                return {
                    'websites_in_sqlite': websites_count,
                    'check_history_in_sqlite': check_history_count,
                    'websites_json_size': websites_json_size,
                    'check_history_json_size': check_history_json_size,
                    'migration_successful': websites_count > 0 and check_history_count > 0
                }
                
        except Exception as e:
            logger.error(f"Error verifying migration: {e}")
            return {'migration_successful': False, 'error': str(e)}

def run_migration():
    """Main function to run the migration."""
    migration_manager = SQLiteMigrationManager()
    
    print("Starting SQLite migration...")
    results = migration_manager.run_full_migration()
    
    print("\nMigration Results:")
    for key, value in results.items():
        status = "✅ SUCCESS" if value else "❌ FAILED"
        print(f"  {key}: {status}")
    
    print("\nVerifying migration...")
    verification = migration_manager.verify_migration()
    
    print("\nVerification Results:")
    for key, value in verification.items():
        print(f"  {key}: {value}")
    
    if verification.get('migration_successful'):
        print("\n🎉 Migration completed successfully!")
        print("You can now safely remove the JSON files.")
    else:
        print("\n⚠️  Migration had issues. Please check the logs.")

if __name__ == "__main__":
    run_migration()
