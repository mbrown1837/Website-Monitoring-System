#!/usr/bin/env python3
"""
🚀 IMPROVED BULK WEBSITE IMPORT TOOL for Website Monitoring System

This script imports websites one by one with proper concurrency control.
The app will handle processing naturally through the scheduler.

Key Features:
- ✅ Imports sites one by one (reliable)
- ✅ Respects concurrency limits (1 site at a time)
- ✅ No auto-setup conflicts (let scheduler handle it)
- ✅ Better error handling (continue on failures)
- ✅ Real-time progress tracking
- ✅ Uses global exclude pages settings automatically

Usage:
1. Manual entry: python bulk_website_import_improved.py
2. CSV import: python bulk_website_import_improved.py --csv websites.csv
3. Text import: python bulk_website_import_improved.py --text websites.txt
"""

import os
import sys
import csv
import json
import time
from datetime import datetime, timezone

# Add src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from src.website_manager_sqlite import WebsiteManager
    from src.config_loader import get_config
    from src.scheduler_integration import reschedule_tasks
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running this script from the project root directory.")
    sys.exit(1)

def improved_bulk_import():
    """Import websites one by one with proper concurrency control"""
    
    print("🚀 IMPROVED BULK WEBSITE IMPORT TOOL")
    print("=" * 60)
    print("✅ Imports sites one by one (reliable)")
    print("✅ Respects concurrency limits (1 site at a time)")
    print("✅ No auto-setup conflicts (let scheduler handle it)")
    print("✅ Better error handling (continue on failures)")
    print("✅ Uses global exclude pages settings automatically")
    print("=" * 60)
    print()
    
    # Initialize managers
    config = get_config(config_path='config/config.yaml')
    website_manager = WebsiteManager(config_path='config/config.yaml')
    
    # Get websites to import
    websites_to_import = get_websites_to_import()
    
    if not websites_to_import:
        print("❌ No websites to import. Exiting.")
        return
    
    # Get configuration
    print(f"\n📊 Found {len(websites_to_import)} websites to import")
    print("\n⚙️ IMPORT CONFIGURATION")
    print("-" * 30)
    
    # Standard configuration for all sites
    default_config = {
        'check_interval_minutes': 1440,  # 24 hours
        'is_active': True,
        'capture_subpages': True,
        'render_delay': 6,  # Consistent with manual adds
        'max_crawl_depth': 2,
        'visual_diff_threshold': 5,
        'enable_blur_detection': True,  # Enable by default
        'blur_detection_scheduled': False,
        'blur_detection_manual': True,
        'auto_crawl_enabled': True,
        'auto_visual_enabled': True,
        'auto_blur_enabled': True,
        'auto_performance_enabled': True,
        'auto_full_check_enabled': True,
        'tags': [],
        'notification_emails': [],
        'exclude_pages_keywords': []  # Empty means use global settings
    }
    
    print(f"✅ Scheduling Interval: {default_config['check_interval_minutes']} minutes (24 hours)")
    print(f"✅ Full Check Enabled: {default_config['auto_full_check_enabled']}")
    print(f"✅ Active Monitoring: {default_config['is_active']}")
    print(f"✅ Crawl Depth: {default_config['max_crawl_depth']} levels")
    print(f"✅ Visual Diff Threshold: {default_config['visual_diff_threshold']}%")
    print(f"✅ Exclude Pages: Will use global settings automatically")
    print(f"✅ Concurrency: 1 site at a time (respects system limits)")
    print()
    
    # Auto-proceed without confirmation for easier web interface usage
    print("🚀 Starting import automatically...")
    
    print(f"\n🔄 Starting import of {len(websites_to_import)} websites...")
    print("=" * 60)
    
    # Import websites one by one
    imported_count = 0
    failed_count = 0
    failed_sites = []
    
    for i, website_data in enumerate(websites_to_import, 1):
        name = website_data['name']
        url = website_data['url']
        
        print(f"\n[{i:2d}/{len(websites_to_import)}] Importing: {name}")
        print(f"           URL: {url}")
        
        try:
            # Merge with default config
            full_website_data = {**default_config, **website_data}
            
            # Add the website
            result = website_manager.add_website(full_website_data)
            
            if result:
                print(f"           ✅ SUCCESS - ID: {result.get('id', 'N/A')}")
                imported_count += 1
                
                # Small delay to respect concurrency limits
                if i < len(websites_to_import):  # Don't delay after last site
                    print(f"           ⏳ Waiting 2 seconds before next import...")
                    time.sleep(2)
            else:
                print(f"           ❌ FAILED - Could not add website")
                failed_count += 1
                failed_sites.append(f"{name} ({url})")
                
        except Exception as e:
            print(f"           ❌ ERROR - {str(e)}")
            failed_count += 1
            failed_sites.append(f"{name} ({url}) - {str(e)}")
        
        # Progress indicator
        progress = (i / len(websites_to_import)) * 100
        print(f"           📊 Progress: {progress:.1f}% ({i}/{len(websites_to_import)})")
    
    # Update scheduler with new websites
    print(f"\n🔄 Updating scheduler with new websites...")
    try:
        reschedule_tasks()
        print("✅ Scheduler updated successfully")
    except Exception as e:
        print(f"⚠️ Scheduler update warning: {e}")
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 BULK IMPORT SUMMARY")
    print("=" * 60)
    print(f"✅ Successfully imported: {imported_count} websites")
    print(f"❌ Failed imports: {failed_count} websites")
    print(f"📈 Total websites in system: {len(website_manager.list_websites())}")
    
    if failed_sites:
        print(f"\n❌ FAILED IMPORTS:")
        for site in failed_sites:
            print(f"   • {site}")
    
    print(f"\n🎉 Bulk import complete!")
    print(f"⏰ All imported websites will be checked every {default_config['check_interval_minutes']} minutes")
    print(f"🚀 Full checks (crawl + visual + blur + performance) are enabled for all sites")
    print(f"📸 Baselines will be created automatically by the scheduler")
    print(f"🚫 Exclude pages (products, blogs, etc.) will be skipped automatically")
    print(f"⚡ Processing will respect concurrency limits (1 site at a time)")

