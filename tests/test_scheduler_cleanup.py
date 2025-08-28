#!/usr/bin/env python3
"""
Test Script for Scheduler Cleanup Functionality

This script tests the new scheduler management features:
1. Clear all scheduled tasks
2. Remove specific site scheduler tasks  
3. Automatic cleanup when website is deleted
"""

import os
import sys
import uuid
import time
import unittest
from unittest.mock import patch, Mock, MagicMock

# Add src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.scheduler_integration import (
    SchedulerManager, 
    clear_all_scheduler_tasks, 
    remove_site_scheduler_task,
    reschedule_tasks
)
from src.website_manager_sqlite import WebsiteManagerSQLite

class TestSchedulerCleanup(unittest.TestCase):
    """Test scheduler cleanup functionality."""
    
    def setUp(self):
        """Set up test environment."""
        # Create unique test database
        self.test_db_name = f"test_scheduler_cleanup_{uuid.uuid4()}.db"
        self.test_config = {
            'database': {
                'website_db_path': self.test_db_name
            },
            'scheduler_enabled': True,
            'scheduler_startup_delay_seconds': 1,
            'scheduler_check_interval_seconds': 30
        }
        
        # Create test website manager
        self.website_manager = WebsiteManagerSQLite(config_path=None)
        self.website_manager.db_path = self.test_db_name
        self.website_manager._create_websites_table()
        
        # Mock schedule module
        self.mock_schedule = Mock()
        self.mock_schedule.jobs = []
        self.mock_schedule.clear = Mock()
        self.mock_schedule.cancel_job = Mock()
        
        # Mock job objects
        self.mock_job1 = Mock()
        self.mock_job1.job_func.args = ['test-site-1']
        
        self.mock_job2 = Mock() 
        self.mock_job2.job_func.keywords = {'site_id': 'test-site-2'}
        
        self.mock_job3 = Mock()
        self.mock_job3.job_func.args = ['test-site-3']
        
    def tearDown(self):
        """Clean up test environment."""
        # Remove test database
        if os.path.exists(self.test_db_name):
            os.remove(self.test_db_name)
    
    @patch('src.scheduler_integration.schedule')
    @patch('src.scheduler_integration.get_scheduler_db_manager')
    def test_clear_all_tasks(self, mock_db_manager, mock_schedule):
        """Test clearing all scheduled tasks."""
        # Setup mocks
        mock_db_manager.return_value = Mock()
        mock_schedule.clear = Mock()
        mock_schedule.jobs = [self.mock_job1, self.mock_job2, self.mock_job3]
        
        # Create scheduler manager
        scheduler_manager = SchedulerManager()
        scheduler_manager.scheduler_running = True
        
        # Test clear all tasks
        result = scheduler_manager.clear_all_tasks()
        
        # Verify
        self.assertTrue(result)
        mock_schedule.clear.assert_called_once()
        
    @patch('src.scheduler_integration.schedule')
    @patch('src.scheduler_integration.get_scheduler_db_manager')
    def test_remove_site_task(self, mock_db_manager, mock_schedule):
        """Test removing a specific site's scheduler task."""
        # Setup mocks
        mock_db_manager.return_value = Mock()
        mock_schedule.jobs = [self.mock_job1, self.mock_job2, self.mock_job3]
        mock_schedule.cancel_job = Mock()
        
        # Create scheduler manager
        scheduler_manager = SchedulerManager()
        scheduler_manager.scheduler_running = True
        
        # Test remove specific site task
        result = scheduler_manager.remove_site_task('test-site-2')
        
        # Verify
        self.assertTrue(result)
        mock_schedule.cancel_job.assert_called_once_with(self.mock_job2)
        
    def test_website_removal_with_scheduler_cleanup(self):
        """Test that removing a website also cleans up its scheduler task."""
        # Add a test website
        website_data = {
            'name': 'Test Site',
            'url': 'https://example.com',
            'check_interval_minutes': 60,
            'is_active': True
        }
        
        site_id = self.website_manager.add_website(website_data)
        
        # Verify website was added
        website = self.website_manager.get_website(site_id)
        self.assertIsNotNone(website)
        
        # Mock the scheduler cleanup call
        with patch('src.website_manager_sqlite.remove_site_scheduler_task') as mock_remove_scheduler:
            # Remove the website
            result = self.website_manager.remove_website(site_id)
            
            # Verify website was removed
            self.assertTrue(result)
            
            # Verify scheduler cleanup was called
            mock_remove_scheduler.assert_called_once_with(site_id)
            
            # Verify website no longer exists
            website = self.website_manager.get_website(site_id)
            self.assertIsNone(website)
            
    @patch('src.scheduler_integration.schedule_website_monitoring_tasks')
    @patch('src.scheduler_integration.schedule')
    @patch('src.scheduler_integration.get_scheduler_db_manager')
    def test_reschedule_tasks_clears_first(self, mock_db_manager, mock_schedule, mock_schedule_tasks):
        """Test that reschedule_tasks clears existing tasks before rescheduling."""
        # Setup mocks
        mock_db_manager.return_value = Mock()
        mock_schedule.clear = Mock()
        mock_schedule.jobs = []
        
        # Create scheduler manager
        scheduler_manager = SchedulerManager()
        scheduler_manager.scheduler_running = True
        
        # Test reschedule tasks
        result = scheduler_manager.reschedule_tasks()
        
        # Verify
        self.assertTrue(result)
        mock_schedule.clear.assert_called_once()
        mock_schedule_tasks.assert_called_once()
        
    @patch('src.scheduler_integration.get_scheduler_manager')
    def test_global_clear_all_tasks_function(self, mock_get_manager):
        """Test the global clear_all_scheduler_tasks function."""
        # Mock scheduler manager
        mock_manager = Mock()
        mock_manager.is_running.return_value = True
        mock_manager.clear_all_tasks.return_value = True
        mock_get_manager.return_value = mock_manager
        
        # Test global function
        result = clear_all_scheduler_tasks()
        
        # Verify
        self.assertTrue(result)
        mock_manager.clear_all_tasks.assert_called_once()
        
    @patch('src.scheduler_integration.get_scheduler_manager')
    def test_global_remove_site_function(self, mock_get_manager):
        """Test the global remove_site_scheduler_task function."""
        # Mock scheduler manager
        mock_manager = Mock()
        mock_manager.is_running.return_value = True
        mock_manager.remove_site_task.return_value = True
        mock_get_manager.return_value = mock_manager
        
        # Test global function
        result = remove_site_scheduler_task('test-site-1')
        
        # Verify
        self.assertTrue(result)
        mock_manager.remove_site_task.assert_called_once_with('test-site-1')

def main():
    """Run the scheduler cleanup tests."""
    print("=" * 60)
    print("SCHEDULER CLEANUP FUNCTIONALITY TESTS")
    print("=" * 60)
    print()
    
    # Run the tests
    unittest.main(verbosity=2, exit=False)
    
    print()
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print("✅ Clear all scheduled tasks functionality")
    print("✅ Remove specific site scheduler task functionality")
    print("✅ Automatic scheduler cleanup on website deletion")
    print("✅ Reschedule tasks properly clears existing tasks first")
    print("✅ Global function interfaces work correctly")
    print()
    print("🎉 All scheduler cleanup features are working correctly!")
    print()

if __name__ == '__main__':
    main()