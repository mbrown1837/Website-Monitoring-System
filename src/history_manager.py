import json
import os
import uuid
from datetime import datetime, timezone
from src.config_loader import get_config
from src.logger_setup import setup_logging

class HistoryManager:
    def __init__(self, config_path=None):
        if config_path:
            self.config = get_config(config_path=config_path)
            self.logger = setup_logging(config_path=config_path)
        else:
            self.config = get_config()
            self.logger = setup_logging()
        
        self.history_file_path = self._initialize_history_file_path()
        self._history = []  # Internal cache
        self._history_loaded = False  # Flag for cache state
        self._load_history() # Initial load

    def _initialize_history_file_path(self):
        path = self.config.get('check_history_file_path', 'data/check_history.json')
        if not os.path.isabs(path):
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            path = os.path.join(project_root, path)
        
        directory = os.path.dirname(path)
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory, exist_ok=True)
                self.logger.info(f"Created directory for check history: {directory}")
            except OSError as e:
                self.logger.error(f"Error creating directory {directory} for check history: {e}")
                raise
        return path

    def _load_history(self, force_reload=False):
        if self._history_loaded and not force_reload:
            return self._history

        try:
            if not os.path.exists(self.history_file_path):
                self.logger.info(f"History file not found at {self.history_file_path}. Creating an empty list.")
                with open(self.history_file_path, 'w', encoding='utf-8') as f:
                    json.dump([], f)
                self._history = []
            else:
                with open(self.history_file_path, 'r', encoding='utf-8') as f:
                    self._history = json.load(f)
            self._history_loaded = True
            return self._history
        except (IOError, json.JSONDecodeError) as e:
            self.logger.error(f"Error loading check history from {self.history_file_path}: {e}")
            self._history = []
            self._history_loaded = True
            return self._history

    def _save_history(self):
        try:
            with open(self.history_file_path, 'w', encoding='utf-8') as f:
                json.dump(self._history, f, indent=2)
            self.logger.info(f"Successfully saved {len(self._history)} entries to check history: {self.history_file_path}")
        except IOError as e:
            self.logger.error(f"Error saving check history to {self.history_file_path}: {e}")

    def add_check_record(
        self,
        site_id: str,
        status: str, # e.g., "success", "error", "pending"
        html_snapshot_path: str | None = None,
        html_content_hash: str | None = None,
        visual_snapshot_path: str | None = None,
        # Catch all other keyword arguments for flexibility in what gets stored
        **details # Includes diff_scores, changed_elements, error_message, etc.
    ) -> dict:
        self._load_history() # Ensure history is current
        
        timestamp = datetime.now(timezone.utc)
        new_record = {
            "check_id": str(uuid.uuid4()),
            "site_id": site_id,
            "timestamp_utc": timestamp.isoformat(),
            "timestamp_readable": timestamp.strftime('%Y-%m-%d %H:%M:%S %Z').strip(), # For easier display
            "status": status,
            "html_snapshot_path": html_snapshot_path,
            "html_content_hash": html_content_hash,
            "visual_snapshot_path": visual_snapshot_path,
        }
        new_record.update(details) # Add all other passed details

        self._history.append(new_record)
        self._save_history()
        self.logger.info(f"Added new check record for site ID {site_id}. Check ID: {new_record['check_id']}")
        return new_record

    def get_history_for_site(self, site_id: str, limit: int = None) -> list[dict]:
        self._load_history() # Ensure history is current
        site_history = [record for record in self._history if record.get('site_id') == site_id]
        # Sort by timestamp_utc descending (most recent first)
        site_history.sort(key=lambda x: x.get('timestamp_utc', ''), reverse=True)
        
        if limit is not None and limit > 0:
            return site_history[:limit]
        # Allow limit=0 or limit=None to mean all records for that site.
        # For consistency with list_websites, perhaps limit=None should be the default for all.
        return site_history

    def get_latest_check_for_site(self, site_id: str, only_successful: bool = False) -> dict | None:
        self._load_history() # Ensure history is current
        site_history = [record for record in self._history if record.get('site_id') == site_id]
        if only_successful:
            site_history = [record for record in site_history if record.get('status') == 'success']
            
        if not site_history:
            return None
            
        site_history.sort(key=lambda x: x.get('timestamp_utc', ''), reverse=True)
        return site_history[0]

    def get_check_by_id(self, check_id: str) -> dict | None:
        """Retrieves a specific check record by its check_id."""
        self._load_history() # Ensure history is current
        for record in self._history:
            if record.get('check_id') == check_id:
                return record
        self.logger.debug(f"Check record with ID '{check_id}' not found.")
        return None

