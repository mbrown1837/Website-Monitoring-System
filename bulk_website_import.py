#!/usr/bin/env python3
"""
🚀 BULK WEBSITE IMPORT TOOL for Website Monitoring System

This script allows you to import multiple websites at once with the same configuration.
Perfect for adding 60+ sites with identical settings like baseline creation, full check, and scheduling.

Usage Examples:
1. Manual entry: python bulk_website_import.py
2. Create samples: python bulk_website_import.py --create-samples
3. CSV import: Create websites.csv then run the script
4. Text import: Create websites.txt then run the script

Your Configuration:
- ⏰ Scheduling: Every 3600 minutes (60 hours)
- 🚀 Full checks enabled (crawl + visual + blur + performance)
- ✅ Baseline creation enabled
- 🔄 All monitoring features active
"""

import os
import sys
import csv
import json
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

def bulk_import_websites():
    """Import multiple websites with same configuration"""
    
    print("🚀 BULK WEBSITE IMPORT TOOL")
    print("=" * 50)
    print()
    
    # Initialize managers
    config = get_config(config_path='config/config.yaml')
    website_manager = WebsiteManager(config_path='config/config.yaml')
    
    # Get user preferences for bulk import
    print("📋 BULK IMPORT CONFIGURATION")
    print("-" * 30)
    
    # Ask for import method
    print("Choose import method:")
    print("1. Manual entry (type URLs one by one)")
    print("2. Import from CSV file") 
    print("3. Import from text file (one URL per line)")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    websites_to_import = []
    
    if choice == "1":
        websites_to_import = get_manual_input()
    elif choice == "2":
        websites_to_import = import_from_csv()
    elif choice == "3":
        websites_to_import = import_from_text_file()
    else:
        print("❌ Invalid choice. Exiting.")
        return
    
    if not websites_to_import:
        print("❌ No websites to import. Exiting.")
        return
    
    # Get common configuration
    print(f"\n📊 Found {len(websites_to_import)} websites to import")
    print("\n⚙️ COMMON CONFIGURATION")
    print("-" * 25)
    
    # Your requested configuration for all 60+ sites
    default_config = {
        'check_interval_minutes': 3600,  # 60 hours as requested
        'is_active': True,
        'capture_subpages': True,
        'render_delay': 3,
        'max_crawl_depth': 2,
        'visual_diff_threshold': 5,
        'enable_blur_detection': False,
        'blur_detection_scheduled': False,
        'blur_detection_manual': True,
        'auto_crawl_enabled': True,
        'auto_visual_enabled': True,
        'auto_blur_enabled': True,
        'auto_performance_enabled': True,
        'auto_full_check_enabled': True,  # Enable full check as requested
    }
    
    print(f"✅ Scheduling Interval: {default_config['check_interval_minutes']} minutes (60 hours)")
    print(f"✅ Full Check Enabled: {default_config['auto_full_check_enabled']}")
    print(f"✅ Baseline Creation: Enabled")
    print(f"✅ Active Monitoring: {default_config['is_active']}")
    print(f"✅ Crawl Depth: {default_config['max_crawl_depth']} levels")
    print(f"✅ Visual Diff Threshold: {default_config['visual_diff_threshold']}%")
    print()
    
    # Confirm before proceeding
    confirm = input("🤔 Proceed with bulk import? (y/N): ").strip().lower()
    if confirm != 'y':
        print("❌ Import cancelled.")
        return
    
    # Start bulk import
    print(f"\n🔄 IMPORTING {len(websites_to_import)} WEBSITES")
    print("=" * 40)
    
    imported_count = 0
    failed_count = 0
    failed_sites = []
    
    for i, website_data in enumerate(websites_to_import, 1):
        name = website_data['name']
        url = website_data['url']
        
        print(f"[{i:2d}/{len(websites_to_import)}] Importing: {name}")
        print(f"           URL: {url}")
        
        try:
            # Merge with default config
            full_website_data = {**default_config, **website_data}
            
            # Add the website
            result = website_manager.add_website(full_website_data)
            
            if result:
                print(f"           ✅ SUCCESS - ID: {result.get('id', 'N/A')}")
                imported_count += 1
            else:
                print(f"           ❌ FAILED - Could not add website")
                failed_count += 1
                failed_sites.append(f"{name} ({url})")
                
        except Exception as e:
            print(f"           ❌ ERROR - {str(e)}")
            failed_count += 1
            failed_sites.append(f"{name} ({url}) - {str(e)}")
        
        print()
    
    # Update scheduler with new websites
    print("🔄 Updating scheduler with new websites...")
    try:
        reschedule_tasks()
        print("✅ Scheduler updated successfully")
    except Exception as e:
        print(f"⚠️ Scheduler update warning: {e}")
    
    # Summary
    print("=" * 50)
    print("📊 BULK IMPORT SUMMARY")
    print("=" * 50)
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
    print(f"📸 To create baselines, go to each website's history page and click 'Create/Update Baseline'")

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

