#!/usr/bin/env python3
"""
Test Greenflare configuration to see what's actually being extracted
"""

import os
import sys

# Add src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.greenflare_crawler import GreenflareWrapper, GREENFLARE_AVAILABLE
from src.config_loader import get_config

def test_greenflare_extraction():
    """Test what Greenflare is actually extracting."""
    print("=" * 60)
    print("GREENFLARE META TAG EXTRACTION TEST")
    print("=" * 60)
    print()
    
    print(f"🔍 Greenflare available: {GREENFLARE_AVAILABLE}")
    
    config = get_config()
    
    # Create Greenflare wrapper
    bot = GreenflareWrapper(
        user_agent='Website Monitoring System Crawler/1.0',
        retries=3,
        backoff_base=0.3,
        timeout=30,
        max_depth=2,
        respect_robots=True,
        check_external_links=True
    )
    
    # Configure for meta tag extraction
    greenflare_config = {
        'start_urls': ['https://adrianl61.sg-host.com/'], 
        'max_depth': 1, 
        'respect_robots_txt': True, 
        'check_external_links': False,
        'extract_images': True,
        'extract_alt_text': True,
        'meta_tags': ["title", "description"]
    }
    
    print(f"📋 Configuration:")
    for key, value in greenflare_config.items():
        print(f"   {key}: {value}")
    print()
    
    print(f"🚀 Running crawl...")
    
    try:
        crawler = bot.configure(greenflare_config)
        
        # Show crawler settings before running
        print(f"📊 Crawler CRAWL_ITEMS: {crawler.settings.get('CRAWL_ITEMS', [])}")
        print()
        
        results = crawler.run()
        
        print(f"✅ Crawl completed!")
        print(f"📊 Total pages found: {len(results.get('pages', []))}")
        print()
        
        # Analyze first page
        pages = results.get('pages', [])
        if pages:
            page = pages[0]
            print(f"🔍 Analyzing first page: {page.get('url', 'Unknown')}")
            print(f"   Status: {page.get('status_code', 'Unknown')}")
            print(f"   Title: {page.get('title', 'No title')}")
            
            # Check raw data keys
            print(f"   Available keys: {list(page.keys())}")
            
            # Check for meta description specifically
            if 'meta_description' in page:
                meta_desc = page.get('meta_description')
                print(f"   Meta description: '{meta_desc}'")
                if not meta_desc:
                    print(f"   ⚠️  Meta description is empty!")
            else:
                print(f"   ❌ No 'meta_description' key found!")
            
            # Check for missing meta tags
            missing_meta = page.get('missing_meta_tags', {})
            print(f"   Missing meta tags: {missing_meta}")
            
        else:
            print(f"❌ No pages found in results!")
        
    except Exception as e:
        print(f"❌ Error during crawl: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_greenflare_extraction()
