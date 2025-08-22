import unittest
import time
import os
import sys
from unittest.mock import patch, MagicMock
import uuid

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Import modules after path is set
from src.website_manager_sqlite import WebsiteManager
from src.scheduler import perform_website_check
from src.scheduler_integration import get_scheduler_manager, reschedule_tasks, _scheduler_manager
from src.history_manager_sqlite import HistoryManager

class TestFullAppWorkflow(unittest.TestCase):

    def setUp(self):
        """Set up a test environment before each test."""
        self.config_path = os.path.join(project_root, 'config', 'config.test.yaml')
        
        # Use a unique database for each test to prevent conflicts
        self.db_path = os.path.join(project_root, 'data', f'test_monitor_{uuid.uuid4()}.db')
        
        # Create a test config file with a sanitized path for YAML
        sanitized_db_path = self.db_path.replace('\\', '/')
        with open(self.config_path, 'w') as f:
            f.write(f"""
database_path: "{sanitized_db_path}"
log_level: DEBUG
default_monitoring_interval_minutes: 60
scheduler_enabled: True
            """)
        
        self.website_manager = WebsiteManager(config_path=self.config_path)
        self.history_manager = HistoryManager(config_path=self.config_path)
        
        # Mock external dependencies
        self.crawler_patch = patch('src.scheduler.CrawlerModule')
        self.mock_crawler_module = self.crawler_patch.start()
        
        # Mock the scheduler's internal schedule object to inspect jobs
        self.schedule_patch = patch('src.scheduler.schedule')
        self.mock_schedule = self.schedule_patch.start()
        
        # Patch the get_scheduler_managers function to inject our test managers
        self.get_managers_patch = patch('src.scheduler.get_scheduler_managers')
        self.mock_get_managers = self.get_managers_patch.start()
        self.mock_get_managers.return_value = (
            self.website_manager, 
            self.history_manager, 
            self.mock_crawler_module.return_value, 
            {}
        )

    def tearDown(self):
        """Clean up the test environment after each test."""
        # This helps release the lock on the db file
        self.website_manager = None
        self.history_manager = None
        
        if os.path.exists(self.config_path):
            os.remove(self.config_path)
        
        self.crawler_patch.stop()
        self.schedule_patch.stop()
        self.get_managers_patch.stop()

        # Reset the global scheduler manager to ensure isolation between tests
        global _scheduler_manager
        if _scheduler_manager and hasattr(_scheduler_manager, 'db_manager'):
            _scheduler_manager.db_manager.close_connection()
        _scheduler_manager = None
        
        # Clean up the unique database file
        if os.path.exists(self.db_path):
            os.remove(self.db_path)


    def test_add_website_and_schedule(self):
        """Test adding a website and verifying it gets scheduled correctly."""
        print("\\nRunning: test_add_website_and_schedule")
        
        # Reset mocks for test isolation
        self.mock_schedule.reset_mock()
        
        # 1. Add a new website with a custom interval
        website_data = {
            "name": "Test Site 1",
            "url": "http://testsite1.com",
            "check_interval_minutes": 5
        }
        added_website = self.website_manager.add_website(website_data)
        self.assertIsNotNone(added_website)
        self.assertEqual(added_website['check_interval_minutes'], 5)
        print("  - Website added successfully with interval of 5 minutes.")
        
        # Force the website manager to reload from the database before scheduling
        self.website_manager._load_websites(force_reload=True)

        # 2. Trigger scheduler to load and schedule tasks
        manager = get_scheduler_manager(config_path=self.config_path)
        manager.reschedule_tasks()
        
        # 3. Verify that the scheduler created a job with the correct interval
        self.mock_schedule.every.assert_called_with(5)
        self.mock_schedule.every.return_value.minutes.do.assert_called_with(
            perform_website_check, 
            site_id=added_website['id'],
            config_path=self.config_path
        )
        print("  - Scheduler correctly scheduled the job for 5 minutes.")

    def test_update_website_and_reschedule(self):
        """Test updating a website's interval and ensuring the scheduler reschedules it."""
        print("\\nRunning: test_update_website_and_reschedule")
        
        # Reset mocks for test isolation
        self.mock_schedule.reset_mock()
        
        # 1. Add a website with an initial interval
        website_data = {
            "name": "Test Site 2",
            "url": "http://testsite2.com",
            "check_interval_minutes": 10
        }
        website = self.website_manager.add_website(website_data)
        print(f"  - Added website with ID {website['id']} and interval 10.")
        
        # Force the website manager to reload from the database before scheduling
        self.website_manager._load_websites(force_reload=True)
        
        # 2. Run the scheduler once
        manager = get_scheduler_manager(config_path=self.config_path)
        manager.reschedule_tasks()
        self.mock_schedule.every.assert_called_with(10)
        print("  - Initial schedule call verified for 10 minutes.")

        # 3. Update the website's interval
        self.website_manager.update_website(website['id'], {'check_interval_minutes': 15})
        updated_website = self.website_manager.get_website(website['id'])
        self.assertEqual(updated_website['check_interval_minutes'], 15)
        print("  - Website interval updated to 15 minutes in the database.")
        
        # Force the website manager to reload from the database before rescheduling
        self.website_manager._load_websites(force_reload=True)

        # 4. Trigger a reschedule and verify the new interval is used
        manager.reschedule_tasks()
        self.mock_schedule.every.assert_called_with(15)
        self.mock_schedule.every.return_value.minutes.do.assert_called_with(
            perform_website_check, 
            site_id=website['id'],
            config_path=self.config_path
        )
        print("  - Scheduler correctly rescheduled the job for 15 minutes.")
        
    def test_manual_check_and_history(self):
        """Test running a manual check and verifying history is recorded."""
        print("\\nRunning: test_manual_check_and_history")
        
        # Reset mocks for test isolation
        self.mock_crawler_module.reset_mock()
        
        # 1. Mock the crawler's return value for a successful check
        mock_crawl_result = {
            "status": "No significant change",
            "significant_change_detected": False,
            "check_id": "test_check_123"
        }
        self.mock_crawler_module.return_value.crawl_website.return_value = mock_crawl_result
        
        # 2. Add a website
        website_data = {"name": "Test Site 3", "url": "http://testsite3.com"}
        website = self.website_manager.add_website(website_data)
        print(f"  - Added website for manual check: {website['id']}")

        # 3. Perform a manual check
        result = perform_website_check(site_id=website['id'], config_path=self.config_path)
        self.assertEqual(result['status'], 'No significant change')
        print("  - Manual check performed successfully.")

        # 4. Verify that the history was recorded in the database
        history = self.history_manager.get_history_for_site(website['id'])
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['site_id'], website['id'])
        self.assertEqual(history[0]['status'], 'No significant change')
        print("  - Check history record verified in the database.")

if __name__ == '__main__':
    print("--- Starting Full Application Workflow Test Suite ---")
    unittest.main(verbosity=0)
    print("--- Test Suite Finished ---")
