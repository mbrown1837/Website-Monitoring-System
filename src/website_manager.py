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
from .path_utils import get_project_root, resolve_path, clean_path_for_logging

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
        self._cache_mod_time = 0.0  # Tracks the modification time of the loaded file
        self._load_websites()  # Initial load

    def _initialize_website_list_path(self):
        """Initialize path to store websites list file."""
        path = self.config.get("websites_file_path", "data/websites.json")
        
        # Use environment-agnostic path resolution
        resolved_path = resolve_path(path)
        
        # Ensure directory exists
        directory = os.path.dirname(resolved_path)
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory, exist_ok=True)
                self.logger.info(f"Created directory for websites data: {clean_path_for_logging(directory)}")
            except OSError as e:
                self.logger.error(f"Error creating directory {clean_path_for_logging(directory)} for websites data: {e}")
                raise
                
        return resolved_path

    def _load_websites(self, force_reload=False):
        """
        Load websites from the JSON file into self._websites.
        Implements a cache that reloads automatically if the underlying file has changed.
        """
        try:
            # Check if the file has been modified since the last load.
            # This ensures that changes made by other processes are picked up.
            current_mod_time = os.path.getmtime(self.websites_file_path)
            if current_mod_time > self._cache_mod_time:
                self.logger.info(f"Change detected in {clean_path_for_logging(self.websites_file_path)}. Forcing cache reload.")
                force_reload = True
        except OSError:
            # This can happen if the file does not exist, which is a valid state.
            # The logic below will handle creating an empty file.
            pass

        if self._websites_loaded and not force_reload:
            return self._websites
            
        try:
            if not os.path.exists(self.websites_file_path):
                self.logger.info(f"Websites file not found at {clean_path_for_logging(self.websites_file_path)}. Starting with empty list.")
                with open(self.websites_file_path, "w", encoding="utf-8") as f:
                    json.dump([], f)
                self._websites = []
            else:
                with open(self.websites_file_path, "r", encoding="utf-8") as f:
                    self._websites = json.load(f)
                self.logger.debug(f"Successfully loaded {len(self._websites)} websites from {clean_path_for_logging(self.websites_file_path)}")
            
            # Update cache state
            self._websites_loaded = True
            self._cache_mod_time = os.path.getmtime(self.websites_file_path)
            return self._websites
            
        except (IOError, json.JSONDecodeError, OSError) as e:
            self.logger.error(f"Error loading websites from {clean_path_for_logging(self.websites_file_path)}: {e}")
            # Reset cache state on error
            self._websites = []
            self._websites_loaded = True # Mark as "loaded" to prevent reload loops on a broken file
            self._cache_mod_time = 0.0
            return self._websites
            
    def _save_websites(self):
        """Save self._websites to the JSON file."""
        try:
            with open(self.websites_file_path, "w", encoding="utf-8") as f:
                json.dump(self._websites, f, indent=2)
            self.logger.debug(f"Successfully saved {len(self._websites)} websites to {clean_path_for_logging(self.websites_file_path)}")
            # Update the cache modification time to prevent an immediate reload
            self._cache_mod_time = os.path.getmtime(self.websites_file_path)
            return True
        except (IOError, OSError) as e:
            self.logger.error(f"Error saving websites to {clean_path_for_logging(self.websites_file_path)}: {e}")
            return False

    def add_website(self, url: str, name: str = "", interval: int = None, is_active: bool = True, tags: list = None, notification_emails: list = None, 
                   enable_blur_detection: bool = False, blur_detection_scheduled: bool = False, blur_detection_manual: bool = True,
                   auto_crawl_enabled: bool = True, auto_visual_enabled: bool = True, auto_blur_enabled: bool = False, auto_performance_enabled: bool = False,
                   auto_full_check_enabled: bool = False):
        """
        Add a new website to the monitoring list.
        
        Args:
            url (str): The URL of the website.
            name (str, optional): The name of the website. If empty, the domain will be used.
            interval (int, optional): The monitoring interval in hours. If None, default from config is used.
            is_active (bool, optional): Whether the website should be actively monitored. Defaults to True.
            tags (list, optional): List of tags to categorize the website. Defaults to empty list.
            notification_emails (list, optional): List of email addresses for notifications. Defaults to empty list.
            enable_blur_detection (bool, optional): Whether blur detection is enabled for this website. Defaults to False.
            blur_detection_scheduled (bool, optional): Whether blur detection runs on scheduled checks. Defaults to False.
            blur_detection_manual (bool, optional): Whether blur detection runs on manual checks. Defaults to True.
            auto_crawl_enabled (bool, optional): Whether crawling is enabled for automated checks. Defaults to True.
            auto_visual_enabled (bool, optional): Whether visual monitoring is enabled for automated checks. Defaults to True.
            auto_blur_enabled (bool, optional): Whether blur detection is enabled for automated checks. Defaults to False.
            auto_performance_enabled (bool, optional): Whether performance monitoring is enabled for automated checks. Defaults to False.
            auto_full_check_enabled (bool, optional): Whether full check is enabled for automated checks. Defaults to False.
            
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
            
        # Handle Full Check option - when enabled, it enables all other monitoring types
        if auto_full_check_enabled:
            auto_crawl_enabled = True
            auto_visual_enabled = True
            auto_blur_enabled = True
            auto_performance_enabled = True
        
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
            'last_updated_utc': datetime.now(timezone.utc).isoformat(),
            'render_delay': 6,  # Default render delay
            'max_crawl_depth': 2,  # Default crawl depth
            'visual_diff_threshold': 5,  # Default visual difference threshold
            'capture_subpages': True,  # Always capture subpages by default
            'all_baselines': {},
            'has_subpage_baselines': False,
            'baseline_visual_path': None,
            # Blur detection options
            'enable_blur_detection': enable_blur_detection,
            'blur_detection_scheduled': blur_detection_scheduled,
            'blur_detection_manual': blur_detection_manual,
            # Automated monitoring preferences
            'auto_crawl_enabled': auto_crawl_enabled,
            'auto_visual_enabled': auto_visual_enabled,
            'auto_blur_enabled': auto_blur_enabled,
            'auto_performance_enabled': auto_performance_enabled,
            'auto_full_check_enabled': auto_full_check_enabled
        }
        
        self._websites.append(new_website)
        self._save_websites()
        self.logger.info(f"Added new website: {name} ({url}) with blur detection: {enable_blur_detection}")
        
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
                
        if current_site_idx < 0:
            self.logger.warning(f"Website with ID '{site_id}' not found. Cannot update.")
            return None
        
        # Get the current website data
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
        
        # Update last_updated timestamp
        current_site['last_updated_utc'] = datetime.now(timezone.utc).isoformat()
        
        # Save the changes
        self._save_websites()
        self.logger.info(f"Updated website: {current_site.get('name')} (ID: {site_id})")
        
        return current_site
        
    def save_website(self, site_id: str, website_data: dict):
        """
        Save a website's complete data by replacing the existing record.
        
        Args:
            site_id (str): The ID of the website to save.
            website_data (dict): Complete website data dictionary.
            
        Returns:
            dict: The saved website record, or None if save failed.
        """
        self._load_websites()
        
        # Find the website to update
        current_site_idx = -1
        for i, site in enumerate(self._websites):
            if site.get('id') == site_id:
                current_site_idx = i
                
        if current_site_idx < 0:
            self.logger.warning(f"Website with ID '{site_id}' not found. Cannot save.")
            return None
            
        # Ensure the ID is preserved
        website_data['id'] = site_id
        
        # Update last_updated timestamp if not already set in the provided data
        if 'last_updated_utc' not in website_data:
            website_data['last_updated_utc'] = datetime.now(timezone.utc).isoformat()
        
        # Replace the website data
        self._websites[current_site_idx] = website_data
        
        # Save the changes
        self._save_websites()
        self.logger.info(f"Saved website: {website_data.get('name')} (ID: {site_id})")
        
        return website_data

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

    def capture_baseline_for_site(self, site_id):
        """
        Triggers a comprehensive baseline capture for a website, including all subpages.
        This is now handled by the scheduler's check function with a specific option.

        Args:
            site_id (str): ID of the website to capture baseline for.

        Returns:
            dict: The result from the check, or an error dictionary.
        """
        self.logger.info(f"Delegating baseline capture for site_id: {site_id} to the scheduler.")
        
        site = self.get_website(site_id)
        if not site:
            self.logger.error(f"Site with ID {site_id} not found, cannot capture baseline.")
            return {"status": "error", "message": "Website not found"}

        try:
            # We import here to avoid circular dependency issues at startup
            from src.scheduler import perform_website_check
            
            # The scheduler's check function now handles the entire process
            # when called with the 'create_baseline' option.
            result = perform_website_check(
                site_id,
                crawler_options_override={'create_baseline': True}
            )

            if result and result.get('status') == 'Baseline Created':
                self.logger.info(f"Successfully initiated and completed baseline capture for site {site_id}.")
                return result
            else:
                self.logger.error(f"Baseline capture for site {site_id} failed or did not complete as expected. Result: {result}")
                return result

        except Exception as e:
            self.logger.error(f"An unexpected error occurred while triggering baseline capture for site {site_id}: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    def get_automated_check_config(self, website_id):
        """Get automated monitoring configuration for a website."""
        website = self.get_website(website_id)
        if not website:
            return None
        
        # Check if Full Check is enabled
        if website.get('auto_full_check_enabled', False):
            # If Full Check is enabled, enable all monitoring types
            return {
                'crawl_enabled': True,
                'visual_enabled': True,
                'blur_enabled': True,
                'performance_enabled': True
            }
        else:
            # Otherwise, use individual settings
            return {
                'crawl_enabled': website.get('auto_crawl_enabled', True),
                'visual_enabled': website.get('auto_visual_enabled', True),
                'blur_enabled': website.get('auto_blur_enabled', False),
                'performance_enabled': website.get('auto_performance_enabled', False)
            }
    
    def get_manual_check_config(self, check_type):
        """Get manual check configuration based on button pressed."""
        configs = {
            'full': {'crawl_enabled': True, 'visual_enabled': True, 'blur_enabled': True, 'performance_enabled': True},
            'visual': {'crawl_enabled': False, 'visual_enabled': True, 'blur_enabled': False, 'performance_enabled': False},
            'crawl': {'crawl_enabled': True, 'visual_enabled': False, 'blur_enabled': False, 'performance_enabled': False},
            'blur': {'crawl_enabled': False, 'visual_enabled': False, 'blur_enabled': True, 'performance_enabled': False},
            'performance': {'crawl_enabled': False, 'visual_enabled': False, 'blur_enabled': False, 'performance_enabled': True}
        }
        return configs.get(check_type, configs['full'])

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