#!/usr/bin/env python3
"""
Test manual check buttons functionality and baseline creation with global exclude keywords.
"""

import sys
import os
import time

# Add src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from src.website_manager_sqlite import WebsiteManager
    from src.crawler_module import CrawlerModule
    from src.config_loader import get_config
    from src.logger_setup import setup_logging
    from src.queue_processor import get_queue_processor
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

logger = setup_logging()

def test_manual_check_configurations():
    """Test that manual check configurations are correct for each check type."""
    print("🧪 Testing Manual Check Configurations")
    print("=" * 50)
    
    try:
        website_manager = WebsiteManager()
        
        # Create a test website
        test_website = {
            'name': 'Test Manual Checks Site',
            'url': 'https://example.com',
            'check_interval_minutes': 1440,
            'max_crawl_depth': 2,
            'is_active': True,
            'capture_subpages': True,
            'auto_crawl_enabled': True,
            'auto_visual_enabled': True,
            'auto_blur_enabled': True,
            'enable_blur_detection': True,
            'auto_performance_enabled': True,
            'auto_full_check_enabled': True,
            'render_delay': 6,
            'visual_diff_threshold': 5,
            'blur_detection_scheduled': False,
            'blur_detection_manual': True,
            'exclude_pages_keywords': [],
            'tags': [],
            'notification_emails': []
        }
        
        # Add test website
        result = website_manager.add_website(test_website)
        if not result:
            print("❌ Failed to add test website")
            return False
            
        website_id = result['id']
        print(f"✅ Test website added - ID: {website_id}")
        
        # Test each check type configuration
        check_types = ['full', 'visual', 'crawl', 'blur', 'performance', 'baseline']
        
        for check_type in check_types:
            config = website_manager.get_manual_check_config(website_id, check_type)
            print(f"\n📋 {check_type.upper()} Check Configuration:")
            
            if check_type == 'full':
                expected = {'crawl_enabled': True, 'visual_enabled': True, 'blur_enabled': True, 'performance_enabled': True}
            elif check_type == 'visual':
                expected = {'crawl_enabled': False, 'visual_enabled': True, 'blur_enabled': False, 'performance_enabled': False}
            elif check_type == 'crawl':
                expected = {'crawl_enabled': True, 'visual_enabled': False, 'blur_enabled': False, 'performance_enabled': False}
            elif check_type == 'blur':
                expected = {'crawl_enabled': False, 'visual_enabled': False, 'blur_enabled': True, 'performance_enabled': False}
            elif check_type == 'performance':
                expected = {'crawl_enabled': False, 'visual_enabled': False, 'blur_enabled': False, 'performance_enabled': True}
            elif check_type == 'baseline':
                expected = {'crawl_enabled': False, 'visual_enabled': True, 'blur_enabled': False, 'performance_enabled': False}
            
            print(f"   Expected: {expected}")
            print(f"   Actual:   {config}")
            
            if config == expected:
                print(f"   ✅ {check_type} configuration is correct")
            else:
                print(f"   ❌ {check_type} configuration is incorrect")
                return False
        
        # Clean up test website
        website_manager.remove_website(website_id)
        print(f"\n✅ Test website cleaned up")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        logger.error(f"Manual check configuration test failed: {e}", exc_info=True)
        return False

def test_global_exclude_keywords():
    """Test that baseline creation respects global exclude keywords."""
    print("\n🧪 Testing Global Exclude Keywords")
    print("=" * 50)
    
    try:
        # Get global config
        config = get_config()
        global_exclude_keywords = config.get('exclude_pages_keywords', ['products', 'blogs', 'blog', 'product'])
        print(f"📋 Global exclude keywords: {global_exclude_keywords}")
        
        # Test URL filtering
        crawler = CrawlerModule()
        
        test_urls = [
            'https://example.com/',
            'https://example.com/products',
            'https://example.com/blogs',
            'https://example.com/blog',
            'https://example.com/product',
            'https://example.com/about',
            'https://example.com/contact',
            'https://example.com/products/item1',
            'https://example.com/blogs/post1',
            'https://example.com/admin',
            'https://example.com/login'
        ]
        
        print(f"\n🔍 Testing URL exclusion for baseline creation:")
        
        excluded_count = 0
        included_count = 0
        
        for url in test_urls:
            should_exclude = crawler._should_exclude_url_for_checks(url, 'baseline')
            status = "❌ EXCLUDED" if should_exclude else "✅ INCLUDED"
            print(f"   {url:<40} {status}")
            
            if should_exclude:
                excluded_count += 1
            else:
                included_count += 1
        
        print(f"\n📊 Results:")
        print(f"   URLs included: {included_count}")
        print(f"   URLs excluded: {excluded_count}")
        
        # Verify that pages with exclude keywords are excluded
        expected_excluded = ['products', 'blogs', 'blog', 'product']
        for keyword in expected_excluded:
            test_url = f'https://example.com/{keyword}'
            if not crawler._should_exclude_url_for_checks(test_url, 'baseline'):
                print(f"❌ URL with keyword '{keyword}' should be excluded but wasn't")
                return False
        
        print("✅ Global exclude keywords are working correctly")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        logger.error(f"Global exclude keywords test failed: {e}", exc_info=True)
        return False

