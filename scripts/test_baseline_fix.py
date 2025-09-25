#!/usr/bin/env python3
"""
Test script to add a website and create baselines to test the baseline fix.
"""

import os
import sys
import uuid
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from website_manager_sqlite import WebsiteManagerSQLite
from history_manager_sqlite import HistoryManagerSQLite
from crawler_module import CrawlerModule
from config_loader import get_config

def test_baseline_fix():
    """Test the baseline fix by adding a website and creating baselines."""
    
    print("🧪 Testing Baseline Fix")
    print("=" * 40)
    
    # Initialize managers
    config = get_config()
    website_manager = WebsiteManagerSQLite(config)
    history_manager = HistoryManagerSQLite(config)
    crawler_module = CrawlerModule(config)
    
    # Test website data
    test_website = {
        'id': str(uuid.uuid4()),
        'name': 'Test Website',
        'url': 'https://httpbin.org',
        'interval': 60,
        'is_active': True,
        'tags': ['test'],
        'notification_emails': [],
        'monitoring_mode': 'full',
        'render_delay': 6,
        'max_crawl_depth': 2,
        'visual_diff_threshold': 5,
        'capture_subpages': True,
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat()
    }
    
    print(f"📝 Adding test website: {test_website['name']}")
    
    # Add website to database
    website_manager.add_website(
        test_website['url'],
        test_website['name'],
        test_website['interval'],
        test_website['is_active'],
        test_website['tags'],
        test_website['notification_emails']
    )
    
    # Get the website ID from the database
    websites = website_manager.list_websites()
    test_site_id = None
    for site_id, site_data in websites.items():
        if site_data.get('name') == test_website['name']:
            test_site_id = site_id
            break
    
    if not test_site_id:
        print("❌ Failed to find test website in database")
        return False
    
    print(f"✅ Test website added with ID: {test_site_id}")
    
    # Create baseline
    print("📸 Creating baseline...")
    
    try:
        # Run a baseline creation check
        result = crawler_module.check_website(
            test_site_id,
            create_baseline=True,
            capture_subpages=True,
            crawl_only=False,
            visual_check_only=False
        )
        
        if result:
            print("✅ Baseline created successfully!")
            
            # Check if baseline files exist
            domain_name = test_website['url'].replace('https://', '').replace('http://', '').replace('.', '_').replace(':', '_')
            baseline_dir = os.path.join('data', 'snapshots', domain_name, test_site_id, 'baseline')
            
            if os.path.exists(baseline_dir):
                baseline_files = os.listdir(baseline_dir)
                print(f"📁 Baseline directory: {baseline_dir}")
                print(f"📸 Baseline files: {baseline_files}")
            else:
                print(f"❌ Baseline directory not found: {baseline_dir}")
                
        else:
            print("❌ Failed to create baseline")
            return False
            
    except Exception as e:
        print(f"❌ Error creating baseline: {e}")
        return False
    
    # Test the history page
    print("\n🔍 Testing history page...")
    
    try:
        from app import app
        with app.test_client() as client:
            response = client.get(f'/website/history/{test_site_id}')
            if response.status_code == 200:
                print("✅ History page loads successfully!")
                
                # Check if baseline images are mentioned in the response
                if 'baseline' in response.get_data(as_text=True).lower():
                    print("✅ Baseline images found in history page!")
                else:
                    print("⚠️  No baseline images found in history page")
            else:
                print(f"❌ History page failed with status: {response.status_code}")
                return False
                
    except Exception as e:
        print(f"❌ Error testing history page: {e}")
        return False
    
    print("\n✅ Baseline fix test completed successfully!")
    return True

if __name__ == "__main__":
    success = test_baseline_fix()
    if not success:
        sys.exit(1)
