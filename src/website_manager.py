import json
import os
import uuid
import shutil # Added for rmtree
from datetime import datetime, timezone
from src.config_loader import get_config
from src.logger_setup import setup_logging
import src.content_retriever as content_retriever # For baseline capture
import src.snapshot_tool as snapshot_tool # For baseline capture
from urllib.parse import urlparse

class WebsiteManager:
    def __init__(self, config_path=None):
        # If a specific config_path is provided for this instance, use it.
        # Otherwise, the global config (if already loaded by another module) or default path will be used.
        # This allows flexibility if multiple manager instances with different configs were needed.
        if config_path:
            self.config = get_config(config_path=config_path) # specific config for this instance
            self.logger = setup_logging(config_path=config_path)
        else:
            self.config = get_config() # Uses global/default config
            self.logger = setup_logging() # Uses global/default logger setup
        
        self.websites_file_path = self._initialize_website_list_path()
        self._websites = []  # Internal cache for websites
        self._websites_loaded = False  # Flag to check if initial load happened
        self._load_websites() # Initial load

    def _initialize_website_list_path(self):
        path = self.config.get('website_list_file_path', 'data/websites.json')
        if not os.path.isabs(path):
            # Assuming project root is one level up from 'src' where this file is expected
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            path = os.path.join(project_root, path)
        
        directory = os.path.dirname(path)
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory)
                self.logger.info(f"Created directory for website list: {directory}")
            except OSError as e:
                self.logger.error(f"Error creating directory {directory} for website list: {e}")
                raise
        return path

    def _load_websites(self, force_reload=False):
        try:
            if not os.path.exists(self.websites_file_path):
                self.logger.info(f"Website list file not found at {self.websites_file_path}. Creating an empty list.")
                with open(self.websites_file_path, 'w', encoding='utf-8') as f:
                    json.dump([], f)
                self._websites = []
            else:
                with open(self.websites_file_path, 'r', encoding='utf-8') as f:
                    self._websites = json.load(f)
            self._websites_loaded = True
            return self._websites
        except (IOError, json.JSONDecodeError) as e:
            self.logger.error(f"Error loading websites from {self.websites_file_path}: {e}")
            self._websites = [] 
            self._websites_loaded = True 
            return self._websites

    def _save_websites(self):
        try:
            with open(self.websites_file_path, 'w', encoding='utf-8') as f:
                json.dump(self._websites, f, indent=2)
            self.logger.info(f"Successfully saved {len(self._websites)} websites to {self.websites_file_path}")
        except IOError as e:
            self.logger.error(f"Error saving websites to {self.websites_file_path}: {e}")

    def add_website(self, url: str, name: str = "", interval: int = None, is_active: bool = True, tags: list = None, notification_emails: list = None):
        self._load_websites() # Ensure list is current before add
        if not url:
            self.logger.warning("Attempted to add a website with no URL.")
            return None

        for site in self._websites:
            if site['url'] == url:
                self.logger.warning(f"Website with URL '{url}' already exists (ID: {site['id']}). Returning existing.")
                return site

        default_interval = self.config.get('default_monitoring_interval_hours', 24)
        
        new_site = {
            "id": str(uuid.uuid4()),
            "url": url,
            "name": name if name else url,
            "interval": interval if interval is not None else default_interval,
            "last_checked_utc": None,
            "is_active": is_active,
            "tags": tags if tags is not None else [],
            "notification_emails": notification_emails if notification_emails is not None else [],
            "date_added_utc": datetime.now(timezone.utc).isoformat(),
            "baseline_html_path": None, # New field for baseline
            "baseline_visual_path": None, # New field for baseline
            "baseline_html_hash": None # New field for baseline
        }
        self._websites.append(new_site)
        self._save_websites()
        self.logger.info(f"Added new website: {new_site['name']} ({new_site['url']}) with ID {new_site['id']}.")
        
        # Automatically capture baseline for the new site
        self.logger.info(f"Attempting to capture initial baseline for new site ID: {new_site['id']}")
        baseline_success = self.capture_baseline_for_site(new_site['id'])
        if baseline_success:
            self.logger.info(f"Successfully captured initial baseline for site ID: {new_site['id']}")
        else:
            self.logger.warning(f"Failed to capture initial baseline for site ID: {new_site['id']}. Site added without baseline.")
            # The site is added, but baseline fields will remain None. User can try manual capture.
            
        # Return the site object, potentially updated with baseline paths from capture_baseline_for_site
        # Need to re-fetch it as capture_baseline_for_site modifies and saves it.
        return self.get_website(new_site['id'])

    def get_website(self, site_id: str):
        self._load_websites() # Ensure list is current
        for site in self._websites:
            if site['id'] == site_id:
                return site
        self.logger.debug(f"Website with ID '{site_id}' not found.")
        return None
    
    def get_website_by_url(self, url: str):
        self._load_websites() # Ensure list is current
        for site in self._websites:
            if site['url'] == url:
                return site
        self.logger.debug(f"Website with URL '{url}' not found.")
        return None

    def list_websites(self, active_only: bool = False):
        self._load_websites() # Ensure list is current
        # Prepare data for UI, especially for last_checked
        processed_sites = {}
        for site in self._websites:
            if active_only and not site.get('is_active', True):
                continue
            site_copy = site.copy() # Avoid modifying cache
            if site_copy.get('last_checked_utc'):
                try:
                    dt_obj = datetime.fromisoformat(site_copy['last_checked_utc'].replace('Z', '+00:00'))
                    site_copy['last_checked_simple'] = dt_obj.strftime('%Y-%m-%d %H:%M:%S %Z').strip()
                except ValueError:
                    site_copy['last_checked_simple'] = site_copy['last_checked_utc'] # fallback
            else:
                site_copy['last_checked_simple'] = 'Never'
            
            # Add baseline info for display if available
            site_copy['baseline_html_available'] = bool(site_copy.get('baseline_html_path'))
            site_copy['baseline_visual_available'] = bool(site_copy.get('baseline_visual_path'))
            site_copy['notification_emails'] = site_copy.get('notification_emails', []) # Ensure it's in output

            processed_sites[site_copy['id']] = site_copy
        return processed_sites

    def update_website(self, site_id: str, updates: dict):
        self._load_websites() # Ensure list is current
        site_found_idx = -1
        for i, site in enumerate(self._websites):
            if site['id'] == site_id:
                site_found_idx = i
                break
        
        if site_found_idx == -1:
            self.logger.warning(f"Failed to update. Website with ID '{site_id}' not found.")
            return None

        # Handle potential baseline recapture
        recapture_baseline_flag = updates.pop('recapture_baseline', False)

        # Prevent updating immutable fields directly, or validate
        if 'id' in updates and updates['id'] != site_id: 
            self.logger.warning(f"Attempt to change site ID for {site_id} was ignored.")
            del updates['id']
        if 'date_added_utc' in updates: 
            del updates['date_added_utc']
        # Ensure notification_emails is a list if provided
        if 'notification_emails' in updates and not isinstance(updates['notification_emails'], list):
            self.logger.warning(f"Invalid format for notification_emails for site {site_id}. Expected a list. Ignoring update to this field.")
            del updates['notification_emails']
        
        # Check for URL collision if URL is being changed
        if 'url' in updates and updates['url'] != self._websites[site_found_idx]['url']:
            for other_site in self._websites:
                if other_site['id'] != site_id and other_site['url'] == updates['url']:
                    self.logger.error(f"Cannot update URL for site ID '{site_id}'. New URL '{updates['url']}' already exists for site '{other_site['name']}' (ID: {other_site['id']}).")
                    return None
        
        self._websites[site_found_idx].update(updates)
        self._websites[site_found_idx]["last_updated_utc"] = datetime.now(timezone.utc).isoformat()
        self._save_websites()
        self.logger.info(f"Updated website ID: {site_id} with details: {updates}")

        if recapture_baseline_flag:
            self.logger.info(f"Recapture baseline flag set for site ID: {site_id}. Attempting to update baseline.")
            baseline_success = self.capture_baseline_for_site(site_id)
            if baseline_success:
                self.logger.info(f"Successfully updated baseline for site ID: {site_id}")
            else:
                self.logger.warning(f"Failed to update baseline for site ID: {site_id} during update operation.")
        
        return self.get_website(site_id) # Return the potentially updated site from cache

    def remove_website(self, site_id: str):
        self._load_websites() # Ensure list is current
        site_to_remove = self.get_website(site_id) # Get details before removing from list
        original_length = len(self._websites)
        self._websites = [site for site in self._websites if site['id'] != site_id]
        
        if len(self._websites) < original_length:
            self._save_websites()
            self.logger.info(f"Removed website data for ID: {site_id}")

            # Get base snapshot directory
            snapshot_base_dir = self.config.get('snapshot_directory', 'data/snapshots')
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            
            # Ensure snapshot_base_dir is absolute
            if not os.path.isabs(snapshot_base_dir):
                snapshot_base_dir = os.path.join(project_root, snapshot_base_dir)

            # Now, remove associated snapshot directory - multiple approaches
            domain_name = None
            if site_to_remove and site_to_remove.get('url', ''):
                parsed_url = urlparse(site_to_remove.get('url', ''))
                domain_name = parsed_url.netloc.replace('.', '_').replace(':', '_')

            # List of potential paths to check and remove
            potential_paths = []

            # 1. Standard case: domain_name/site_id
            if domain_name:
                potential_paths.append(os.path.join(snapshot_base_dir, domain_name, site_id))
            
            # 2. Site ID at top level
            potential_paths.append(os.path.join(snapshot_base_dir, site_id))
            
            # 3. Domain name folder might contain this site's data
            if domain_name:
                domain_path = os.path.join(snapshot_base_dir, domain_name)
                if os.path.exists(domain_path):
                    potential_paths.append(domain_path)

            # Try to remove all potential paths
            paths_removed = False
            for path in potential_paths:
                if os.path.exists(path):
                    try:
                        shutil.rmtree(path)
                        self.logger.info(f"Successfully removed snapshot directory: {path}")
                        paths_removed = True
                    except OSError as e:
                        self.logger.error(f"Error removing snapshot directory {path}: {e}")

            # Final fallback: Look for any directory containing this site_id
            if not paths_removed:
                try:
                    for root, dirs, files in os.walk(snapshot_base_dir):
                        for dir_name in dirs:
                            if site_id in dir_name:
                                full_path = os.path.join(root, dir_name)
                                try:
                                    shutil.rmtree(full_path)
                                    self.logger.info(f"Removed alternative snapshot directory: {full_path}")
                                    paths_removed = True
                                except OSError as e:
                                    self.logger.error(f"Error removing directory {full_path}: {e}")
                except Exception as e:
                    self.logger.error(f"Error searching for alternative snapshot directories for site ID {site_id}: {e}")
            
            if not paths_removed:
                self.logger.warning(f"No snapshot directories found or removed for site ID {site_id}.")
                
            return True
        else:
            self.logger.warning(f"Failed to remove website data. Website with ID '{site_id}' not found in records.")
            return False

    def capture_baseline_for_site(self, site_id: str) -> bool:
        """Captures and saves HTML and visual snapshots as the baseline for a given site.

        Args:
            site_id (str): The ID of the website to capture the baseline for.

        Returns:
            bool: True if baseline capture and update were successful, False otherwise.
        """
        self.logger.info(f"Starting baseline capture for site ID: {site_id}")
        site_details = self.get_website(site_id)
        if not site_details:
            self.logger.error(f"Cannot capture baseline: Site ID {site_id} not found.")
            return False

        url = site_details['url']
        self.logger.info(f"Fetching content for baseline for {url} (Site ID: {site_id})...")
        status_code, _, html_content, fetch_error = content_retriever.fetch_website_content(url)

        if fetch_error or not html_content:
            self.logger.error(f"Failed to fetch content for baseline (Site ID: {site_id}, URL: {url}). Error: {fetch_error}")
            # Optionally update site status or log more specifically
            return False

        self.logger.info(f"Saving baseline HTML snapshot for site ID: {site_id}")
        baseline_html_path, baseline_html_hash = snapshot_tool.save_html_snapshot(
            site_id, url, html_content, is_baseline=True
        )

        self.logger.info(f"Saving baseline visual snapshot for site ID: {site_id}")
        baseline_visual_path = snapshot_tool.save_visual_snapshot(
            site_id, url, is_baseline=True
        )

        if not baseline_html_path and not baseline_visual_path:
            self.logger.error(f"Failed to save both HTML and visual baselines for site ID: {site_id}.")
            return False # Both failed, something is wrong
        
        update_payload = {}
        if baseline_html_path:
            update_payload['baseline_html_path'] = baseline_html_path
            update_payload['baseline_html_hash'] = baseline_html_hash
            self.logger.info(f"Baseline HTML for site {site_id} stored at: {baseline_html_path} with hash {baseline_html_hash}")
        else:
            self.logger.warning(f"Failed to save baseline HTML for site ID: {site_id}")

        if baseline_visual_path:
            update_payload['baseline_visual_path'] = baseline_visual_path
            self.logger.info(f"Baseline visual for site {site_id} stored at: {baseline_visual_path}")
        else:
            self.logger.warning(f"Failed to save baseline visual for site ID: {site_id}")

        if not update_payload: # If neither was successful
            self.logger.error(f"No baseline data captured successfully for site {site_id}")
            return False

        # Update the website record with new baseline paths and hash
        # Internal update without triggering another baseline capture
        current_site_idx = -1
        for i, site in enumerate(self._websites):
            if site['id'] == site_id:
                current_site_idx = i
                break
        
        if current_site_idx != -1:
            self._websites[current_site_idx].update(update_payload)
            self._websites[current_site_idx]["last_updated_utc"] = datetime.now(timezone.utc).isoformat()
            self._save_websites()
            self.logger.info(f"Site {site_id} record updated with new baseline information: {update_payload}")
            return True
        else:
            # This case should ideally not happen if get_website succeeded earlier
            self.logger.error(f"Internal error: Site {site_id} not found in cache during baseline update.")
            return False

