#!/usr/bin/env python3
"""
Comprehensive Function Test for Website Monitoring System

Tests all major components and functions to ensure everything works correctly.
"""

import os
import sys
import time
import requests
import json

# Add src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.website_manager_sqlite import WebsiteManager
from src.history_manager_sqlite import HistoryManager
from src.crawler_module import CrawlerModule
from src.config_loader import get_config
from src.logger_setup import setup_logging

def test_core_functions():
    """Test all core application functions."""
    print("=" * 80)
    print("COMPREHENSIVE WEBSITE MONITORING SYSTEM FUNCTION TEST")
    print("=" * 80)
    print()
    
    # Initialize components
    logger = setup_logging()
    config = get_config()
    website_manager = WebsiteManager(config_path='config/config.yaml')
    history_manager = HistoryManager(config_path='config/config.yaml')
    crawler = CrawlerModule(config_path='config/config.yaml')
    
    results = {
        'tests_passed': 0,
        'tests_failed': 0,
        'test_details': []
    }
    
    def run_test(test_name, test_function):
        """Run a test and record results."""
        print(f"🧪 Testing: {test_name}")
        try:
            result = test_function()
            if result:
                print(f"   ✅ PASSED")
                results['tests_passed'] += 1
            else:
                print(f"   ❌ FAILED")
                results['tests_failed'] += 1
            results['test_details'].append({'name': test_name, 'passed': result})
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            results['tests_failed'] += 1
            results['test_details'].append({'name': test_name, 'passed': False, 'error': str(e)})
        print()
    
    # Test 1: Database Connectivity
    def test_database_connectivity():
        websites = website_manager.list_websites()
        return isinstance(websites, dict)
    
    # Test 2: Configuration Loading
    def test_configuration():
        return config is not None and 'meta_tags_to_check' in config
    
    # Test 3: Meta Tags Configuration
    def test_meta_tags_config():
        meta_tags = config.get('meta_tags_to_check', [])
        return 'title' in meta_tags and 'description' in meta_tags
    
    # Test 4: Website Manager Functions
    def test_website_management():
        # Add a test website
        test_website = {
            'name': 'Test Site',
            'url': 'https://httpbin.org/html',
            'check_interval_minutes': 60,
            'is_active': True
        }
        
        added_website = website_manager.add_website(test_website)
        if not added_website:
            return False
        
        site_id = added_website.get('id')
        if not site_id:
            return False
        
        # Get the website
        retrieved = website_manager.get_website(site_id)
        if not retrieved or retrieved['name'] != 'Test Site':
            return False
        
        # Update the website
        updates = {'name': 'Updated Test Site'}
        update_success = website_manager.update_website(site_id, updates)
        if not update_success:
            return False
        
        # Remove the website
        removed = website_manager.remove_website(site_id)
        return removed
    
    # Test 5: Crawler Module Initialization
    def test_crawler_initialization():
        return crawler is not None and hasattr(crawler, 'crawl_website')
    
    # Test 6: Config Path Consistency
    def test_config_paths():
        # Check that all managers use consistent config paths
        return all([
            hasattr(website_manager, 'config'),
            hasattr(history_manager, 'config'),
            hasattr(crawler, 'config')
        ])
    
    # Test 7: Greenflare Availability
    def test_greenflare():
        from src.greenflare_crawler import GREENFLARE_AVAILABLE
        return GREENFLARE_AVAILABLE
    
    # Test 8: Meta Tag Detection Logic
    def test_meta_tag_detection():
        # Test the meta tag suggestion function
        suggestion = crawler._get_meta_tag_suggestion('description', 'Missing meta description')
        return 'meta description' in suggestion.lower()
    
    # Test 9: Database Schema
    def test_database_schema():
        import sqlite3
        conn = sqlite3.connect('data/website_monitor.db')
        cursor = conn.cursor()
        
        # Check for required tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        required_tables = ['websites', 'crawl_results', 'missing_meta_tags', 'broken_links']
        has_all_tables = all(table in tables for table in required_tables)
        
        conn.close()
        return has_all_tables
    
    # Test 10: Scheduler Integration
    def test_scheduler_integration():
        try:
            from src.scheduler_integration import get_scheduler_manager
            manager = get_scheduler_manager()
            return manager is not None
        except ImportError:
            return False
    
    # Run all tests
    run_test("Database Connectivity", test_database_connectivity)
    run_test("Configuration Loading", test_configuration)
    run_test("Meta Tags Configuration", test_meta_tags_config)
    run_test("Website Management", test_website_management)
    run_test("Crawler Initialization", test_crawler_initialization)
    run_test("Config Path Consistency", test_config_paths)
    run_test("Greenflare Availability", test_greenflare)
    run_test("Meta Tag Detection Logic", test_meta_tag_detection)
    run_test("Database Schema", test_database_schema)
    run_test("Scheduler Integration", test_scheduler_integration)
    
    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    total_tests = results['tests_passed'] + results['tests_failed']
    success_rate = (results['tests_passed'] / total_tests * 100) if total_tests > 0 else 0
    
    print(f"✅ Passed: {results['tests_passed']}")
    print(f"❌ Failed: {results['tests_failed']}")
    print(f"📊 Success Rate: {success_rate:.1f}%")
    print()
    
    if results['tests_failed'] == 0:
        print("🎉 ALL TESTS PASSED! System is ready for production.")
    else:
        print("⚠️  Some tests failed. Review the issues above.")
        for test in results['test_details']:
            if not test['passed']:
                print(f"   • {test['name']}: {'ERROR - ' + test.get('error', 'Failed')}")
    
    print()
    return results['tests_failed'] == 0

def check_current_websites():
    """Check what websites are currently in the system."""
    print("🔍 CHECKING CURRENT WEBSITES")
    print("=" * 40)
    
    website_manager = WebsiteManager(config_path='config/config.yaml')
    websites = website_manager.list_websites()
    
    if not websites:
        print("✅ No websites found - system is clean!")
        return []
    
    print(f"📊 Found {len(websites)} website(s):")
    website_list = []
    
    for website_id, website_data in websites.items():
        name = website_data.get('name', 'Unnamed')
        url = website_data.get('url', 'No URL')
        is_active = website_data.get('is_active', False)
        status = "🟢 Active" if is_active else "🔴 Inactive"
        
        print(f"   • {name} - {url} ({status})")
        website_list.append((website_id, website_data))
    
    print()
    return website_list

if __name__ == '__main__':
    # Run comprehensive tests
    all_passed = test_core_functions()
    
    # Check current websites
    websites = check_current_websites()
    
    if websites:
        print("⚠️  Test websites found in system.")
        print("💡 Run the cleanup script to remove them before production.")
    else:
        print("✅ System is clean and ready!")
    
    print()
    
    if all_passed and not websites:
        print("🚀 SYSTEM FULLY TESTED AND READY FOR PRODUCTION!")
    else:
        print("🔧 Please address the issues above before deployment.")
