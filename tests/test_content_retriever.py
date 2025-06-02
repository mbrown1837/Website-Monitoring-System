import unittest
from unittest.mock import patch, MagicMock, call
import os
import sys
import requests # For actual RequestException, Timeout, HTTPError

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src import content_retriever
from src.config_loader import _config_cache, get_config

class TestContentRetriever(unittest.TestCase):

    def setUp(self):
        _config_cache.clear()
        self.test_url = "http://test-site.com"
        self.default_user_agent = content_retriever.DEFAULT_USER_AGENT
        self.default_timeout = content_retriever.DEFAULT_TIMEOUT_SECONDS

        # Default config for retries, can be overridden per test
        self.base_retry_config = {
            'fetch_retry_total': 2, # Lower for faster tests
            'fetch_retry_backoff_factor': 0.1,
            'fetch_retry_status_forcelist': [500, 502]
        }
        self.get_config_patcher = patch('src.content_retriever.get_config', return_value=self.base_retry_config)
        self.mock_get_config = self.get_config_patcher.start()
        content_retriever.config = self.base_retry_config
        
        # Patch the requests.Session class itself to control its instances
        self.session_patcher = patch('requests.Session', autospec=True)
        self.MockSession = self.session_patcher.start()
        self.mock_session_instance = self.MockSession.return_value

    def tearDown(self):
        self.get_config_patcher.stop()
        self.session_patcher.stop()
        _config_cache.clear()
        content_retriever.config = get_config() # Reset

    def test_fetch_success_first_try(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>Success</html>"
        mock_response.headers = {'Content-Type': 'text/html'}
        self.mock_session_instance.get.return_value = mock_response

        status, c_type, html, error = content_retriever.fetch_website_content(self.test_url)

        self.assertEqual(status, 200)
        self.assertEqual(c_type, 'text/html')
        self.assertEqual(html, "<html>Success</html>")
        self.assertIsNone(error)
        self.mock_session_instance.get.assert_called_once_with(
            self.test_url, headers={"User-Agent": self.default_user_agent}, 
            timeout=self.default_timeout, allow_redirects=True
        )
        mock_response.raise_for_status.assert_called_once()

    def test_fetch_retry_on_status_code_then_success(self):
        mock_response_fail = MagicMock()
        mock_response_fail.status_code = 500
        mock_response_fail.reason = "Internal Server Error"
        mock_response_fail.headers = {'Content-Type': 'text/plain'}
        mock_response_fail.text = "Server Error"
        # Configure raise_for_status to be called and raise HTTPError for specific calls
        http_error = requests.exceptions.HTTPError(response=mock_response_fail)
        mock_response_fail.raise_for_status.side_effect = http_error

        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.text = "<html>Retry Success</html>"
        mock_response_success.headers = {'Content-Type': 'text/html'}
        mock_response_success.raise_for_status.return_value = None # No error on success

        self.mock_session_instance.get.side_effect = [mock_response_fail, mock_response_success]

        status, c_type, html, error = content_retriever.fetch_website_content(self.test_url)

        self.assertEqual(status, 200)
        self.assertEqual(html, "<html>Retry Success</html>")
        self.assertIsNone(error)
        self.assertEqual(self.mock_session_instance.get.call_count, 2)
        # raise_for_status should be called for both attempts
        self.assertEqual(mock_response_fail.raise_for_status.call_count, 1) 
        self.assertEqual(mock_response_success.raise_for_status.call_count, 1)

    def test_fetch_all_retries_fail_on_status_code(self):
        mock_response_fail = MagicMock()
        mock_response_fail.status_code = 502
        mock_response_fail.reason = "Bad Gateway"
        mock_response_fail.headers = {'Content-Type': 'text/html'}
        mock_response_fail.text = "Gateway Error Page"
        http_error = requests.exceptions.HTTPError(response=mock_response_fail)
        mock_response_fail.raise_for_status.side_effect = http_error

        # Total retries is 2 from config, so 3 attempts total
        self.mock_session_instance.get.side_effect = [mock_response_fail, mock_response_fail, mock_response_fail]

        status, c_type, html, error = content_retriever.fetch_website_content(self.test_url)

        self.assertEqual(status, 502)
        self.assertEqual(c_type, 'text/html')
        self.assertEqual(html, "Gateway Error Page") # Should return content of last error page
        self.assertIn("HTTP error occurred after retries: 502 Bad Gateway", error)
        self.assertEqual(self.mock_session_instance.get.call_count, 3) # Initial + 2 retries

    def test_fetch_timeout_all_attempts(self):
        self.mock_session_instance.get.side_effect = requests.exceptions.Timeout("Connection timed out")
        
        # Configure total retries to 1 for this test (so 2 attempts)
        retry_config = self.base_retry_config.copy()
        retry_config['fetch_retry_total'] = 1 
        self.mock_get_config.return_value = retry_config
        content_retriever.config = retry_config
        # Re-patch session because _get_retry_session uses the module-level config at definition time
        # This is a bit tricky. A better design might pass config explicitly or use a class for ContentRetriever.
        # For now, re-patching the session creation to use the updated retry count.
        # We need to reinstantiate the patcher to capture the new session behavior.
        self.session_patcher.stop() 
        self.MockSession = self.session_patcher.start()
        self.mock_session_instance = self.MockSession.return_value
        self.mock_session_instance.get.side_effect = requests.exceptions.Timeout("Connection timed out")

        status, c_type, html, error = content_retriever.fetch_website_content(self.test_url)

        self.assertIsNone(status)
        self.assertIsNone(html)
        self.assertIn(f"Request timed out after {self.default_timeout} seconds (and potential retries)", error)
        self.assertEqual(self.mock_session_instance.get.call_count, 2) # Initial + 1 retry

    def test_fetch_non_retryable_http_error(self):
        mock_response_404 = MagicMock()
        mock_response_404.status_code = 404
        mock_response_404.reason = "Not Found"
        mock_response_404.headers = {'Content-Type':'text/html'}
        mock_response_404.text = "Not Found Page"
        http_error = requests.exceptions.HTTPError(response=mock_response_404)
        mock_response_404.raise_for_status.side_effect = http_error

        self.mock_session_instance.get.return_value = mock_response_404

        status, c_type, html, error = content_retriever.fetch_website_content(self.test_url)

        self.assertEqual(status, 404)
        self.assertEqual(html, "Not Found Page")
        self.assertIn("HTTP error occurred after retries: 404 Not Found", error) # Even if no retries for 404, message says "after retries"
        self.mock_session_instance.get.assert_called_once() # No retry for 404 by default

    def test_fetch_connection_error(self):
        # ConnectionError should be retried by default by urllib3 Retry
        self.mock_session_instance.get.side_effect = requests.exceptions.ConnectionError("Failed to connect")
        
        status, c_type, html, error = content_retriever.fetch_website_content(self.test_url)

        self.assertIsNone(status)
        self.assertIsNone(html)
        self.assertIn("An error occurred during request (after retries)", error)
        self.assertIn("Failed to connect", error)
        # Total retries = 2 from config => 3 attempts
        self.assertEqual(self.mock_session_instance.get.call_count, 3)

if __name__ == '__main__':
    unittest.main() 