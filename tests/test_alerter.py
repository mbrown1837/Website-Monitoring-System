import unittest
from unittest.mock import patch, MagicMock # For mocking smtplib
import os
import sys
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src import alerter
from src.config_loader import _config_cache, get_config

class TestAlerter(unittest.TestCase):

    def setUp(self):
        _config_cache.clear()
        # Ensure a minimal config for alerter
        self.test_config = {
            'notification_email_from': "monitor@example.com",
            'notification_email_to': ["websitecheckapp@digitalclics.com"],
            'smtp_server': "smtp.example.com",
            'smtp_port': 587,
            'smtp_username': "monitor_user",
            'smtp_password': "secret_password",
            'smtp_use_tls': True
        }
        # Patch get_config to return our test_config for alerter module
        self.get_config_patcher = patch('src.alerter.get_config', return_value=self.test_config)
        self.mock_get_config = self.get_config_patcher.start()
        alerter.config = self.test_config # Also directly set it as it might be loaded at module level

    def tearDown(self):
        self.get_config_patcher.stop()
        _config_cache.clear()
        # Reset alerter.config if it was globally patched in the module, to be safe
        # This requires alerter to have its config reloaded if used outside tests or by other tests.
        # A better way might be to instantiate Alerter class if it were a class.
        alerter.config = get_config() # Reset to original config loading behavior

    def test_format_alert_message_basic(self):
        check_record = {
            "check_id": "chk_123",
            "site_id": "site_abc",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "status": "completed_with_changes",
            "html_snapshot_path": "/path/to/html.html",
            "visual_snapshot_path": "/path/to/visual.png",
            "significant_change_detected": True,
            "content_diff_score": 0.85,
            "visual_diff_score": 0.15
        }
        subject, html_body, text_body = alerter.format_alert_message(
            site_url="http://example.com",
            site_name="Example Site",
            check_record=check_record
        )
        self.assertIn("[Website Monitor Alert] Significant Change Detected for Example Site", subject)
        self.assertIn("Example Site (http://example.com)", html_body)
        self.assertIn("Content Similarity: 0.85", html_body)
        self.assertIn("Visual Difference: 0.15", html_body)
        self.assertIn("Example Site (http://example.com)", text_body)
        self.assertIn("Content Similarity: 0.85", text_body)

    def test_format_alert_message_with_all_fields(self):
        now_iso = datetime.now(timezone.utc).isoformat()
        check_record = {
            "check_id": "chk_789", "site_id": "site_xyz", "timestamp_utc": now_iso,
            "status": "completed_with_changes", "significant_change_detected": True,
            "fetch_status_code": 200,
            "html_snapshot_path": "/snaps/site_xyz/html/1.html",
            "html_content_hash": "hash123",
            "visual_snapshot_path": "/snaps/site_xyz/visual/1.png",
            "visual_diff_image_path": "/snaps/site_xyz/diff/1.png",
            "content_diff_score": 0.75, "structure_diff_score": 0.80,
            "visual_diff_score": 0.25, 
            "meta_changes": {"description": {"old": "Old Desc", "new": "New Desc"}},
            "link_changes": {"added": ["http://new.com"], "removed": []},
            "image_src_changes": {"added_images": ["/new_img.jpg"], "removed_images": []},
            "canonical_url_change": {"old": "http://oldcanonical.com", "new": "http://newcanonical.com"}
        }
        subject, html_body, text_body = alerter.format_alert_message(
            site_url="http://test.com", site_name="Test Site", check_record=check_record
        )
        self.assertIn("Significant Change Detected for Test Site", subject)
        self.assertIn("http://test.com", html_body)
        self.assertIn("Description changed", html_body)
        self.assertIn("New links found: http://new.com", html_body)
        self.assertIn("New images found: /new_img.jpg", html_body)
        self.assertIn("Canonical URL changed from http://oldcanonical.com to http://newcanonical.com", html_body)
        self.assertIn("Visual Diff Image: /snaps/site_xyz/diff/1.png", html_body)

    @patch('smtplib.SMTP') # For general SMTP connection
    @patch('smtplib.SMTP_SSL') # For SSL connection
    def test_send_email_alert_success_tls(self, mock_smtp_ssl, mock_smtp):
        self.mock_get_config.return_value['smtp_use_tls'] = True
        alerter.config = self.mock_get_config.return_value # re-assign

        mock_server_tls = MagicMock()
        mock_smtp.return_value = mock_server_tls # When SMTP() is called

        alerter.send_email_alert("Test Subject", "<p>HTML Body</p>", "Text Body")

        mock_smtp.assert_called_once_with(self.test_config['smtp_server'], self.test_config['smtp_port'], timeout=alerter.SMTP_TIMEOUT)
        mock_server_tls.starttls.assert_called_once()
        mock_server_tls.login.assert_called_once_with(self.test_config['smtp_username'], self.test_config['smtp_password'])
        mock_server_tls.sendmail.assert_called_once()
        args, _ = mock_server_tls.sendmail.call_args
        self.assertEqual(args[0], self.test_config['notification_email_from'])
        self.assertEqual(args[1], self.test_config['notification_email_to'])
        self.assertIn("Subject: Test Subject", args[2])
        mock_server_tls.quit.assert_called_once()
        mock_smtp_ssl.assert_not_called() # Ensure SSL version not used

    @patch('smtplib.SMTP_SSL')
    @patch('smtplib.SMTP')
    def test_send_email_alert_success_ssl(self, mock_smtp, mock_smtp_ssl):
        self.mock_get_config.return_value['smtp_use_tls'] = False # Test SSL direct
        self.mock_get_config.return_value['smtp_port'] = 465 # Typical SSL port
        alerter.config = self.mock_get_config.return_value # re-assign

        mock_server_ssl = MagicMock()
        mock_smtp_ssl.return_value = mock_server_ssl # When SMTP_SSL() is called

        alerter.send_email_alert("SSL Test Subject", "<p>HTML SSL</p>", "Text SSL")

        mock_smtp_ssl.assert_called_once_with(self.test_config['smtp_server'], 465, timeout=alerter.SMTP_TIMEOUT)
        mock_server_ssl.login.assert_called_once_with(self.test_config['smtp_username'], self.test_config['smtp_password'])
        mock_server_ssl.sendmail.assert_called_once()
        mock_smtp.assert_not_called()
        mock_server_ssl.quit.assert_called_once()

    @patch('smtplib.SMTP')
    def test_send_email_alert_failure(self, mock_smtp):
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server
        mock_server.login.side_effect = Exception("SMTP Login Failed")

        # We expect this to log an error but not raise an exception itself
        with self.assertLogs(logger=alerter.logger, level='ERROR') as log_cm:
            alerter.send_email_alert("Fail Subject", "<p>HTML</p>", "Text")
        self.assertTrue(any("Failed to send email alert: SMTP Login Failed" in msg for msg in log_cm.output))

    def test_send_email_alert_no_config(self):
        # Test when essential SMTP config is missing
        self.mock_get_config.return_value = {'notification_email_to': ["test@example.com"]}
        alerter.config = self.mock_get_config.return_value
        
        with self.assertLogs(logger=alerter.logger, level='ERROR') as log_cm:
            alerter.send_email_alert("No Config Subject", "HTML", "Text")
        self.assertTrue(any("SMTP server, port, or sender not configured. Cannot send email." in msg for msg in log_cm.output))

if __name__ == '__main__':
    unittest.main() 