#!/usr/bin/env python3
"""
Debug script to check meta tag detection in the database
"""

import os
import sys
import sqlite3
import json

# Add src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def check_database_meta_tags():
    """Check what meta tag data is actually in the database."""
    db_path = 'data/website_monitor.db'
    
    print("=" * 60)
    print("META TAGS DEBUG ANALYSIS")
    print("=" * 60)
    print()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check recent crawl results
        print("🔍 Checking recent crawl results...")
        cursor.execute('''
            SELECT cr.id, cr.website_id, cr.timestamp, cr.crawl_data 
            FROM crawl_results cr 
            ORDER BY cr.timestamp DESC 
            LIMIT 3
        ''')
        
        crawl_results = cursor.fetchall()
        
        for crawl_id, website_id, timestamp, crawl_data_json in crawl_results:
            print(f"\n📊 Crawl ID: {crawl_id}")
            print(f"   Website ID: {website_id}")
            print(f"   Timestamp: {timestamp}")
            
            # Parse crawl data
            try:
                crawl_data = json.loads(crawl_data_json)
                pages = crawl_data.get('all_pages', [])
                print(f"   Total pages: {len(pages)}")
                
                # Check first few pages for meta tag data
                for i, page in enumerate(pages[:3]):
                    print(f"\n   📄 Page {i+1}: {page.get('url', 'Unknown URL')}")
                    print(f"      Status: {page.get('status_code', 'Unknown')}")
                    print(f"      Title: {page.get('title', 'No title found')}")
                    
                    # Check for meta tags in page data
                    meta_tags = page.get('meta_tags', {})
                    print(f"      Meta tags: {meta_tags}")
                    
                    # Check for missing meta tags
                    missing_meta = page.get('missing_meta_tags', {})
                    print(f"      Missing meta: {missing_meta}")
                    
                    # Check raw page data for description
                    if 'meta_description' in page:
                        print(f"      Meta description: '{page.get('meta_description', 'Not found')}'")
                    else:
                        print(f"      Meta description key: NOT PRESENT")
                
            except json.JSONDecodeError as e:
                print(f"   ❌ Error parsing crawl data: {e}")
        
        # Check missing_meta_tags table
        print(f"\n🔍 Checking missing_meta_tags table...")
        cursor.execute('''
            SELECT mmt.crawl_id, mmt.url, mmt.type, mmt.element, mmt.details
            FROM missing_meta_tags mmt
            ORDER BY mmt.crawl_id DESC
            LIMIT 10
        ''')
        
        missing_tags = cursor.fetchall()
        
        if missing_tags:
            print(f"   Found {len(missing_tags)} missing meta tag records:")
            for crawl_id, url, tag_type, element, details in missing_tags:
                print(f"   • Crawl {crawl_id}: {tag_type} missing on {url}")
                print(f"     Details: {details}")
        else:
            print("   ❌ No missing meta tags found in database!")
        
        # Check websites table
        print(f"\n🔍 Checking websites...")
        cursor.execute('SELECT id, name, url FROM websites')
        websites = cursor.fetchall()
        
        for website_id, name, url in websites:
            print(f"   • {name}: {url} (ID: {website_id})")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Database error: {e}")

def test_url_directly():
    """Test meta tag extraction on a specific URL."""
    print(f"\n🧪 TESTING URL DIRECTLY")
    print("=" * 40)
    
    import requests
    from bs4 import BeautifulSoup
    
    test_url = "https://adrianl61.sg-host.com/"
    
    try:
        print(f"📡 Fetching: {test_url}")
        response = requests.get(test_url, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Check title
            title = soup.find('title')
            print(f"🏷️  Title: '{title.text if title else 'NOT FOUND'}'")
            
            # Check meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc:
                print(f"📝 Meta description: '{meta_desc.get('content', 'NO CONTENT')}'")
            else:
                print(f"📝 Meta description: NOT FOUND")
            
            # Check all meta tags
            meta_tags = soup.find_all('meta')
            print(f"🔍 Total meta tags found: {len(meta_tags)}")
            
            for meta in meta_tags[:5]:  # Show first 5
                name = meta.get('name', meta.get('property', 'unknown'))
                content = meta.get('content', 'no content')[:50]
                print(f"   • {name}: {content}...")
        else:
            print(f"❌ HTTP {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error testing URL: {e}")

if __name__ == '__main__':
    check_database_meta_tags()
    test_url_directly()
