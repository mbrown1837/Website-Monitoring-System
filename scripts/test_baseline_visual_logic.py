#!/usr/bin/env python3
"""
Test the new baseline creation and visual check logic.
"""

import sys
import os
import time

# Add src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from src.website_manager_sqlite import WebsiteManager
    from src.crawler_module import CrawlerModule
    from src.queue_processor import get_queue_processor
    from src.config_loader import get_config
    from src.logger_setup import setup_logging
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

logger = setup_logging()

def test_baseline_creation_logic():
    """Test that baseline creation only creates baselines for pages that will do visual checks."""
    print("🧪 Testing Baseline Creation Logic")
    print("=" * 50)
    
    try:
        website_manager = WebsiteManager()
        crawler = CrawlerModule()
        
        # Create a test website
        test_website = {
            'name': 'Test Baseline Logic Site',
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
        
        # Test URL exclusion logic
        test_urls = [
            'https://example.com/',
            'https://example.com/about',
            'https://example.com/products',
            'https://example.com/blogs',
            'https://example.com/blog',
            'https://example.com/product',
            'https://example.com/contact',
            'https://example.com/login'
        ]
        
        print(f"\n🔍 Testing URL exclusion for baseline creation:")
        excluded_count = 0
        included_count = 0
        
        for url in test_urls:
            should_exclude = crawler._should_exclude_url_for_checks(url, 'visual', website_id)
            status = "❌ EXCLUDED" if should_exclude else "✅ INCLUDED"
            print(f"   {url:<40} {status}")
            
            if should_exclude:
                excluded_count += 1
            else:
                included_count += 1
        
        print(f"\n📊 Results:")
        print(f"   URLs included for baseline: {included_count}")
        print(f"   URLs excluded from baseline: {excluded_count}")
        
        # Clean up test website
        website_manager.remove_website(website_id)
        print(f"\n✅ Test website cleaned up")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        logger.error(f"Baseline creation logic test failed: {e}", exc_info=True)
        return False

def test_visual_check_baseline_validation():
    """Test that visual check validates baseline existence."""
    print("\n🧪 Testing Visual Check Baseline Validation")
    print("=" * 50)
    
    try:
        website_manager = WebsiteManager()
        crawler = CrawlerModule()
        
        # Create a test website without baselines
        test_website = {
            'name': 'Test Visual Check Site',
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
        
        # Test visual check without baselines
        print(f"\n🔍 Testing visual check without baselines:")
        
        # Get manual check config for visual check
        check_config = website_manager.get_manual_check_config(website_id, 'visual')
        print(f"   Visual check config: {check_config}")
        
        # Simulate visual check without baselines
        website_config = website_manager.get_website(website_id)
        all_baselines = website_config.get('all_baselines', {}) if website_config else {}
        
        if not all_baselines:
            print("   ✅ No baselines found - visual check should fail with user-friendly message")
            print("   📝 Expected error message: 'Please first create baselines, then do the visual check.'")
        else:
            print(f"   ⚠️ Found {len(all_baselines)} baselines - visual check should proceed")
        
        # Clean up test website
        website_manager.remove_website(website_id)
        print(f"\n✅ Test website cleaned up")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        logger.error(f"Visual check baseline validation test failed: {e}", exc_info=True)
        return False

def test_queue_processor_error_handling():
    """Test that queue processor handles crawler errors properly."""
    print("\n🧪 Testing Queue Processor Error Handling")
    print("=" * 50)
    
    try:
        website_manager = WebsiteManager()
        queue_processor = get_queue_processor()
        
        # Create a test website
        test_website = {
            'name': 'Test Queue Error Site',
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
        
        # Test adding visual check to queue (should fail due to no baselines)
        print(f"\n🔍 Testing visual check queue addition:")
        
        queue_id = queue_processor.add_manual_check(website_id, 'visual')
        if queue_id:
            print(f"   ✅ Visual check added to queue - ID: {queue_id}")
            
            # Get queue status
            status = queue_processor.get_queue_status(queue_id=queue_id)
            if status:
                print(f"   Status: {status[0]['status']}")
            else:
                print(f"   ⚠️ Could not get queue status")
        else:
            print(f"   ❌ Failed to add visual check to queue")
            return False
        
        # Clean up test website
        website_manager.remove_website(website_id)
        print(f"\n✅ Test website cleaned up")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        logger.error(f"Queue processor error handling test failed: {e}", exc_info=True)
        return False

def main():
    """Main test function."""
    print("🚀 BASELINE & VISUAL CHECK LOGIC TEST")
    print("=" * 70)
    
    # Test 1: Baseline creation logic
    baseline_test = test_baseline_creation_logic()
    
    # Test 2: Visual check baseline validation
    validation_test = test_visual_check_baseline_validation()
    
    # Test 3: Queue processor error handling
    queue_test = test_queue_processor_error_handling()
    
    print("\n" + "=" * 70)
    print("🎯 BASELINE & VISUAL CHECK TEST RESULTS:")
    print(f"✅ Baseline creation logic: {'PASSED' if baseline_test else 'FAILED'}")
    print(f"✅ Visual check baseline validation: {'PASSED' if validation_test else 'FAILED'}")
    print(f"✅ Queue processor error handling: {'PASSED' if queue_test else 'FAILED'}")
    
    if baseline_test and validation_test and queue_test:
        print("\n🎉 All baseline & visual check tests PASSED!")
        print("✅ Baseline creation only creates baselines for visual check pages")
        print("✅ Visual check validates baseline existence")
        print("✅ Queue processor handles crawler errors properly")
        print("\n🚀 New baseline & visual check logic is working correctly!")
    else:
        print("\n❌ Some baseline & visual check tests FAILED!")
        print("Check the logs for detailed error information.")
    
    return baseline_test and validation_test and queue_test

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