def test_queue_processor_integration():
    """Test that manual checks are properly added to the queue."""
    print("\n🧪 Testing Queue Processor Integration")
    print("=" * 50)
    
    try:
        website_manager = WebsiteManager()
        queue_processor = get_queue_processor()
        
        # Create a test website
        test_website = {
            'name': 'Test Queue Integration Site',
            'url': 'https://example.com',
            'check_interval_minutes': 1440,
            'max_crawl_depth': 2,
            'is_active': True,
            'capture_subpages': True,
            'auto_crawl_enabled': True,
            'auto_visual_enabled': True,
            'auto_blur_enabled': True,
            'enable_blur_detection': True,
            'auto_performance_enabled': True,
            'auto_full_check_enabled': True,
            'render_delay': 6,
            'visual_diff_threshold': 5,
            'blur_detection_scheduled': False,
            'blur_detection_manual': True,
            'exclude_pages_keywords': [],
            'tags': [],
            'notification_emails': []
        }
        
        # Add test website
        result = website_manager.add_website(test_website)
        if not result:
            print("❌ Failed to add test website")
            return False
            
        website_id = result['id']
        print(f"✅ Test website added - ID: {website_id}")
        
        # Test adding different check types to queue
        check_types = ['visual', 'crawl', 'blur', 'performance', 'baseline']
        
        for check_type in check_types:
            queue_id = queue_processor.add_manual_check(website_id, check_type)
            if queue_id:
                print(f"✅ {check_type} check added to queue - ID: {queue_id}")
                
                # Get queue status
                status = queue_processor.get_queue_status(queue_id=queue_id)
                if status:
                    print(f"   Status: {status[0]['status']}")
                else:
                    print(f"   ⚠️ Could not get queue status")
            else:
                print(f"❌ Failed to add {check_type} check to queue")
                return False
        
        # Clean up test website
        website_manager.remove_website(website_id)
        print(f"\n✅ Test website cleaned up")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        logger.error(f"Queue processor integration test failed: {e}", exc_info=True)
        return False

def main():
    """Main test function."""
    print("🚀 MANUAL CHECKS VERIFICATION TEST")
    print("=" * 70)
    
    # Test 1: Manual check configurations
    config_test = test_manual_check_configurations()
    
    # Test 2: Global exclude keywords
    exclude_test = test_global_exclude_keywords()
    
    # Test 3: Queue processor integration
    queue_test = test_queue_processor_integration()
    
    print("\n" + "=" * 70)
    print("🎯 MANUAL CHECKS TEST RESULTS:")
    print(f"✅ Manual check configurations: {'PASSED' if config_test else 'FAILED'}")
    print(f"✅ Global exclude keywords: {'PASSED' if exclude_test else 'FAILED'}")
    print(f"✅ Queue processor integration: {'PASSED' if queue_test else 'FAILED'}")
    
    if config_test and exclude_test and queue_test:
        print("\n🎉 All manual checks tests PASSED!")
        print("✅ Individual check buttons work correctly")
        print("✅ Baseline creation respects global exclude keywords")
        print("✅ Queue system integration is working")
        print("\n🚀 Manual checks system is ready for production!")
    else:
        print("\n❌ Some manual checks tests FAILED!")
        print("Check the logs for detailed error information.")
    
    return config_test and exclude_test and queue_test

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