def get_websites_to_import():
    """Get websites to import based on command line arguments or user input"""
    
    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == '--csv' and len(sys.argv) > 2:
            return import_from_csv(sys.argv[2])
        elif sys.argv[1] == '--text' and len(sys.argv) > 2:
            return import_from_text_file(sys.argv[2])
        elif sys.argv[1] == '--create-samples':
            create_sample_files()
            return []
    
    # Interactive mode
    print("Choose import method:")
    print("1. Manual entry (type URLs one by one)")
    print("2. Import from CSV file") 
    print("3. Import from text file (one URL per line)")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == "1":
        return get_manual_input()
    elif choice == "2":
        filename = input("Enter CSV filename (default: websites.csv): ").strip() or 'websites.csv'
        return import_from_csv(filename)
    elif choice == "3":
        filename = input("Enter text filename (default: websites.txt): ").strip() or 'websites.txt'
        return import_from_text_file(filename)
    else:
        print("❌ Invalid choice. Exiting.")
        return []

def get_manual_input():
    """Get websites through manual input"""
    websites = []
    print("\n📝 MANUAL ENTRY MODE")
    print("Enter websites one by one. Press Enter with empty input to finish.")
    print()
    
    while True:
        name = input("Website Name (or press Enter to finish): ").strip()
        if not name:
            break
            
        url = input("Website URL: ").strip()
        if not url:
            print("❌ URL is required. Skipping this entry.")
            continue
        
        # Add https:// if no protocol specified
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        websites.append({'name': name, 'url': url})
        print(f"✅ Added: {name} -> {url}\n")
    
    return websites