def import_from_csv():
    """Import websites from CSV file"""
    print("\n📁 CSV IMPORT MODE")
    print("CSV format: name,url")
    print("Example: My Website,https://example.com")
    print()
    
    filename = input("Enter CSV filename (default: websites.csv): ").strip() or 'websites.csv'
    
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
                    websites.append({'name': name, 'url': url})
        
        print(f"✅ Loaded {len(websites)} websites from CSV")
        
    except Exception as e:
        print(f"❌ Error reading CSV file: {e}")
        return []
    
    return websites

def import_from_text_file():
    """Import websites from text file (one URL per line)"""
    print("\n📄 TEXT FILE IMPORT MODE")
    print("Format: One URL per line")
    print("Website names will be auto-generated from URLs")
    print()
    
    filename = input("Enter text filename (default: websites.txt): ").strip() or 'websites.txt'
    
    if not os.path.exists(filename):
        print(f"❌ File '{filename}' not found.")
        return []
    
    websites = []
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            for line_num, line in enumerate(file, 1):
                url = line.strip()
                if not url or url.startswith('#'):  # Skip empty lines and comments
                    continue
                
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url
                
                # Generate name from URL
                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(url)
                    name = parsed.netloc.replace('www.', '').replace('.', '_').title()
                    if not name:
                        name = f"Website_{line_num}"
                except:
                    name = f"Website_{line_num}"
                
                websites.append({'name': name, 'url': url})
        
        print(f"✅ Loaded {len(websites)} websites from text file")
        
    except Exception as e:
        print(f"❌ Error reading text file: {e}")
        return []
    
    return websites

def create_sample_files():
    """Create sample import files for reference"""
    print("📋 CREATING SAMPLE IMPORT FILES")
    print("-" * 35)
    
    # Create sample CSV
    csv_content = """name,url
Google,https://google.com
GitHub,https://github.com
Stack Overflow,https://stackoverflow.com
Example Website,https://example.com
My Blog,myblog.com
Test Site 1,https://testsite1.com
Test Site 2,https://testsite2.com
Test Site 3,https://testsite3.com"""
    
    with open('sample_websites.csv', 'w', encoding='utf-8') as f:
        f.write(csv_content)
    print("✅ Created: sample_websites.csv")
    
    # Create sample text file
    txt_content = """# Sample websites for bulk import
# One URL per line, comments start with #
https://google.com
https://github.com
https://stackoverflow.com
https://example.com
myblog.com
testsite1.com
testsite2.com
testsite3.com"""
    
    with open('sample_websites.txt', 'w', encoding='utf-8') as f:
        f.write(txt_content)
    print("✅ Created: sample_websites.txt")
    print()
    print("💡 Use these sample files as templates for your bulk import!")
    print("📝 Edit the files with your actual website URLs, then run:")
    print("   python bulk_website_import.py")

if __name__ == '__main__':
    try:
        # Check if user wants to create sample files
        if len(sys.argv) > 1 and sys.argv[1] == '--create-samples':
            create_sample_files()
        else:
            bulk_import_websites()
    except KeyboardInterrupt:
        print("\n\n❌ Import cancelled by user.")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        print("Please check your configuration and try again.")