# Example Usage (for direct script execution testing)
if __name__ == '__main__':
    print("Running HistoryManager class directly for demonstration...")
    
    test_config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')

    # Clean up for demo
    demo_manager_for_path = HistoryManager(config_path=test_config_path)
    if os.path.exists(demo_manager_for_path.history_file_path):
        print(f"Removing existing demo history file: {demo_manager_for_path.history_file_path}")
        os.remove(demo_manager_for_path.history_file_path)

    manager = HistoryManager(config_path=test_config_path)
    manager._load_history(force_reload=True) # Ensure clean state for demo
    logger = manager.logger # Use the logger from the manager instance

    logger.info("----- HistoryManager Class Demo -----")

    test_site_id_1 = "site-history-demo-001"
    test_site_id_2 = "site-history-demo-002"

    # Add some records
    record1 = manager.add_check_record(
        site_id=test_site_id_1,
        status="success", # Changed from completed
        html_snapshot_path="data/snapshots/site-history-demo-001/html/dummy1.html",
        html_content_hash="hash1",
        visual_snapshot_path="data/snapshots/site-history-demo-001/visual/dummy1.png",
        diff_scores={"text_diff": 0.01, "visual_mse": 0.5},
        changes_detected=False
    )
    import time
    time.sleep(0.01) # Ensure distinct timestamps

    record2 = manager.add_check_record(
        site_id=test_site_id_1,
        status="success", # Changed from completed
        html_snapshot_path="data/snapshots/site-history-demo-001/html/dummy2.html",
        html_content_hash="hash2",
        visual_snapshot_path="data/snapshots/site-history-demo-001/visual/dummy2.png",
        diff_scores={"text_diff": 0.25, "structure_diff": 0.80, "visual_mse": 10.0},
        changed_elements={"meta_tags": [{"name": "description", "old": "old", "new": "new"}]},
        changes_detected=True
    )
    time.sleep(0.01)

    record3 = manager.add_check_record(
        site_id=test_site_id_2,
        status="error", # Changed from failed
        error_message="Could not connect to server."
    )

    history1 = manager.get_history_for_site(test_site_id_1)
    logger.info(f"History for {test_site_id_1} (most recent first):")
    for rec in history1:
        print(json.dumps(rec, indent=2))
    assert len(history1) == 2, "Should be 2 records for site 1"

    latest1 = manager.get_latest_check_for_site(test_site_id_1)
    logger.info(f"\nLatest check for {test_site_id_1}: {json.dumps(latest1, indent=2)}")
    assert latest1 and latest1['check_id'] == record2['check_id'], "Latest record for site 1 mismatch!"

    latest_success1 = manager.get_latest_check_for_site(test_site_id_1, only_successful=True)
    logger.info(f"\nLatest successful check for {test_site_id_1}: {json.dumps(latest_success1, indent=2)}")
    assert latest_success1 and latest_success1['check_id'] == record2['check_id'], "Latest successful for site 1 mismatch!"

    latest2 = manager.get_latest_check_for_site(test_site_id_2)
    logger.info(f"\nLatest check for {test_site_id_2}: {json.dumps(latest2, indent=2)}")
    assert latest2 and latest2['check_id'] == record3['check_id'], "Latest record for site 2 mismatch!"
    
    latest_success2 = manager.get_latest_check_for_site(test_site_id_2, only_successful=True)
    assert latest_success2 is None, "Should be None for latest successful for site 2 as it only has errors"
    logger.info(f"\nLatest successful check for {test_site_id_2}: {latest_success2}")

    latest_non_existent = manager.get_latest_check_for_site("non-existent-site-demo")
    assert latest_non_existent is None, "Should be None for non-existent site"
    logger.info(f"\nLatest check for non-existent-site-demo: {latest_non_existent}")

    logger.info("----- HistoryManager Class Demo Finished -----")
    print(f"Demo complete. Check history file: {manager.history_file_path}") 