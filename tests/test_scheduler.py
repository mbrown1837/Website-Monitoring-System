import unittest
from unittest.mock import patch, MagicMock
import os
import sys
from datetime import datetime, timezone

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src import scheduler
from src.config_loader import _config_cache, get_config # To reset config

class TestSchedulerLogic(unittest.TestCase):

    def setUp(self):
        _config_cache.clear() # Clear config cache before each test
        self.test_site_config = {
            "id": "test_site_001",
            "url": "http://example.com",
            "name": "Test Example Site",
        }
        # Mock configuration values used by the scheduler functions
        self.mock_config_values = {
            'content_change_threshold': 0.90,
            'structure_change_threshold': 0.95,
            'visual_difference_threshold': 0.10,
            'meta_tags_to_check': ['description', 'keywords'],
            # Default SMTP settings for alerter, assuming alerter is called
            'notification_email_from': 'test@example.com',
            'notification_email_to': ['recv@example.com'],
            'smtp_server': 'localhost',
            'smtp_port': 1025 
        }
        # Patch get_config used within scheduler and its dependencies
        self.get_config_patcher = patch('src.scheduler.get_config', return_value=self.mock_config_values)
        self.mock_get_config = self.get_config_patcher.start()
        scheduler.config = self.mock_config_values # Directly patch module level config

        # Patch all external dependencies of perform_website_check
        patch_prefix = 'src.scheduler' # Prefix for patching modules imported by scheduler
        self.mock_fetch = patch(f'{patch_prefix}.content_retriever.fetch_website_content').start()
        self.mock_save_html = patch(f'{patch_prefix}.snapshot_tool.save_html_snapshot').start()
        self.mock_save_visual = patch(f'{patch_prefix}.snapshot_tool.save_visual_snapshot').start()
        self.mock_compare_content = patch(f'{patch_prefix}.comparators.compare_html_content_similarity').start()
        self.mock_detect_layout = patch(f'{patch_prefix}.comparators.detect_layout_changes').start()
        self.mock_detect_tech = patch(f'{patch_prefix}.comparators.detect_technical_element_changes').start()
        self.mock_detect_media = patch(f'{patch_prefix}.comparators.detect_media_changes').start()
        self.mock_compare_visual = patch(f'{patch_prefix}.comparators.compare_visual_snapshots').start()
        self.mock_get_latest_history = patch(f'{patch_prefix}.history_manager.get_latest_check_for_site').start()
        self.mock_add_history = patch(f'{patch_prefix}.history_manager.add_check_record').start()
        self.mock_format_alert = patch(f'{patch_prefix}.alerter.format_alert_message').start()
        self.mock_send_alert = patch(f'{patch_prefix}.alerter.send_email_alert').start()
        self.mock_bs = patch(f'{patch_prefix}.BeautifulSoup').start() # Mock BeautifulSoup constructor

        # Default return values for mocks
        self.mock_fetch.return_value = (200, 'text/html', '<html></html>', None)
        self.mock_save_html.return_value = ('path/to.html', 'hash123')
        self.mock_save_visual.return_value = 'path/to.png'
        self.mock_get_latest_history.return_value = None
        self.mock_compare_content.return_value = 1.0
        self.mock_detect_layout.return_value = 1.0
        self.mock_detect_tech.return_value = {'meta_changes': {}, 'link_changes': {'added':[],'removed':[]}, 'canonical_url_change': None}
        self.mock_detect_media.return_value = {'added_images':[], 'removed_images':[], 'changed_images': []}
        self.mock_compare_visual.return_value = (0.0, None)
        self.mock_format_alert.return_value = ("Subj", "HTML", "Text")

    def tearDown(self):
        patch.stopall() # Stops all patches started with start()
        _config_cache.clear()
        scheduler.config = get_config() # Reset module config

    def test_perform_check_initial_run(self):
        scheduler.perform_website_check(self.test_site_config)
        self.mock_fetch.assert_called_once_with(self.test_site_config['url'])
        self.mock_save_html.assert_called_once()
        self.mock_save_visual.assert_called_once()
        self.mock_get_latest_history.assert_called_once_with(self.test_site_config['id'])
        self.mock_add_history.assert_called_once()
        self.assertEqual(self.mock_add_history.call_args.kwargs['status'], 'initial_check')
        self.mock_compare_content.assert_not_called()
        self.mock_send_alert.assert_not_called()

    def test_perform_check_content_change_triggers_alert(self):
        self.mock_get_latest_history.return_value = {'html_content_hash': 'old_hash', 'visual_snapshot_path': 'old.png', 'html_snapshot_path': 'old.html'}
        self.mock_save_html.return_value = ('new.html', 'new_hash') # Different hash
        self.mock_compare_content.return_value = 0.5 # Significant change

        scheduler.perform_website_check(self.test_site_config)
        self.mock_compare_content.assert_called_once()
        self.mock_send_alert.assert_called_once()
        self.assertTrue(self.mock_add_history.call_args.kwargs['significant_change_detected'])
        self.assertEqual(self.mock_add_history.call_args.kwargs['status'], 'completed_with_changes')

    def test_perform_check_visual_change_triggers_alert(self):
        self.mock_get_latest_history.return_value = {'html_content_hash': 'hash123', 'visual_snapshot_path': 'old.png', 'html_snapshot_path': 'old.html'}
        # HTML hash is the same as self.mock_save_html default, so no content diff path
        self.mock_compare_visual.return_value = (0.2, 'diff.png') # Significant visual change
        
        scheduler.perform_website_check(self.test_site_config)
        self.mock_compare_content.assert_not_called() # Hash matched
        self.mock_compare_visual.assert_called_once()
        self.mock_send_alert.assert_called_once()
        self.assertTrue(self.mock_add_history.call_args.kwargs['significant_change_detected'])

    def test_perform_check_fetch_failure(self):
        self.mock_fetch.return_value = (None, None, None, "Fetch Error")
        scheduler.perform_website_check(self.test_site_config)
        self.mock_save_html.assert_not_called()
        self.mock_add_history.assert_called_once()
        self.assertEqual(self.mock_add_history.call_args.kwargs['status'], 'failed_fetch')
        self.assertEqual(self.mock_add_history.call_args.kwargs['errors'], 'Fetch Error')
        self.mock_send_alert.assert_not_called()

    def test_determine_significance_various_cases(self):
        cfg = self.mock_config_values
        # Content
        is_sig, _ = scheduler.determine_significance({'content_diff_score': cfg['content_change_threshold'] - 0.1})
        self.assertTrue(is_sig)
        # Structure
        is_sig, _ = scheduler.determine_significance({'structure_diff_score': cfg['structure_change_threshold'] - 0.1})
        self.assertTrue(is_sig)
        # Visual
        is_sig, _ = scheduler.determine_significance({'visual_diff_score': cfg['visual_difference_threshold'] + 0.1})
        self.assertTrue(is_sig)
        # Meta
        is_sig, _ = scheduler.determine_significance({'meta_changes': {'description': {'old':'a','new':'b'}}})
        self.assertTrue(is_sig)
        # No change
        is_sig, _ = scheduler.determine_significance({
            'content_diff_score': 1.0, 'structure_diff_score': 1.0, 'visual_diff_score': 0.0,
            'meta_changes': {}, 'link_changes': {'added':[],'removed':[]}, 
            'image_src_changes': {'added_images':[],'removed_images':[]}, 'canonical_url_change': None
        })
        self.assertFalse(is_sig)

if __name__ == '__main__':
    unittest.main() 