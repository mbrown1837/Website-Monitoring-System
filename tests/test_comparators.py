import unittest
from unittest.mock import patch, MagicMock
import os
import sys
from bs4 import BeautifulSoup
from PIL import Image, ImageChops
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src import comparators
from src.config_loader import _config_cache, get_config

# Helper to create a simple PIL Image for testing
def create_test_image(width, height, color=(0,0,0)):
    return Image.new('RGB', (width, height), color)

class TestComparators(unittest.TestCase):

    def setUp(self):
        _config_cache.clear()
        # Basic config, individual tests can override if comparator uses config
        self.test_config = {
            'meta_tags_to_check': ['description', 'keywords', 'title'],
            'snapshot_directory': '/tmp/test_snapshots' # For diff image saving in visual compare
        }
        self.get_config_patcher = patch('src.comparators.get_config', return_value=self.test_config)
        self.mock_get_config = self.get_config_patcher.start()
        comparators.config = self.test_config

        self.html_doc1 = """
        <html><head><title>Test Doc 1</title><meta name=\"description\" content=\"Original description\"></head>
        <body><p>This is paragraph one.</p><img src=\"image1.jpg\"><a href=\"/page1\">Link 1</a></body></html>
        """
        self.html_doc2_similar = """
        <html><head><title>Test Doc 1 Similar</title><meta name=\"description\" content=\"Original description slightly changed\"></head>
        <body><p>This is paragraph one, slightly modified.</p><img src=\"image1_updated.jpg\"><a href=\"/page2\">Link 2</a></body></html>
        """
        self.html_doc3_very_different = """
        <html><head><title>Totally Different</title></head>
        <body><div>Totally different content</div><img src=\"new_image.png\"><a href=\"/somewhere_else\">Other Link</a></body></html>
        """
        self.soup1 = BeautifulSoup(self.html_doc1, 'html.parser')
        self.soup2_similar = BeautifulSoup(self.html_doc2_similar, 'html.parser')
        self.soup3_very_different = BeautifulSoup(self.html_doc3_very_different, 'html.parser')

    def tearDown(self):
        self.get_config_patcher.stop()
        _config_cache.clear()
        comparators.config = get_config()

    def test_compare_html_content_similarity(self):
        # Identical
        score_identical = comparators.compare_html_content_similarity(self.soup1, self.soup1)
        self.assertEqual(score_identical, 1.0)
        # Similar
        score_similar = comparators.compare_html_content_similarity(self.soup1, self.soup2_similar)
        self.assertTrue(0.5 < score_similar < 1.0)
        # Different
        score_different = comparators.compare_html_content_similarity(self.soup1, self.soup3_very_different)
        self.assertTrue(0.0 <= score_different < 0.5)

    def test_detect_layout_changes(self):
        # Identical structure (ignoring text)
        struct_score_identical = comparators.detect_layout_changes(self.soup1, self.soup1)
        self.assertEqual(struct_score_identical, 1.0)

        # Slightly different structure (e.g. a new div)
        html_doc1_plus_div = self.html_doc1.replace("</body>", "<div>New Div</div></body>")
        soup1_plus_div = BeautifulSoup(html_doc1_plus_div, 'html.parser')
        struct_score_minor_change = comparators.detect_layout_changes(self.soup1, soup1_plus_div)
        self.assertTrue(0.8 < struct_score_minor_change < 1.0) # Expect high similarity

        # Very different structure
        struct_score_different = comparators.detect_layout_changes(self.soup1, self.soup3_very_different)
        self.assertTrue(0.0 <= struct_score_different < 0.5)

    def test_detect_technical_element_changes(self):
        changes1_vs_1 = comparators.detect_technical_element_changes(self.soup1, self.soup1)
        self.assertEqual(len(changes1_vs_1['meta_changes']), 0)
        self.assertEqual(len(changes1_vs_1['link_changes']['added']), 0)
        self.assertIsNone(changes1_vs_1['canonical_url_change'])

        changes1_vs_2 = comparators.detect_technical_element_changes(self.soup1, self.soup2_similar)
        self.assertIn('description', changes1_vs_2['meta_changes'])
        self.assertEqual(changes1_vs_2['meta_changes']['description']['old'], "Original description")
        self.assertEqual(changes1_vs_2['link_changes']['added'][0], "/page2")
        self.assertEqual(changes1_vs_2['link_changes']['removed'][0], "/page1")

        # Test canonical (add them to soup)
        soup1_canon = BeautifulSoup('<head><link rel="canonical" href="http://example.com/page1"></head>', 'html.parser')
        soup2_canon_changed = BeautifulSoup('<head><link rel="canonical" href="http://example.com/page2"></head>', 'html.parser')
        changes_canon = comparators.detect_technical_element_changes(soup1_canon, soup2_canon_changed)
        self.assertIsNotNone(changes_canon['canonical_url_change'])
        self.assertEqual(changes_canon['canonical_url_change']['old'], "http://example.com/page1")
        self.assertEqual(changes_canon['canonical_url_change']['new'], "http://example.com/page2")

    def test_detect_media_changes(self):
        changes1_vs_1 = comparators.detect_media_changes(self.soup1, self.soup1)
        self.assertEqual(len(changes1_vs_1['added_images']), 0)
        self.assertEqual(len(changes1_vs_1['removed_images']), 0)
        self.assertEqual(len(changes1_vs_1['changed_images']), 0)

        changes1_vs_2 = comparators.detect_media_changes(self.soup1, self.soup2_similar)
        self.assertIn("image1_updated.jpg", changes1_vs_2['added_images'])
        self.assertIn("image1.jpg", changes1_vs_2['removed_images'])

    @patch('src.comparators.Image.open')
    @patch('src.comparators.os.path.exists', return_value=True)
    @patch('src.comparators.os.makedirs') # To mock diff image saving directory creation
    def test_compare_visual_snapshots_identical(self, mock_makedirs, mock_exists, mock_image_open):
        img1 = create_test_image(100, 100, (255,0,0)) # Red image
        mock_image_open.side_effect = [img1, img1]

        mse, diff_path = comparators.compare_visual_snapshots("site1", "path/to/img1.png", "path/to/img1_again.png", "ts1")
        self.assertEqual(mse, 0.0)
        self.assertIsNone(diff_path) # No diff image for identical images
        mock_makedirs.assert_not_called()

    @patch('src.comparators.Image.open')
    @patch('src.comparators.os.path.exists', return_value=True)
    @patch('src.comparators.os.makedirs')
    @patch('src.comparators.ImageChops.difference') # Mock the difference calculation
    @patch('src.comparators.Image.Image.save') # Mock saving the diff image
    def test_compare_visual_snapshots_different(self, mock_img_save, mock_img_diff, mock_makedirs, mock_exists, mock_image_open):
        img1 = create_test_image(100, 100, (255,0,0)) # Red
        img2 = create_test_image(100, 100, (0,255,0)) # Green
        mock_image_open.side_effect = [img1, img2]

        # Mock ImageChops.difference to return a non-black image
        diff_image_mock = create_test_image(100, 100, (10,10,10)) # Simulate some difference
        mock_img_diff.return_value = diff_image_mock

        expected_diff_dir = os.path.join(self.test_config['snapshot_directory'], "site1", "diff")
        expected_diff_filename = f"site1_ts1_diff.png"
        expected_diff_filepath = os.path.join(expected_diff_dir, expected_diff_filename)

        mse, diff_path = comparators.compare_visual_snapshots("site1", "path/to/img1.png", "path/to/img2.png", "ts1", save_diff_image=True)
        self.assertGreater(mse, 0.0)
        self.assertEqual(diff_path, expected_diff_filepath)
        mock_makedirs.assert_called_once_with(expected_diff_dir, exist_ok=True)
        mock_img_save.assert_called_once_with(expected_diff_filepath)

    def test_compare_visual_snapshots_file_not_found(self):
        with patch('src.comparators.os.path.exists', return_value=False):
            mse, diff_path = comparators.compare_visual_snapshots("site1", "nonexistent1.png", "nonexistent2.png", "ts1")
            self.assertIsNone(mse)
            self.assertIsNone(diff_path)

    def test_compare_visual_snapshots_image_load_error(self):
        with patch('src.comparators.os.path.exists', return_value=True):
            with patch('src.comparators.Image.open', side_effect=IOError("Cannot load image")):
                mse, diff_path = comparators.compare_visual_snapshots("site1", "img1.png", "img2.png", "ts1")
                self.assertIsNone(mse)
                self.assertIsNone(diff_path)

if __name__ == '__main__':
    unittest.main() 