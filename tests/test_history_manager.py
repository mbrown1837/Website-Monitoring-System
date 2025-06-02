import unittest
import os
import sys
import json
import shutil
from datetime import datetime, timezone, timedelta

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src import history_manager
from src.config_loader import _config_cache

class TestHistoryManager(unittest.TestCase):

    def setUp(self):
        _config_cache.clear()
        self.test_data_dir = os.path.join(PROJECT_ROOT, 'tests', 'temp_data')
        os.makedirs(self.test_data_dir, exist_ok=True)
        self.test_history_file = os.path.join(self.test_data_dir, 'test_check_history.json')

        history_manager.HISTORY_FILE_PATH = self.test_history_file
        
        if os.path.exists(self.test_history_file):
            os.remove(self.test_history_file)
        with open(self.test_history_file, 'w') as f:
            json.dump([], f)
        history_manager._load_history(force_reload=True)

    def tearDown(self):
        if os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir)
        history_manager.HISTORY_FILE_PATH = os.path.join(PROJECT_ROOT, 'data', 'check_history.json')
        _config_cache.clear()

    def _create_sample_record_data(self, site_id, timestamp_offset_days=0, status="completed"):
        ts = datetime.now(timezone.utc) - timedelta(days=timestamp_offset_days)
        return {
            "site_id": site_id,
            "status": status,
            "timestamp_utc": ts.isoformat(), # Will be overridden by add_check_record
            "html_snapshot_path": f"/snapshots/{site_id}/html/{ts.strftime('%Y%m%d_%H%M%S')}.html",
            "html_content_hash": f"hash_{site_id}_{ts.timestamp()}",
            "significant_change_detected": (status == "completed_with_changes")
        }

    def test_add_check_record(self):
        record_data = self._create_sample_record_data("site1")
        added_record = history_manager.add_check_record(**record_data)
        self.assertIsNotNone(added_record)
        self.assertEqual(added_record['site_id'], "site1")
        self.assertEqual(added_record['status'], record_data['status'])
        self.assertIn('check_id', added_record)
        self.assertIn('timestamp_utc', added_record) # Ensure new timestamp is added

        history = history_manager._load_history(force_reload=True)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['check_id'], added_record['check_id'])

    def test_get_check_history_for_site(self):
        history_manager.add_check_record(**self._create_sample_record_data("site1", timestamp_offset_days=2, status="initial_check"))
        r2 = history_manager.add_check_record(**self._create_sample_record_data("site1", timestamp_offset_days=1, status="completed_no_changes"))
        r3 = history_manager.add_check_record(**self._create_sample_record_data("site1", timestamp_offset_days=0, status="completed_with_changes"))
        history_manager.add_check_record(**self._create_sample_record_data("site2", timestamp_offset_days=0, status="completed")) # Different site

        site1_history = history_manager.get_check_history_for_site("site1")
        self.assertEqual(len(site1_history), 3)
        self.assertEqual(site1_history[0]['check_id'], r3['check_id']) # Most recent first
        self.assertEqual(site1_history[1]['check_id'], r2['check_id'])

        site1_history_limit_1 = history_manager.get_check_history_for_site("site1", limit=1)
        self.assertEqual(len(site1_history_limit_1), 1)
        self.assertEqual(site1_history_limit_1[0]['check_id'], r3['check_id'])

        site1_history_limit_0 = history_manager.get_check_history_for_site("site1", limit=0)
        self.assertEqual(len(site1_history_limit_0), 3)

        non_existent_history = history_manager.get_check_history_for_site("nonexistent_site")
        self.assertEqual(len(non_existent_history), 0)

    def test_get_latest_check_for_site(self):
        history_manager.add_check_record(**self._create_sample_record_data("site1", timestamp_offset_days=2))
        latest_added = history_manager.add_check_record(**self._create_sample_record_data("site1", timestamp_offset_days=1))
        history_manager.add_check_record(**self._create_sample_record_data("site2", timestamp_offset_days=0))

        latest_site1 = history_manager.get_latest_check_for_site("site1")
        self.assertIsNotNone(latest_site1)
        self.assertEqual(latest_site1['check_id'], latest_added['check_id'])

        latest_nonexistent = history_manager.get_latest_check_for_site("nonexistent_site")
        self.assertIsNone(latest_nonexistent)

    def test_empty_history_file(self):
        # setUp creates an empty file already
        history = history_manager.get_check_history_for_site("any_site")
        self.assertEqual(len(history), 0)
        latest = history_manager.get_latest_check_for_site("any_site")
        self.assertIsNone(latest)

if __name__ == '__main__':
    unittest.main() 