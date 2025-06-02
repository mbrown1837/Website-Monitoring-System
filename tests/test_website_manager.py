import unittest
import os
import sys
import json
import shutil # For copying files

# Add project root to sys.path to allow importing src modules
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src import website_manager
from src.config_loader import _config_cache # To clear config cache if needed

class TestWebsiteManager(unittest.TestCase):

    def setUp(self):
        """Set up for test methods."""
        _config_cache.clear() # Ensure config is fresh if it affects website_manager
        self.test_data_dir = os.path.join(PROJECT_ROOT, 'tests', 'temp_data')
        os.makedirs(self.test_data_dir, exist_ok=True)
        self.test_websites_file = os.path.join(self.test_data_dir, 'test_websites.json')

        # Override the default websites file path for testing
        website_manager.WEBSITES_FILE_PATH = self.test_websites_file
        
        # Ensure the test file is empty before each test
        if os.path.exists(self.test_websites_file):
            os.remove(self.test_websites_file)
        with open(self.test_websites_file, 'w') as f:
            json.dump([], f)
        website_manager._load_websites(force_reload=True) # Load the empty list into the manager, forcing reload

    def tearDown(self):
        """Clean up after test methods."""
        if os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir)
        # Reset to default path (important if other tests use website_manager)
        website_manager.WEBSITES_FILE_PATH = os.path.join(PROJECT_ROOT, 'data', 'websites.json')
        _config_cache.clear()

    def test_add_website_success(self):
        site = website_manager.add_website("http://example.com", "Example", 24, True, ["test"])
        self.assertIsNotNone(site)
        self.assertEqual(site['url'], "http://example.com")
        self.assertEqual(site['name'], "Example")
        self.assertEqual(len(website_manager.list_websites()), 1)

    def test_add_website_duplicate_url(self):
        website_manager.add_website("http://example.com", "Example1")
        site2 = website_manager.add_website("http://example.com", "Example2")
        self.assertIsNone(site2) # Should not add duplicate URL
        self.assertEqual(len(website_manager.list_websites()), 1)

    def test_add_website_invalid_url(self):
        site = website_manager.add_website("", "Empty URL Site") # Empty URL
        self.assertIsNone(site)
        site_none = website_manager.add_website(None, "None URL Site") # None URL
        self.assertIsNone(site_none)
        self.assertEqual(len(website_manager.list_websites()), 0)

    def test_list_websites(self):
        website_manager.add_website("http://site1.com", "Site1", is_active=True)
        website_manager.add_website("http://site2.com", "Site2", is_active=False)
        website_manager.add_website("http://site3.com", "Site3", is_active=True)
        
        all_sites = website_manager.list_websites()
        self.assertEqual(len(all_sites), 3)
        
        active_sites = website_manager.list_websites(active_only=True)
        self.assertEqual(len(active_sites), 2)
        self.assertTrue(all(s['is_active'] for s in active_sites))

    def test_get_website_by_id_and_url(self):
        added_site = website_manager.add_website("http://getme.com", "GetMe")
        self.assertIsNotNone(added_site)
        site_id = added_site['id']

        found_by_id = website_manager.get_website_by_id(site_id)
        self.assertIsNotNone(found_by_id)
        self.assertEqual(found_by_id['url'], "http://getme.com")

        found_by_url = website_manager.get_website_by_url("http://getme.com")
        self.assertIsNotNone(found_by_url)
        self.assertEqual(found_by_url['id'], site_id)

        self.assertIsNone(website_manager.get_website_by_id("nonexistentid"))
        self.assertIsNone(website_manager.get_website_by_url("http://nonexistent.com"))

    def test_update_website_success(self):
        site = website_manager.add_website("http://update.com", "Original Name")
        site_id = site['id']
        updates = {"name": "Updated Name", "monitoring_interval_hours": 12, "is_active": False, "tags": ["updated"]}
        updated_site = website_manager.update_website(site_id, updates)
        
        self.assertIsNotNone(updated_site)
        self.assertEqual(updated_site['name'], "Updated Name")
        self.assertEqual(updated_site['monitoring_interval_hours'], 12)
        self.assertFalse(updated_site['is_active'])
        self.assertEqual(updated_site['tags'], ["updated"])

        # Check persistence
        reloaded_site = website_manager.get_website_by_id(site_id)
        self.assertEqual(reloaded_site['name'], "Updated Name")

    def test_update_website_url_conflict(self):
        site1 = website_manager.add_website("http://url1.com", "URL1")
        site2 = website_manager.add_website("http://url2.com", "URL2") # Existing URL for conflict
        
        # Try to update site1's URL to site2's URL
        updated_site = website_manager.update_website(site1['id'], {"url": "http://url2.com"})
        self.assertIsNone(updated_site) # Should fail due to URL conflict

        # Ensure original site1 URL is unchanged
        reloaded_site1 = website_manager.get_website_by_id(site1['id'])
        self.assertEqual(reloaded_site1['url'], "http://url1.com")

    def test_update_website_not_found(self):
        updated_site = website_manager.update_website("nonexistentid", {"name": "New Name"})
        self.assertIsNone(updated_site)

    def test_remove_website_success(self):
        site = website_manager.add_website("http://remove.com", "RemoveMe")
        site_id = site['id']
        self.assertEqual(len(website_manager.list_websites()), 1)
        
        removed = website_manager.remove_website(site_id)
        self.assertTrue(removed)
        self.assertEqual(len(website_manager.list_websites()), 0)
        self.assertIsNone(website_manager.get_website_by_id(site_id))

    def test_remove_website_not_found(self):
        removed = website_manager.remove_website("nonexistentid")
        self.assertFalse(removed)

if __name__ == '__main__':
    unittest.main() 