# Example Usage (for direct script execution testing)
if __name__ == '__main__':
    print("Running WebsiteManager class directly for demonstration...")
    
    # Create a dummy config for the test if a global one isn't sufficient
    # For this demo, we assume a config.yaml exists or default_config works.
    # You might want to point to a specific test config for isolated testing.
    test_config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')
    
    # Ensure a clean slate for demo file if it exists from prior runs
    demo_manager_for_path = WebsiteManager(config_path=test_config_path)
    if os.path.exists(demo_manager_for_path.websites_file_path):
        print(f"Removing existing demo file: {demo_manager_for_path.websites_file_path}")
        os.remove(demo_manager_for_path.websites_file_path)
    
    # Create a new manager instance for the demo, which will create the file
    manager = WebsiteManager(config_path=test_config_path)
    manager._load_websites(force_reload=True) # Force reload to ensure clean state for demo

    logger = manager.logger # Use the logger from the manager instance

    logger.info("----- Starting WebsiteManager Class Demo -----")

    # Add some websites
    site1 = manager.add_website(url="https://google.com", name="Google Search", interval=6, tags=["search_engine", "global"])
    site2 = manager.add_website(url="https://openai.com", name="OpenAI", is_active=True, tags=["ai", "research"])
    manager.add_website(url="http://nonexistentsite.xyz", name="Test Site", is_active=False)
    manager.add_website(url="https://google.com") # Attempt to add duplicate

    all_sites_map = manager.list_websites()
    logger.info(f"All websites (map): {json.dumps(all_sites_map, indent=2)}")
    
    active_sites_map = manager.list_websites(active_only=True)
    logger.info(f"Active websites (map): {json.dumps(active_sites_map, indent=2)}")

    if site1:
        retrieved_site = manager.get_website(site1['id'])
        logger.info(f"Retrieved site by ID ({site1['id']}): {json.dumps(retrieved_site, indent=2)}")

    retrieved_by_url = manager.get_website_by_url("https://openai.com")
    logger.info(f"Retrieved site by URL (https://openai.com): {json.dumps(retrieved_by_url, indent=2)}")

    if site2:
        update_payload = {"name": "OpenAI Official Site", "interval": 12, "is_active": True, "tags": ["ai", "official"], "new_field": "test"}
        updated_site = manager.update_website(site2['id'], update_payload)
        logger.info(f"Updated site ({site2['id']}): {json.dumps(updated_site, indent=2)}")
        
        logger.info(f"Attempting to update URL of site {site1['id']} to {site2['url']} (should fail or warn)")
        failed_update = manager.update_website(site1['id'], {"url": site2['url']})
        if failed_update is None:
            logger.info("URL update to existing URL correctly prevented.")
        else:
            logger.error("URL update to existing URL was NOT prevented.")

    if site1:
        manager.remove_website(site1['id'])
        logger.info(f"Attempted to remove site ID: {site1['id']}")
    
    manager.remove_website("non_existent_id")

    final_sites_map = manager.list_websites()
    logger.info(f"Final list of websites (map): {json.dumps(final_sites_map, indent=2)}")

    logger.info("----- WebsiteManager Class Demo Finished -----")
    print(f"Demo complete. Check the log file: {manager.config.get('log_file_path')} and website list: {manager.websites_file_path}") 