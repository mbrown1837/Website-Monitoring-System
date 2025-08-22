import json
import os
import uuid
from datetime import datetime, timezone
import threading
from src.config_loader import get_config
from src.logger_setup import setup_logging
from .path_utils import resolve_path, clean_path_for_logging

class HistoryManager:
    def __init__(self, config_path=None):
        if config_path:
            self.config = get_config(config_path=config_path)
            self.logger = setup_logging(config_path=config_path)
        else:
            self.config = get_config()
            self.logger = setup_logging()
        
        self.lock = threading.Lock()
        self.history_file_path = self._initialize_history_file_path()
        self._history = []  # Internal cache
        self._history_loaded = False  # Flag for cache state
        self._load_history() # Initial load

    def _initialize_history_file_path(self):
        path = self.config.get('check_history_file_path', 'data/check_history.json')
        
        # Use environment-agnostic path resolution
        resolved_path = resolve_path(path)
        
        directory = os.path.dirname(resolved_path)
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory, exist_ok=True)
                self.logger.info(f"Created directory for check history: {clean_path_for_logging(directory)}")
            except OSError as e:
                self.logger.error(f"Error creating directory {clean_path_for_logging(directory)} for check history: {e}")
                raise
        return resolved_path

    def _load_history(self, force_reload=False):
        if self._history_loaded and not force_reload:
            return self._history

        with self.lock:
            try:
                if not os.path.exists(self.history_file_path):
                    self.logger.info(f"History file not found at {clean_path_for_logging(self.history_file_path)}. Creating an empty list.")
                    with open(self.history_file_path, 'w', encoding='utf-8') as f:
                        json.dump([], f)
                    self._history = []
                else:
                    with open(self.history_file_path, 'r', encoding='utf-8') as f:
                        self._history = json.load(f)
                self._history_loaded = True
                return self._history
            except (IOError, json.JSONDecodeError) as e:
                self.logger.error(f"Error loading check history from {clean_path_for_logging(self.history_file_path)}: {e}")
                self._history = []
                self._history_loaded = True
                return self._history

    def _save_history(self):
        with self.lock:
            try:
                with open(self.history_file_path, 'w', encoding='utf-8') as f:
                    json.dump(self._history, f, indent=2)
                self.logger.info(f"Successfully saved {len(self._history)} entries to check history: {clean_path_for_logging(self.history_file_path)}")
            except IOError as e:
                self.logger.error(f"Error saving check history to {clean_path_for_logging(self.history_file_path)}: {e}")

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
        
    def add_history_entry(self, website_id: str, check_result: dict) -> bool:
        """
        Add a new history entry for a website check.
        
        Args:
            website_id (str): The unique identifier for the website.
            check_result (dict): The result of the website check.
            
        Returns:
            bool: True if history was successfully updated, False otherwise.
        """
        if not website_id or not isinstance(check_result, dict):
            self.logger.error("Invalid parameters for add_history_entry")
            return False
        
        try:
            # Create a history entry from the check result
            entry = self._create_history_entry(website_id, check_result)
            
            # Get current website history
            current_history = self.get_history_for_site(website_id)
            if current_history is None:
                current_history = []
                
            # Make sure all paths in the history entry are properly formatted for web display
            entry = self._normalize_paths_for_web(entry)
                
            # Add new entry at the beginning of the history
            self._history.insert(0, entry)
            
            # Limit the number of entries for this site
            max_entries = self.config.get('max_history_entries_per_site', 100)
            site_entries = [record for record in self._history if record.get('site_id') == website_id]
            if len(site_entries) > max_entries:
                # Keep most recent max_entries for this site
                site_ids_to_keep = set(record['check_id'] for record in site_entries[:max_entries])
                # Filter the main history list
                self._history = [record for record in self._history 
                                if record.get('site_id') != website_id or record.get('check_id') in site_ids_to_keep]
            
            # Save history to file
            self._save_history()
            self.logger.info(f"Added history entry for website ID {website_id}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error adding history entry: {e}", exc_info=True)
            return False
            
    def _normalize_paths_for_web(self, entry: dict) -> dict:
        """
        Normalize file paths in history entry for web display.
        Ensures paths are relative to /data directory and use forward slashes.
        
        Args:
            entry (dict): The history entry to normalize
            
        Returns:
            dict: The updated history entry with normalized paths
        """
        try:
            # Helper function to normalize a single path
            def normalize_path(path):
                if not path:
                    return None
                    
                # Convert Windows backslashes to forward slashes
                path = path.replace("\\", "/")
                
                # Ensure path is relative to /data
                if path.startswith("data/"):
                    return path
                    
                # Check if it's an absolute path containing 'data/'
                if "data/" in path:
                    # Extract portion after 'data/'
                    path_parts = path.split("data/")
                    if len(path_parts) > 1:
                        return "data/" + path_parts[1]
                        
                return path
            
            # Normalize paths in baseline and current HTML/visual paths
            for path_key in ["visual_snapshot_path", "baseline_snapshot_path", 
                             "current_html_path", "baseline_html_path", "html_diff_path"]:
                if path_key in entry and entry[path_key]:
                    entry[path_key] = normalize_path(entry[path_key])
            
            # Handle crawler results visual baselines
            if "crawler_results" in entry and entry["crawler_results"]:
                if "visual_baselines" in entry["crawler_results"]:
                    for i, baseline in enumerate(entry["crawler_results"]["visual_baselines"]):
                        if "visual_path" in baseline:
                            entry["crawler_results"]["visual_baselines"][i]["visual_path"] = normalize_path(baseline["visual_path"])
            
            return entry
            
        except Exception as e:
            self.logger.error(f"Error normalizing paths: {e}", exc_info=True)
            return entry  # Return original entry if normalization fails
            
    def _create_history_entry(self, website_id: str, check_result: dict) -> dict:
        """Create a history entry from a check result."""
        # This is a stub method for now - implement based on requirements
        return {
            "check_id": str(uuid.uuid4()),
            "site_id": website_id,
            "timestamp": datetime.now().isoformat(),
            **check_result
        }

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