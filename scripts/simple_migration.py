#!/usr/bin/env python3
"""
Simple migration script to sync JSON website data to SQLite database.
This script directly handles the database operations without complex imports.
"""

import os
import sys
import json
import sqlite3
from datetime import datetime, timezone

def get_database_path():
    """Get the database path."""
    # Try different possible locations
    possible_paths = [
        'data/website_monitor.db',
        'src/../data/website_monitor.db',
        os.path.join(os.path.dirname(__file__), '..', 'data', 'website_monitor.db')
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    # If not found, create in data directory
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, 'website_monitor.db')

def get_json_path():
    """Get the JSON file path."""
    possible_paths = [
        'data/websites.json',
        'src/../data/websites.json',
        os.path.join(os.path.dirname(__file__), '..', 'data', 'websites.json')
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    return None

def create_database_tables(db_path):
    """Create necessary database tables."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create websites table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS websites (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            monitoring_interval_hours INTEGER DEFAULT 24,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_checked TIMESTAMP,
            check_count INTEGER DEFAULT 0,
            last_status TEXT,
            last_response_time REAL,
            last_error TEXT,
            notification_email TEXT,
            custom_headers TEXT,
            excluded_pages TEXT,
            monitoring_enabled BOOLEAN DEFAULT 1,
            visual_monitoring_enabled BOOLEAN DEFAULT 1,
            content_monitoring_enabled BOOLEAN DEFAULT 1,
            performance_monitoring_enabled BOOLEAN DEFAULT 1,
            meta_tags_monitoring_enabled BOOLEAN DEFAULT 1,
            broken_links_monitoring_enabled BOOLEAN DEFAULT 1,
            blur_detection_enabled BOOLEAN DEFAULT 1,
            crawler_enabled BOOLEAN DEFAULT 1,
            greenflare_enabled BOOLEAN DEFAULT 1,
            pagespeed_enabled BOOLEAN DEFAULT 1,
            custom_js TEXT,
            custom_css TEXT,
            notes TEXT
        )
    ''')
    
    # Create check_history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS check_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            website_id TEXT NOT NULL,
            check_type TEXT NOT NULL,
            status TEXT NOT NULL,
            response_time REAL,
            error_message TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            details TEXT,
            FOREIGN KEY (website_id) REFERENCES websites (id)
        )
    ''')
    
    # Create manual_check_queue table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS manual_check_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            website_id TEXT NOT NULL,
            check_type TEXT NOT NULL,
            priority INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (website_id) REFERENCES websites (id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print(f"✅ Database tables created/verified at: {db_path}")

def migrate_websites(json_path, db_path):
    """Migrate websites from JSON to SQLite."""
    print(f"📖 Loading websites from: {json_path}")
    
    # Load websites from JSON
    with open(json_path, 'r', encoding='utf-8') as f:
        websites = json.load(f)
    
    print(f"📊 Found {len(websites)} websites in JSON file")
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    migrated_count = 0
    skipped_count = 0
    
    for website in websites:
        try:
            # Check if website already exists
            cursor.execute("SELECT id FROM websites WHERE id = ?", (website.get('id'),))
            if cursor.fetchone():
                print(f"⏭️  Website {website.get('name')} already exists, skipping")
                skipped_count += 1
                continue
            
            # Prepare website data for insertion
            website_data = {
                'id': website.get('id'),
                'name': website.get('name'),
                'url': website.get('url'),
                'is_active': website.get('is_active', True),
                'monitoring_interval_hours': website.get('monitoring_interval_hours', 24),
                'created_at': website.get('created_at', datetime.now(timezone.utc).isoformat()),
                'updated_at': website.get('updated_at', datetime.now(timezone.utc).isoformat()),
                'last_checked': website.get('last_checked'),
                'check_count': website.get('check_count', 0),
                'last_status': website.get('last_status'),
                'last_response_time': website.get('last_response_time'),
                'last_error': website.get('last_error'),
                'notification_email': website.get('notification_email'),
                'custom_headers': json.dumps(website.get('custom_headers', {})) if website.get('custom_headers') else None,
                'excluded_pages': json.dumps(website.get('excluded_pages', [])) if website.get('excluded_pages') else None,
                'monitoring_enabled': website.get('monitoring_enabled', True),
                'visual_monitoring_enabled': website.get('visual_monitoring_enabled', True),
                'content_monitoring_enabled': website.get('content_monitoring_enabled', True),
                'performance_monitoring_enabled': website.get('performance_monitoring_enabled', True),
                'meta_tags_monitoring_enabled': website.get('meta_tags_monitoring_enabled', True),
                'broken_links_monitoring_enabled': website.get('broken_links_monitoring_enabled', True),
                'blur_detection_enabled': website.get('blur_detection_enabled', True),
                'crawler_enabled': website.get('crawler_enabled', True),
                'greenflare_enabled': website.get('greenflare_enabled', True),
                'pagespeed_enabled': website.get('pagespeed_enabled', True),
                'custom_js': website.get('custom_js'),
                'custom_css': website.get('custom_css'),
                'notes': website.get('notes')
            }
            
            # Insert website
            cursor.execute('''
                INSERT INTO websites (
                    id, name, url, is_active, monitoring_interval_hours, created_at, updated_at,
                    last_checked, check_count, last_status, last_response_time, last_error,
                    notification_email, custom_headers, excluded_pages, monitoring_enabled,
                    visual_monitoring_enabled, content_monitoring_enabled, performance_monitoring_enabled,
                    meta_tags_monitoring_enabled, broken_links_monitoring_enabled, blur_detection_enabled,
                    crawler_enabled, greenflare_enabled, pagespeed_enabled, custom_js, custom_css, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                website_data['id'], website_data['name'], website_data['url'], website_data['is_active'],
                website_data['monitoring_interval_hours'], website_data['created_at'], website_data['updated_at'],
                website_data['last_checked'], website_data['check_count'], website_data['last_status'],
                website_data['last_response_time'], website_data['last_error'], website_data['notification_email'],
                website_data['custom_headers'], website_data['excluded_pages'], website_data['monitoring_enabled'],
                website_data['visual_monitoring_enabled'], website_data['content_monitoring_enabled'],
                website_data['performance_monitoring_enabled'], website_data['meta_tags_monitoring_enabled'],
                website_data['broken_links_monitoring_enabled'], website_data['blur_detection_enabled'],
                website_data['crawler_enabled'], website_data['greenflare_enabled'], website_data['pagespeed_enabled'],
                website_data['custom_js'], website_data['custom_css'], website_data['notes']
            ))
            
            migrated_count += 1
            print(f"✅ Migrated: {website.get('name')} ({website.get('url')})")
            
        except Exception as e:
            print(f"❌ Error migrating {website.get('name')}: {e}")
            continue
    
    conn.commit()
    conn.close()
    
    print(f"\n📊 Migration Summary:")
    print(f"   ✅ Migrated: {migrated_count} websites")
    print(f"   ⏭️  Skipped: {skipped_count} websites")
    print(f"   📁 Database: {db_path}")
    
    return migrated_count > 0

def verify_migration(db_path):
    """Verify that websites are properly loaded in the database."""
    print(f"\n🔍 Verifying migration...")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Count total websites
        cursor.execute("SELECT COUNT(*) FROM websites")
        total_count = cursor.fetchone()[0]
        
        # Count active websites
        cursor.execute("SELECT COUNT(*) FROM websites WHERE is_active = 1")
        active_count = cursor.fetchone()[0]
        
        print(f"📊 Database contains {total_count} total websites ({active_count} active)")
        
        # List websites
        cursor.execute("SELECT id, name, url, is_active FROM websites ORDER BY name")
        websites = cursor.fetchall()
        
        for website in websites:
            status = "🟢 Active" if website[3] else "🔴 Inactive"
            print(f"   {status} {website[1]} ({website[2]})")
        
        conn.close()
        return total_count > 0
        
    except Exception as e:
        print(f"❌ Error verifying migration: {e}")
        return False

def main():
    """Main migration function."""
    print("🔄 Starting JSON to SQLite migration...")
    
    # Get file paths
    json_path = get_json_path()
    if not json_path:
        print("❌ JSON file not found. Please check the data/websites.json file exists.")
        return False
    
    db_path = get_database_path()
    print(f"📁 JSON file: {json_path}")
    print(f"📁 Database: {db_path}")
    
    # Create database tables
    create_database_tables(db_path)
    
    # Migrate websites
    success = migrate_websites(json_path, db_path)
    
    if success:
        print("✅ Migration completed successfully")
        
        # Verify migration
        if verify_migration(db_path):
            print("✅ Verification successful - websites are now in database")
            print("\n🎉 The scheduler should now be able to find and monitor your websites!")
        else:
            print("❌ Verification failed - no websites found in database")
            return False
    else:
        print("❌ Migration failed")
        return False
    
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
