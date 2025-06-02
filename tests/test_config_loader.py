import unittest
import os
import sys
import yaml

# Add project root to sys.path to allow importing src modules
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.config_loader import load_config, get_config, _config_cache

class TestConfigLoader(unittest.TestCase):

    def setUp(self):
        """Set up for test methods."""
        # Ensure a clean slate for config loading tests
        _config_cache.clear()
        self.test_config_path = os.path.join(PROJECT_ROOT, 'config', 'config.yaml')
        self.backup_config_path = os.path.join(PROJECT_ROOT, 'config', 'config.yaml.bak')

        # Backup existing config if it exists
        if os.path.exists(self.test_config_path):
            os.rename(self.test_config_path, self.backup_config_path)

        # Create a controlled test config
        self.sample_config_data = {
            'log_level': 'INFO',
            'log_file_path': 'logs/app.log',
            'default_monitoring_interval_hours': 12,
            'webdriver_path': 'path/to/chromedriver',
            'notification_email_to': ['test@example.com']
        }
        with open(self.test_config_path, 'w') as f:
            yaml.dump(self.sample_config_data, f)

    def tearDown(self):
        """Clean up after test methods."""
        _config_cache.clear()
        # Delete the test config
        if os.path.exists(self.test_config_path):
            os.remove(self.test_config_path)
        # Restore backup if it exists
        if os.path.exists(self.backup_config_path):
            os.rename(self.backup_config_path, self.test_config_path)

    def test_load_config_success(self):
        """Test successful loading of the config file."""
        config = load_config(self.test_config_path)
        self.assertIsNotNone(config)
        self.assertEqual(config.get('log_level'), 'INFO')
        self.assertEqual(config.get('default_monitoring_interval_hours'), 12)

    def test_get_config_uses_cache(self):
        """Test that get_config uses the cached config after initial load."""
        config1 = load_config(self.test_config_path)
        config2 = get_config()
        self.assertIs(config1, config2) # Should be the same object
        self.assertEqual(config2.get('webdriver_path'), 'path/to/chromedriver')

    def test_load_config_file_not_found(self):
        """Test behavior when the config file is not found."""
        _config_cache.clear() # Ensure cache is clear for this specific test
        non_existent_path = 'config/non_existent_config.yaml'
        with self.assertLogs(level='ERROR') as log:
            config = load_config(non_existent_path)
            self.assertTrue(any("Configuration file not found" in message for message in log.output))
        self.assertIsNotNone(config) # Should return an empty dict
        self.assertEqual(len(config), 0)

    def test_load_config_invalid_yaml(self):
        """Test behavior with an invalid YAML file."""
        _config_cache.clear()
        invalid_yaml_path = os.path.join(PROJECT_ROOT, 'config', 'invalid_config.yaml')
        with open(invalid_yaml_path, 'w') as f:
            f.write("log_level: INFO\n  bad_indent: true") # Invalid YAML
        
        with self.assertLogs(level='ERROR') as log:
            config = load_config(invalid_yaml_path)
            self.assertTrue(any("Error parsing YAML configuration" in message for message in log.output))
        self.assertIsNotNone(config)
        self.assertEqual(len(config), 0)
        os.remove(invalid_yaml_path)

if __name__ == '__main__':
    unittest.main() 