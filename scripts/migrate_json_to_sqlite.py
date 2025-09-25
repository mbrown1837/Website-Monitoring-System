#!/usr/bin/env python3
"""
Migration script to sync JSON website data to SQLite database.
This ensures the scheduler can find websites that were added via the web interface.
"""

import os
import sys
import json
import sqlite3
from datetime import datetime, timezone

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import with proper path handling
try:
    from config_loader import get_config
    from logger_setup import setup_logging
    from website_manager_sqlite import WebsiteManagerSQLite
except ImportError:
    # Fallback for different Python path setups
    import importlib.util
    import os
    
    # Get the project root directory
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_path = os.path.join(project_root, 'src')
    
    # Add src to Python path
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    
    from config_loader import get_config
    from logger_setup import setup_logging
    from website_manager_sqlite import WebsiteManagerSQLite

def migrate_json_to_sqlite():
    """Migrate websites from JSON file to SQLite database."""
    logger = setup_logging()
    config = get_config()
    
    # Get paths
    json_path = config.get('website_list_file_path', 'data/websites.json')
    db_path = config.get('database_path', 'data/website_monitor.db')
    
    logger.info(f"Starting migration from {json_path} to {db_path}")
    
    # Check if JSON file exists
    if not os.path.exists(json_path):
        logger.error(f"JSON file not found: {json_path}")
        return False
    
    # Load websites from JSON
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            websites = json.load(f)
        logger.info(f"Loaded {len(websites)} websites from JSON file")
    except Exception as e:
        logger.error(f"Error loading JSON file: {e}")
        return False
    
    # Initialize SQLite manager
    try:
        website_manager = WebsiteManagerSQLite()
        logger.info("Initialized SQLite website manager")
    except Exception as e:
        logger.error(f"Error initializing SQLite manager: {e}")
        return False
    
    # Migrate each website
    migrated_count = 0
    for website in websites:
        try:
            # Check if website already exists in database
            existing = website_manager.get_website(website.get('id'))
            if existing:
                logger.info(f"Website {website.get('name')} already exists in database, skipping")
                continue
            
            # Add website to database
            website_manager.add_website(website)
            migrated_count += 1
            logger.info(f"Migrated website: {website.get('name')} ({website.get('id')})")
            
        except Exception as e:
            logger.error(f"Error migrating website {website.get('name')}: {e}")
            continue
    
    logger.info(f"Migration completed: {migrated_count} websites migrated")
    return True

def verify_migration():
    """Verify that websites are properly loaded in the database."""
    logger = setup_logging()
    
    try:
        website_manager = WebsiteManagerSQLite()
        websites = website_manager.list_websites()
        
        logger.info(f"Database contains {len(websites)} websites:")
        for site_id, website in websites.items():
            logger.info(f"  - {website.get('name')} ({website.get('url')}) - Active: {website.get('is_active')}")
        
        return len(websites) > 0
        
    except Exception as e:
        logger.error(f"Error verifying migration: {e}")
        return False

if __name__ == '__main__':
    print("🔄 Starting JSON to SQLite migration...")
    
    # Run migration
    success = migrate_json_to_sqlite()
    
    if success:
        print("✅ Migration completed successfully")
        
        # Verify migration
        print("🔍 Verifying migration...")
        if verify_migration():
            print("✅ Verification successful - websites are now in database")
        else:
            print("❌ Verification failed - no websites found in database")
    else:
        print("❌ Migration failed")
        sys.exit(1)