def import_from_csv(filename):
    """Import websites from CSV file"""
    print(f"\n📁 CSV IMPORT MODE: {filename}")
    print("CSV format: name,url,monitoring_interval,enable_crawl,enable_visual,enable_blur_detection,enable_performance,max_depth,exclude_pages_keywords,description")
    print("Example: My Website,https://example.com,1440,true,true,true,true,2,products,blogs,My description")
    
    if not os.path.exists(filename):
        print(f"❌ File '{filename}' not found.")
        return []
    
    websites = []
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                name = row.get('name', '').strip()
                url = row.get('url', '').strip()
                
                if name and url:
                    if not url.startswith(('http://', 'https://')):
                        url = 'https://' + url
                    
                    # Parse additional CSV fields
                    exclude_pages_keywords_str = row.get('exclude_pages_keywords', '').strip()
                    exclude_pages_keywords = [keyword.strip() for keyword in exclude_pages_keywords_str.split(',') if keyword.strip()] if exclude_pages_keywords_str else []
                    
                    website_data = {
                        'name': name,
                        'url': url,
                        'check_interval_minutes': int(row.get('monitoring_interval', 1440)),
                        'max_crawl_depth': int(row.get('max_depth', 2)),
                        'auto_crawl_enabled': (row.get('enable_crawl', 'true').lower() == 'true'),
                        'auto_visual_enabled': (row.get('enable_visual', 'true').lower() == 'true'),
                        'auto_blur_enabled': (row.get('enable_blur_detection', 'true').lower() == 'true'),
                        'enable_blur_detection': (row.get('enable_blur_detection', 'true').lower() == 'true'),
                        'auto_performance_enabled': (row.get('enable_performance', 'true').lower() == 'true'),
                        'exclude_pages_keywords': exclude_pages_keywords,
                        'description': row.get('description', '').strip()
                    }
                    
                    websites.append(website_data)
        
        print(f"✅ Loaded {len(websites)} websites from CSV")
        
    except Exception as e:
        print(f"❌ Error reading CSV file: {e}")
        return []
    
    return websites

def import_from_text_file(filename):
    """Import websites from text file (one URL per line)"""
    print(f"\n📁 TEXT IMPORT MODE: {filename}")
    print("Format: One URL per line")
    print("Example: https://example.com")
    
    if not os.path.exists(filename):
        print(f"❌ File '{filename}' not found.")
        return []
    
    websites = []
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            for line_num, line in enumerate(file, 1):
                url = line.strip()
                if url and not url.startswith('#'):  # Skip empty lines and comments
                    if not url.startswith(('http://', 'https://')):
                        url = 'https://' + url
                    
                    # Generate name from URL
                    name = url.replace('https://', '').replace('http://', '').split('/')[0]
                    websites.append({'name': name, 'url': url})
        
        print(f"✅ Loaded {len(websites)} websites from text file")
        
    except Exception as e:
        print(f"❌ Error reading text file: {e}")
        return []
    
    return websites

def create_sample_files():
    """Create sample CSV and text files for import"""
    print("📝 Creating sample files...")
    
    # Sample CSV file
    csv_content = """name,url,monitoring_interval,enable_crawl,enable_visual,enable_blur_detection,enable_performance,max_depth,description
Example Site 1,https://example1.com,1440,true,true,true,true,2,Example website 1
Example Site 2,https://example2.com,1440,true,true,true,true,2,Example website 2
Example Site 3,https://example3.com,1440,true,true,true,true,2,Example website 3"""
    
    with open('websites_sample.csv', 'w', encoding='utf-8') as f:
        f.write(csv_content)
    
    # Sample text file
    text_content = """https://example1.com
https://example2.com
https://example3.com"""
    
    with open('websites_sample.txt', 'w', encoding='utf-8') as f:
        f.write(text_content)
    
    print("✅ Created websites_sample.csv")
    print("✅ Created websites_sample.txt")
    print("\nUsage:")
    print("   python bulk_website_import_improved.py --csv websites_sample.csv")
    print("   python bulk_website_import_improved.py --text websites_sample.txt")

if __name__ == '__main__':
    try:
        improved_bulk_import()
    except KeyboardInterrupt:
        print("\n\n❌ Import cancelled by user.")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        print("Please check your configuration and try again.")
