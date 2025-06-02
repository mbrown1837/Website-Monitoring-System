import unittest
import os
import sys
import json
import csv
from io import StringIO
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src import report_generator

class TestReportGenerator(unittest.TestCase):

    def setUp(self):
        self.sample_check_record_single = {
            "check_id": "chk_single_123", "site_id": "site_abc", 
            "timestamp_utc": datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc).isoformat(),
            "status": "completed_with_changes", "significant_change_detected": True,
            "meta_changes": {"description": {"old": "Old", "new": "New"}},
            "link_changes": {"added": ["http://a.com"], "removed": []}
        }
        self.sample_check_records_list = [
            self.sample_check_record_single,
            {
                "check_id": "chk_multi_456", "site_id": "site_xyz", 
                "timestamp_utc": datetime(2023, 1, 2, 12, 30, 0, tzinfo=timezone.utc).isoformat(),
                "status": "completed_no_changes", "significant_change_detected": False,
                "content_diff_score": 0.99
            },
            {
                "check_id": "chk_multi_789", "site_id": "site_abc", 
                "timestamp_utc": datetime(2023, 1, 3, 15, 0, 0, tzinfo=timezone.utc).isoformat(),
                "status": "failed_fetch", "errors": "Timeout after 30s"
            }
        ]

    def test_generate_json_report_single_record(self):
        # Test with a single record (though the function expects a list for consistency now)
        json_output = report_generator.generate_json_report([self.sample_check_record_single])
        self.assertIsNotNone(json_output)
        try:
            data = json.loads(json_output)
            self.assertIsInstance(data, list)
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]['check_id'], "chk_single_123")
        except json.JSONDecodeError:
            self.fail("generate_json_report did not produce valid JSON for a single record list")

    def test_generate_json_report_multiple_records(self):
        json_output = report_generator.generate_json_report(self.sample_check_records_list)
        self.assertIsNotNone(json_output)
        try:
            data = json.loads(json_output)
            self.assertIsInstance(data, list)
            self.assertEqual(len(data), 3)
            self.assertEqual(data[0]['check_id'], "chk_single_123")
            self.assertEqual(data[1]['check_id'], "chk_multi_456")
        except json.JSONDecodeError:
            self.fail("generate_json_report did not produce valid JSON for multiple records")

    def test_generate_json_report_empty(self):
        json_output = report_generator.generate_json_report([])
        self.assertIsNotNone(json_output)
        try:
            data = json.loads(json_output)
            self.assertIsInstance(data, list)
            self.assertEqual(len(data), 0)
        except json.JSONDecodeError:
            self.fail("generate_json_report did not produce valid JSON for an empty list")

    def test_generate_csv_report_success(self):
        csv_output_string = report_generator.generate_csv_report(self.sample_check_records_list)
        self.assertIsNotNone(csv_output_string)
        
        # Use StringIO to simulate a file for csv.reader
        csv_file = StringIO(csv_output_string)
        reader = csv.reader(csv_file)
        rows = list(reader)

        self.assertEqual(len(rows), 4) # Header + 3 data rows
        self.assertIn("check_id", rows[0])
        self.assertIn("site_id", rows[0])
        self.assertIn("meta_changes", rows[0]) # Check complex field header

        # Check content of a row, including JSON serialized complex field
        # Finding the row for chk_single_123
        target_row = None
        for row in rows[1:]:
            if row[rows[0].index("check_id")] == "chk_single_123":
                target_row = row
                break
        self.assertIsNotNone(target_row, "Record chk_single_123 not found in CSV")
        
        self.assertEqual(target_row[rows[0].index("status")], "completed_with_changes")
        meta_changes_json = target_row[rows[0].index("meta_changes")]
        self.assertTrue(meta_changes_json.startswith('{')) # Check if it looks like JSON
        try:
            meta_data = json.loads(meta_changes_json)
            self.assertEqual(meta_data['description']['new'], "New")
        except json.JSONDecodeError:
            self.fail("CSV report did not correctly serialize complex field to JSON")

    def test_generate_csv_report_empty(self):
        csv_output_string = report_generator.generate_csv_report([])
        self.assertIsNotNone(csv_output_string)
        csv_file = StringIO(csv_output_string)
        reader = csv.reader(csv_file)
        rows = list(reader)
        self.assertEqual(len(rows), 1) # Only header row
        self.assertGreater(len(rows[0]), 0) # Header should not be empty

    def test_generate_csv_report_defined_headers(self):
        # Test if specific headers are present
        csv_output_string = report_generator.generate_csv_report(self.sample_check_records_list)
        csv_file = StringIO(csv_output_string)
        reader = csv.reader(csv_file)
        header_row = next(reader)

        expected_headers = [
            "check_id", "site_id", "timestamp_utc", "status",
            "html_snapshot_path", "html_content_hash", "visual_snapshot_path",
            "fetch_status_code", "content_diff_score", "structure_diff_score",
            "visual_diff_score", "visual_diff_image_path", "meta_changes",
            "link_changes", "image_src_changes", "canonical_url_change",
            "significant_change_detected", "errors"
        ]
        for h in expected_headers:
            self.assertIn(h, header_row)

if __name__ == '__main__':
    unittest.main() 