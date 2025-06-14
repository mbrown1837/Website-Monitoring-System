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
        # Set up basics
        if config_path:
            self.config = get_config(config_path=config_path)
            self.logger = setup_logging(config_path=config_path)
        else:
            self.config = get_config()
            self.logger = setup_logging()
        
        self.websites_file_path = self._initialize_website_list_path()
        self._websites = []  # Cache
        self._websites_loaded = False
        self._load_websites()  # Initial load

    def _initialize_website_list_path(self):
        """Initialize path to store websites list file."""
        path = self.config.get("websites_file_path", "data/websites.json")
        if not os.path.isabs(path):
            # Get the project root (assumes this module is in src/)
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            path = os.path.join(project_root, path)
            
        # Ensure directory exists
        directory = os.path.dirname(path)
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory, exist_ok=True)
                self.logger.info(f"Created directory for websites data: {directory}")
            except OSError as e:
                self.logger.error(f"Error creating directory {directory} for websites data: {e}")
                raise
                
        return path

    def _load_websites(self, force_reload=False):
        """Load websites from the JSON file into self._websites."""
        if self._websites_loaded and not force_reload:
            return self._websites
            
        try:
            if not os.path.exists(self.websites_file_path):
                self.logger.info(f"Websites file not found at {self.websites_file_path}. Starting with empty list.")
                with open(self.websites_file_path, "w", encoding="utf-8") as f:
                    json.dump([], f)
                self._websites = []
            else:
                with open(self.websites_file_path, "r", encoding="utf-8") as f:
                    self._websites = json.load(f)
                self.logger.debug(f"Successfully loaded {len(self._websites)} websites from {self.websites_file_path}")
            self._websites_loaded = True
            return self._websites
        except (IOError, json.JSONDecodeError) as e:
            self.logger.error(f"Error loading websites from {self.websites_file_path}: {e}")
            self._websites = []
            self._websites_loaded = True
            return self._websites
            
    def _save_websites(self):
        """Save self._websites to the JSON file."""
        try:
            with open(self.websites_file_path, "w", encoding="utf-8") as f:
                json.dump(self._websites, f, indent=2)
            self.logger.debug(f"Successfully saved {len(self._websites)} websites to {self.websites_file_path}")
            return True
        except IOError as e:
            self.logger.error(f"Error saving websites to {self.websites_file_path}: {e}")
            return False

    def add_website(self, url: str, name: str = "", interval: int = None, is_active: bool = True, tags: list = None, notification_emails: list = None):
        """
        Add a new website to the monitoring list.
        
        Args:
            url (str): The URL of the website.
            name (str, optional): The name of the website. If empty, the domain will be used.
            interval (int, optional): The monitoring interval in hours. If None, default from config is used.
            is_active (bool, optional): Whether the website should be actively monitored. Defaults to True.
            tags (list, optional): List of tags to categorize the website. Defaults to empty list.
            notification_emails (list, optional): List of email addresses for notifications. Defaults to empty list.
            
        Returns:
            dict: The newly created website record, or None if creation failed.
        """
        self._load_websites()
        
        # Validate URL
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            self.logger.info(f"URL modified to include https:// scheme: {url}")
            
        # Check for duplicates
        if self.get_website_by_url(url):
            self.logger.warning(f"Website with URL '{url}' already exists. Skipping creation.")
            return None
            
        # Set default name if not provided
        if not name:
            parsed_url = urlparse(url)
            name = parsed_url.netloc
            
        # Set default interval if not provided
        if interval is None:
            interval = self.config.get('default_monitoring_interval_hours', 24)
            
        # Set default for tags and notification_emails if not provided
        if tags is None:
            tags = []
        if notification_emails is None:
            notification_emails = []
            
        # Create new website record
        new_website = {
            'id': str(uuid.uuid4()),
            'url': url,
            'name': name,
            'interval': interval,
            'is_active': is_active,
            'tags': tags,
            'notification_emails': notification_emails,
            'created_utc': datetime.now(timezone.utc).isoformat(),
            'last_updated_utc': datetime.now(timezone.utc).isoformat()
        }
        
        self._websites.append(new_website)
        self._save_websites()
        self.logger.info(f"Added new website: {name} ({url})")
        
        return new_website

    def get_website(self, site_id: str):
        """Get a website by its ID."""
        self._load_websites()
        for site in self._websites:
            if site.get('id') == site_id:
                return site
        return None
        
    def get_website_by_url(self, url: str):
        """Get a website by its URL."""
        self._load_websites()
        for site in self._websites:
            if site.get('url') == url:
                return site
        return None
        
    def list_websites(self, active_only: bool = False):
        """
        Get a dictionary of all websites, keyed by site ID.
        
        Args:
            active_only (bool, optional): If True, only return active websites.
            
        Returns:
            dict: Dictionary of websites, keyed by site ID.
        """
        self._load_websites()
        websites_dict = {}
        
        for site in self._websites:
            if not active_only or site.get('is_active', False):
                website_id = site.get('id')
                if website_id:  # Skip entries without a valid ID
                    websites_dict[website_id] = site
                    
        # Quick validation - make sure there are no duplicate IDs
        if len(websites_dict) != len([s for s in self._websites if (not active_only or s.get('is_active', False)) and s.get('id')]):
            self.logger.warning("Detected duplicate website IDs in database. This may cause unexpected behavior.")
            
        return websites_dict

    def update_website(self, site_id: str, updates: dict):
        """
        Update a website's properties.
        
        Args:
            site_id (str): The ID of the website to update.
            updates (dict): Dictionary of properties to update.
            
        Returns:
            dict: The updated website record, or None if update failed.
        """
        self._load_websites()
        
        # Find the website to update
        current_site_idx = -1
        for i, site in enumerate(self._websites):
            if site.get('id') == site_id:
                current_site_idx = i
                break
                
        if current_site_idx == -1:
            self.logger.warning(f"Cannot update website: Site ID {site_id} not found.")
            return None
        
        current_site = self._websites[current_site_idx]
        
        # Special case: if URL is being changed, check for duplicates
        if 'url' in updates and updates['url'] != current_site.get('url'):
            # Check for duplicates
            if self.get_website_by_url(updates['url']):
                self.logger.warning(f"Cannot update URL: Website with URL '{updates['url']}' already exists.")
                return None
        
        # Handle name update - if new name is empty, generate from URL
        if 'name' in updates and not updates['name'] and 'url' in updates:
            parsed_url = urlparse(updates['url'])
            updates['name'] = parsed_url.netloc
        elif 'name' in updates and not updates['name']:
            parsed_url = urlparse(current_site.get('url', ''))
            updates['name'] = parsed_url.netloc
        
        # Update the website record
        for key, value in updates.items():
            # Skip unknown or immutable properties
            if key == 'id':
                continue  # Don't allow changing the ID
            if key == 'created_utc':
                continue  # Don't allow changing the creation timestamp
                
            current_site[key] = value
        
        # Update the last_updated timestamp
        current_site['last_updated_utc'] = datetime.now(timezone.utc).isoformat()
        
        self._save_websites()
        self.logger.info(f"Updated website: {current_site.get('name')} (ID: {site_id})")
        
        return current_site

    def remove_website(self, site_id: str):
        """
        Remove a website from the monitoring list.
        
        Args:
            site_id (str): The ID of the website to remove.
            
        Returns:
            bool: True if removal was successful, False otherwise.
        """
        self._load_websites()
        
        # Find the website to remove
        website = self.get_website(site_id)
        if website:
            # Get domain name for cleanup
            domain_name = None
            try:
                parsed_url = urlparse(website.get('url', ''))
                domain_name = parsed_url.netloc.replace('.', '_').replace(':', '_')
            except:
                self.logger.warning(f"Could not parse URL for site {site_id} during removal.")
            
            # Remove from the list
            self._websites = [site for site in self._websites if site.get('id') != site_id]
            self._save_websites()
            self.logger.info(f"Removed website: {website.get('name', site_id)} (ID: {site_id})")
            
            # Clean up snapshot directories
            snapshot_base_dir = self.config.get('snapshot_directory', 'data/snapshots')
            if not os.path.isabs(snapshot_base_dir):
                # Get the project root (assumes this module is in src/)
                project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
                snapshot_base_dir = os.path.join(project_root, snapshot_base_dir)
            
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

        # Check if site is marked as crawl-only - if so, don't create any baseline
        crawl_only = site_details.get("crawl_only", False)
        if crawl_only:
            self.logger.info(f"Site {site_id} is marked as crawl-only. Skipping baseline creation completely.")
            # Still return True to indicate success (no baseline needed for crawl-only sites)
            return True

        url = site_details["url"]
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

        baseline_visual_path = None
        self.logger.info(f"Saving baseline visual snapshot for site ID: {site_id}")
        baseline_visual_path = snapshot_tool.save_visual_snapshot(
            site_id, url, is_baseline=True
        )

        if not baseline_html_path and not baseline_visual_path:
            self.logger.error(f"Failed to save both HTML and visual baselines for site ID: {site_id}.")
            return False # Both failed, something is wrong
        
        update_payload = {}
        if baseline_html_path:
            update_payload["baseline_html_path"] = baseline_html_path
            update_payload["baseline_html_hash"] = baseline_html_hash
            self.logger.info(f"Baseline HTML for site {site_id} stored at: {baseline_html_path} with hash {baseline_html_hash}")
        else:
            self.logger.warning(f"Failed to save baseline HTML for site ID: {site_id}")

        if baseline_visual_path:
            update_payload["baseline_visual_path"] = baseline_visual_path
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
            if site["id"] == site_id:
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
if __name__ == "__main__":
    print("Running WebsiteManager class directly for demonstration...")
    
    # Create a dummy config for the test if a global one isn't sufficient
    # For this demo, we assume a config.yaml exists or default_config works.
    # You might want to point to a specific test config for isolated testing.
    test_config_path = os.path.join(os.path.dirname(__file__), "..", "config", "config.yaml")
    
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
        retrieved_site = manager.get_website(site1["id"])
        logger.info(f"Retrieved site by ID ({site1['id']}): {json.dumps(retrieved_site, indent=2)}")

    retrieved_by_url = manager.get_website_by_url("https://openai.com")
    logger.info(f"Retrieved site by URL (https://openai.com): {json.dumps(retrieved_by_url, indent=2)}")

    if site2:
        update_payload = {"name": "OpenAI Official Site", "interval": 12, "is_active": True, "tags": ["ai", "official"], "new_field": "test"}
        updated_site = manager.update_website(site2["id"], update_payload)
        logger.info(f"Updated site ({site2['id']}): {json.dumps(updated_site, indent=2)}")
        
        logger.info(f"Attempting to update URL of site {site1['id']} to {site2['url']} (should fail or warn)")
        failed_update = manager.update_website(site1["id"], {"url": site2["url"]})
        if failed_update is None:
            logger.info("URL update to existing URL correctly prevented.")
        else:
            logger.error("URL update to existing URL was NOT prevented.")

    if site1:
        manager.remove_website(site1["id"])
        logger.info(f"Attempted to remove site ID: {site1['id']}")
    
    manager.remove_website("non_existent_id")

    final_sites_map = manager.list_websites()
    logger.info(f"Final list of websites (map): {json.dumps(final_sites_map, indent=2)}")

    logger.info("----- WebsiteManager Class Demo Finished -----")
    print(f"Demo complete. Check the log file: {manager.config.get('log_file_path')} and website list: {manager.websites_file_path}") 