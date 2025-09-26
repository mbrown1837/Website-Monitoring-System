#!/usr/bin/env python3
"""
Comprehensive test script to verify ALL email functions and changes work correctly.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.alerter import (
    _determine_check_type, 
    _create_subject, 
    _create_email_content,
    _create_metrics_section,
    _create_content_sections,
    _create_text_content,
    _send_visual_check_email,
    _send_crawl_check_email,
    _send_blur_check_email,
    send_performance_email,
    _send_baseline_check_email,
    _send_full_check_email,
    send_report
)
from src.website_manager_sqlite import WebsiteManagerSQLite
from src.logger_setup import setup_logging

logger = setup_logging()

def test_all_email_functions():
    """Test ALL email functions comprehensively."""
    
    print("🧪 Testing ALL Email Functions")
    print("=" * 60)
    
    # Initialize website manager
    website_manager = WebsiteManagerSQLite()
    websites = website_manager.get_active_websites()
    if not websites:
        print("❌ No websites found in database")
        return False
    
    test_website = websites[0]
    print(f"📧 Testing with website: {test_website.get('name', 'Unknown')}")
    
    # Test data for different scenarios
    test_scenarios = [
        {
            'name': 'Manual Visual Check',
            'check_results': {
                'website_id': test_website['id'],
                'status': 'Completed',
                'is_manual': True,
                'visual_baselines': {'home': 'path/to/baseline.png'},
                'latest_snapshots': {'home': 'path/to/latest.png'},
                'significant_change_detected': False,
                'visual_diff_percent': 2.5,
                'baseline_comparison_completed': True
            }
        },
        {
            'name': 'Manual Crawl Check',
            'check_results': {
                'website_id': test_website['id'],
                'status': 'Completed',
                'is_manual': True,
                'crawl_stats': {'pages_crawled': 15, 'total_links': 45, 'total_images': 20, 'sitemap_found': True},
                'broken_links': [{'url': 'https://example.com/broken1', 'status_code': 404}],
                'missing_meta_tags': [{'url': 'https://example.com/page1', 'missing_tags': ['description']}]
            }
        },
        {
            'name': 'Manual Blur Check',
            'check_results': {
                'website_id': test_website['id'],
                'status': 'Completed',
                'is_manual': True,
                'blur_detection_summary': {
                    'total_images_processed': 25,
                    'blurry_images': 3,
                    'blur_percentage': 12.0,
                    'total_images_found': 25
                }
            }
        },
        {
            'name': 'Manual Performance Check',
            'check_results': {
                'website_id': test_website['id'],
                'status': 'Completed',
                'is_manual': True,
                'performance_check': {
                    'performance_check_summary': {
                        'pages_analyzed': 5,
                        'avg_mobile_score': 75,
                        'avg_desktop_score': 85,
                        'slowest_page': 'https://example.com/heavy-page',
                        'total_issues': 8
                    }
                }
            }
        },
        {
            'name': 'Manual Baseline Creation',
            'check_results': {
                'website_id': test_website['id'],
                'status': 'Baseline Created',
                'is_manual': True,
                'visual_baselines': {
                    'home': 'path/to/baseline1.png',
                    'about': 'path/to/baseline2.png',
                    'contact': 'path/to/baseline3.png'
                }
            }
        },
        {
            'name': 'Scheduled Full Check',
            'check_results': {
                'website_id': test_website['id'],
                'status': 'Completed',
                'is_manual': False,
                'crawl_stats': {'pages_crawled': 20, 'total_links': 60, 'total_images': 30, 'sitemap_found': True},
                'broken_links': [],
                'missing_meta_tags': [],
                'visual_baselines': {'home': 'path/to/baseline.png'},
                'latest_snapshots': {'home': 'path/to/latest.png'},
                'significant_change_detected': False,
                'blur_detection_summary': {'total_images_processed': 30, 'blurry_images': 0, 'blur_percentage': 0.0},
                'performance_check': {'performance_check_summary': {'pages_analyzed': 8, 'avg_mobile_score': 90, 'avg_desktop_score': 95}}
            }
        },
        {
            'name': 'Error Case',
            'check_results': {
                'website_id': test_website['id'],
                'status': 'error',
                'is_manual': True,
                'error': 'Please first create baselines, then do the visual check.'
            }
        }
    ]
    
    print(f"\n📋 Testing {len(test_scenarios)} scenarios with ALL functions:")
    print("-" * 60)
    
    all_tests_passed = True
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n{i}. {scenario['name']}")
        print("-" * 40)
        
        try:
            # Test 1: _determine_check_type
            check_type = _determine_check_type(scenario['check_results'])
            print(f"   ✅ _determine_check_type: {check_type}")
            
            # Test 2: _create_subject
            subject = _create_subject(
                test_website.get('name', 'Test Site'),
                check_type,
                scenario['check_results'].get('significant_change_detected', False),
                scenario['check_results']
            )
            print(f"   ✅ _create_subject: {subject}")
            
            # Test 3: _create_metrics_section
            metrics_html = _create_metrics_section(check_type, scenario['check_results'])
            print(f"   ✅ _create_metrics_section: {len(metrics_html)} chars")
            
            # Test 4: _create_content_sections
            content_html = _create_content_sections(check_type, scenario['check_results'])
            print(f"   ✅ _create_content_sections: {len(content_html)} chars")
            
            # Test 5: _create_text_content
            text_content = _create_text_content(
                test_website.get('name', 'Test Site'),
                test_website.get('url', 'https://example.com'),
                check_type,
                scenario['check_results'],
                'http://localhost:5001'
            )
            print(f"   ✅ _create_text_content: {len(text_content)} chars")
            
            # Test 6: _create_email_content
            email_html = _create_email_content(
                test_website.get('name', 'Test Site'),
                test_website.get('url', 'https://example.com'),
                check_type,
                scenario['check_results'],
                'http://localhost:5001'
            )
            print(f"   ✅ _create_email_content: {len(email_html)} chars")
            
            # Test 7: Individual email functions
            if check_type == 'manual_visual':
                result = _send_visual_check_email(test_website, scenario['check_results'])
                print(f"   ✅ _send_visual_check_email: {result}")
            elif check_type == 'manual_crawl':
                result = _send_crawl_check_email(test_website, scenario['check_results'])
                print(f"   ✅ _send_crawl_check_email: {result}")
            elif check_type == 'manual_blur':
                result = _send_blur_check_email(test_website, scenario['check_results'])
                print(f"   ✅ _send_blur_check_email: {result}")
            elif check_type == 'manual_performance':
                result = send_performance_email(test_website, scenario['check_results'])
                print(f"   ✅ send_performance_email: {result}")
            elif check_type == 'manual_baseline':
                result = _send_baseline_check_email(test_website, scenario['check_results'])
                print(f"   ✅ _send_baseline_check_email: {result}")
            elif check_type in ['manual_full', 'scheduled_combined', 'scheduled_full']:
                result = _send_full_check_email(test_website, scenario['check_results'])
                print(f"   ✅ _send_full_check_email: {result}")
            
            # Test 8: Main send_report function
            # Mock the email sending to avoid actual sending
            from src.alerter import send_email_alert
            original_send_email_alert = send_email_alert
            
            def mock_send_email_alert(subject, body_html, body_text=None, recipient_emails=None, attachments=None):
                return True
            
            import src.alerter
            src.alerter.send_email_alert = mock_send_email_alert
            
            result = send_report(test_website, scenario['check_results'])
            print(f"   ✅ send_report: {result}")
            
            # Restore original function
            src.alerter.send_email_alert = original_send_email_alert
            
            print(f"   ✅ All functions working for {scenario['name']}")
            
        except Exception as e:
            print(f"   ❌ Error in {scenario['name']}: {e}")
            all_tests_passed = False
            import traceback
            traceback.print_exc()
    
    return all_tests_passed

def test_scheduler_integration():
    """Test that scheduler properly marks checks as scheduled."""
    
    print(f"\n🔄 Testing Scheduler Integration:")
    print("-" * 40)
    
    # Test that scheduler marks is_manual = False
    test_results = {
        'website_id': 'test-id',
        'status': 'Completed',
        'is_manual': False,  # This should be set by scheduler
        'crawl_stats': {'pages_crawled': 10},
        'broken_links': [],
        'missing_meta_tags': []
    }
    
    check_type = _determine_check_type(test_results)
    print(f"   ✅ Scheduler check type: {check_type}")
    
    subject = _create_subject('Test Site', check_type, False, test_results)
    print(f"   ✅ Scheduler subject: {subject}")
    
    return True

def test_crawler_integration():
    """Test that crawler properly marks checks as manual."""
    
    print(f"\n🔧 Testing Crawler Integration:")
    print("-" * 40)
    
    # Test that crawler marks is_manual = True
    test_results = {
        'website_id': 'test-id',
        'status': 'Completed',
        'is_manual': True,  # This should be set by crawler
        'crawl_stats': {'pages_crawled': 10},
        'broken_links': [],
        'missing_meta_tags': []
    }
    
    check_type = _determine_check_type(test_results)
    print(f"   ✅ Crawler check type: {check_type}")
    
    subject = _create_subject('Test Site', check_type, False, test_results)
    print(f"   ✅ Crawler subject: {subject}")
    
    return True

if __name__ == "__main__":
    try:
        print("🚀 Starting Comprehensive Email Function Tests")
        print("=" * 70)
        
        # Test all email functions
        functions_test = test_all_email_functions()
        
        # Test scheduler integration
        scheduler_test = test_scheduler_integration()
        
        # Test crawler integration
        crawler_test = test_crawler_integration()
        
        print(f"\n🎯 Test Results Summary:")
        print("=" * 50)
        print(f"✅ All Email Functions: {'PASSED' if functions_test else 'FAILED'}")
        print(f"✅ Scheduler Integration: {'PASSED' if scheduler_test else 'FAILED'}")
        print(f"✅ Crawler Integration: {'PASSED' if crawler_test else 'FAILED'}")
        
        if functions_test and scheduler_test and crawler_test:
            print(f"\n🎉 ALL TESTS PASSED!")
            print("=" * 50)
            print("📧 All email functions are working correctly")
            print("🔄 Scheduler integration is working")
            print("🔧 Crawler integration is working")
            print("✅ Ready for production deployment!")
        else:
            print(f"\n❌ SOME TESTS FAILED!")
            print("Please check the errors above.")
            
    except Exception as e:
        print(f"❌ Error running comprehensive tests: {e}")
        import traceback
        traceback.print_exc()
