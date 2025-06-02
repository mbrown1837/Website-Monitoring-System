import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import sys
import hashlib
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src import snapshot_tool
from src.config_loader import _config_cache, get_config

class TestSnapshotTool(unittest.TestCase):

    def setUp(self):
        _config_cache.clear()
        self.site_id = "test_site_123"
        self.html_content = "<html><body><h1>Test Page</h1></body></html>"
        self.timestamp = datetime(2023, 1, 1, 12, 0, 0)
        self.formatted_timestamp = self.timestamp.strftime("%Y%m%d_%H%M%S")

        self.test_config = {
            'snapshot_directory': "/tmp/snapshots",
            'webdriver_path': '/mock/driver/path' # Needed for visual snapshot part
        }
        self.get_config_patcher = patch('src.snapshot_tool.get_config', return_value=self.test_config)
        self.mock_get_config = self.get_config_patcher.start()
        snapshot_tool.config = self.test_config

        # Patch os.makedirs and os.path.exists for filesystem interaction
        self.makedirs_patcher = patch('os.makedirs')
        self.mock_makedirs = self.makedirs_patcher.start()
        self.path_exists_patcher = patch('os.path.exists', return_value=True) # Assume paths exist unless specified
        self.mock_path_exists = self.path_exists_patcher.start()

        # Patch open for file writing
        self.open_patcher = patch('builtins.open', new_callable=mock_open)
        self.mock_file_open = self.open_patcher.start()

    def tearDown(self):
        self.get_config_patcher.stop()
        self.makedirs_patcher.stop()
        self.path_exists_patcher.stop()
        self.open_patcher.stop()
        _config_cache.clear()
        snapshot_tool.config = get_config() # Reset config

    @patch('time.strftime', return_value="20230101_120000") # Mock timestamp generation within function
    def test_save_html_snapshot_success(self, mock_strftime):
        expected_dir = os.path.join(self.test_config['snapshot_directory'], self.site_id, "html")
        expected_filename = f"{self.site_id}_{self.formatted_timestamp}.html"
        expected_filepath = os.path.join(expected_dir, expected_filename)
        expected_hash = hashlib.sha256(self.html_content.encode('utf-8')).hexdigest()

        # Simulate directory not existing initially to test creation
        self.mock_path_exists.return_value = False

        filepath, content_hash = snapshot_tool.save_html_snapshot(
            self.site_id, self.html_content, self.timestamp
        )

        self.assertEqual(filepath, expected_filepath)
        self.assertEqual(content_hash, expected_hash)
        self.mock_makedirs.assert_called_once_with(expected_dir, exist_ok=True)
        self.mock_file_open.assert_called_once_with(expected_filepath, 'w', encoding='utf-8')
        handle = self.mock_file_open()
        handle.write.assert_called_once_with(self.html_content)

    @patch('time.strftime', return_value="20230101_120000")
    def test_save_html_snapshot_io_error(self, mock_strftime):
        self.mock_file_open.side_effect = IOError("Cannot write to disk")

        filepath, content_hash = snapshot_tool.save_html_snapshot(
            self.site_id, self.html_content, self.timestamp
        )
        self.assertIsNone(filepath)
        self.assertIsNone(content_hash)
        # Check logs or error handling if specific logging is added for IOError

    @patch('src.snapshot_tool.webdriver') # Mock the entire selenium.webdriver module
    @patch('time.strftime', return_value="20230101_120000")
    @patch('time.sleep') # Mock time.sleep
    def test_save_visual_snapshot_success(self, mock_sleep, mock_strftime, mock_webdriver):
        test_url = "http://example.com"
        expected_dir = os.path.join(self.test_config['snapshot_directory'], self.site_id, "visual")
        expected_filename = f"{self.site_id}_{self.formatted_timestamp}.png"
        expected_filepath = os.path.join(expected_dir, expected_filename)

        mock_driver_instance = MagicMock()
        mock_webdriver.Chrome.return_value.__enter__.return_value = mock_driver_instance # For context manager

        # Simulate directory not existing initially
        self.mock_path_exists.return_value = False

        filepath = snapshot_tool.save_visual_snapshot(self.site_id, test_url, self.timestamp)

        self.assertEqual(filepath, expected_filepath)
        self.mock_makedirs.assert_called_once_with(expected_dir, exist_ok=True)
        mock_webdriver.ChromeOptions.assert_called_once()
        # Check for headless and other options being added if they are in your code
        # options = mock_webdriver.ChromeOptions.return_value
        # self.assertTrue(any(arg == '--headless' for arg in options.arguments))
        mock_webdriver.Chrome.assert_called_once()
        mock_driver_instance.get.assert_called_once_with(test_url)
        mock_driver_instance.set_window_size.assert_called_once_with(1920, 1080) # Or configured size
        mock_driver_instance.save_screenshot.assert_called_once_with(expected_filepath)
        mock_sleep.assert_called_once_with(snapshot_tool.SELENIUM_LOAD_WAIT_SECONDS)

    @patch('src.snapshot_tool.webdriver')
    @patch('time.strftime', return_value="20230101_120000")
    @patch('time.sleep')
    def test_save_visual_snapshot_selenium_error(self, mock_sleep, mock_strftime, mock_webdriver):
        test_url = "http://example.com"
        mock_driver_instance = MagicMock()
        mock_webdriver.Chrome.return_value.__enter__.return_value = mock_driver_instance
        mock_driver_instance.get.side_effect = Exception("Selenium failed to get URL")

        filepath = snapshot_tool.save_visual_snapshot(self.site_id, test_url, self.timestamp)
        self.assertIsNone(filepath)
        # Add log checking if specific logging is done for selenium errors

    @patch('src.snapshot_tool.webdriver')
    @patch('time.strftime', return_value="20230101_120000")
    @patch('time.sleep')
    def test_save_visual_snapshot_no_webdriver_path(self, mock_sleep, mock_strftime, mock_webdriver):
        # Temporarily modify config for this test
        original_config = snapshot_tool.config
        snapshot_tool.config = snapshot_tool.config.copy()
        snapshot_tool.config['webdriver_path'] = None
        self.mock_get_config.return_value = snapshot_tool.config

        filepath = snapshot_tool.save_visual_snapshot(self.site_id, "http://example.com", self.timestamp)
        self.assertIsNone(filepath)
        # Expected: logs an error and returns None.
        # Check with self.assertLogs if you have specific logging for this case.
        mock_webdriver.Chrome.assert_not_called() # Should not attempt to start if no path
        
        snapshot_tool.config = original_config # Restore
        self.mock_get_config.return_value = original_config

if __name__ == '__main__':
    unittest.main() 