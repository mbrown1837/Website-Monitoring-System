#!/usr/bin/env python3
"""
Integration Test Runner for Website Monitoring System
Runs comprehensive integration tests for hosted environment scenarios.
"""

import sys
import os
import unittest
import tempfile
import shutil
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def setup_test_environment():
    """Set up test environment variables."""
    # Set test environment variables
    os.environ['ENVIRONMENT'] = 'testing'
    os.environ['FLASK_ENV'] = 'testing'
    
    # Set test-specific environment variables
    test_env_vars = {
        'WEBSITE_MONITOR_DASHBOARD_PORT': '5002',
        'WEBSITE_MONITOR_LOG_LEVEL': 'DEBUG',
        'WEBSITE_MONITOR_SCHEDULER_ENABLED': 'false',
        'WEBSITE_MONITOR_PLAYWRIGHT_HEADLESS_MODE': 'true',
        'WEBSITE_MONITOR_SMTP_SERVER': 'test.smtp.com',
        'WEBSITE_MONITOR_SMTP_USERNAME': 'test@example.com',
        'WEBSITE_MONITOR_SMTP_PASSWORD': 'test_password'
    }
    
    for key, value in test_env_vars.items():
        os.environ[key] = value

def cleanup_test_environment():
    """Clean up test environment."""
    # Remove test environment variables
    test_env_vars = [
        'WEBSITE_MONITOR_DASHBOARD_PORT',
        'WEBSITE_MONITOR_LOG_LEVEL',
        'WEBSITE_MONITOR_SCHEDULER_ENABLED',
        'WEBSITE_MONITOR_PLAYWRIGHT_HEADLESS_MODE',
        'WEBSITE_MONITOR_SMTP_SERVER',
        'WEBSITE_MONITOR_SMTP_USERNAME',
        'WEBSITE_MONITOR_SMTP_PASSWORD'
    ]
    
    for var in test_env_vars:
        if var in os.environ:
            del os.environ[var]

def run_integration_tests():
    """Run integration tests with proper setup and reporting."""
    print("=" * 80)
    print("WEBSITE MONITORING SYSTEM - INTEGRATION TESTS")
    print("=" * 80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Set up test environment
    setup_test_environment()
    
    try:
        # Discover and run tests
        loader = unittest.TestLoader()
        start_dir = os.path.join(os.path.dirname(__file__), 'tests')
        suite = loader.discover(start_dir, pattern='test_integration.py')
        
        # Run tests with verbose output
        runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
        result = runner.run(suite)
        
        # Print summary
        print("\n" + "=" * 80)
        print("INTEGRATION TEST SUMMARY")
        print("=" * 80)
        print(f"Tests run: {result.testsRun}")
        print(f"Failures: {len(result.failures)}")
        print(f"Errors: {len(result.errors)}")
        print(f"Skipped: {len(result.skipped) if hasattr(result, 'skipped') else 0}")
        
        if result.failures:
            print("\nFAILURES:")
            for test, traceback in result.failures:
                print(f"- {test}: {traceback}")
        
        if result.errors:
            print("\nERRORS:")
            for test, traceback in result.errors:
                print(f"- {test}: {traceback}")
        
        # Determine overall success
        success = result.wasSuccessful()
        status = "PASSED" if success else "FAILED"
        print(f"\nOverall Status: {status}")
        
        return success
        
    finally:
        # Clean up test environment
        cleanup_test_environment()

def run_specific_test(test_name):
    """Run a specific integration test."""
    print(f"Running specific test: {test_name}")
    
    setup_test_environment()
    
    try:
        loader = unittest.TestLoader()
        start_dir = os.path.join(os.path.dirname(__file__), 'tests')
        suite = loader.discover(start_dir, pattern='test_integration.py')
        
        # Filter to specific test
        filtered_suite = unittest.TestSuite()
        for test_suite in suite:
            for test_case in test_suite:
                if test_name in str(test_case):
                    filtered_suite.addTest(test_case)
        
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(filtered_suite)
        
        return result.wasSuccessful()
        
    finally:
        cleanup_test_environment()

def main():
    """Main function to run integration tests."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run integration tests for Website Monitoring System')
    parser.add_argument('--test', '-t', help='Run specific test (partial name match)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    if args.test:
        success = run_specific_test(args.test)
    else:
        success = run_integration_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main() 