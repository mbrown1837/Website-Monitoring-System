import os
import json
import sqlite3
from datetime import datetime
from urllib.parse import urljoin, urlparse, urlunparse
import time
import re

# Import the required libraries
try:
    from yirabot import Yirabot
except ImportError:
    raise ImportError("YiraBot library not installed. Install it using: pip install yirabot")

from requests.exceptions import SSLError, ConnectTimeout, ReadTimeout, ConnectionError, TooManyRedirects, RequestException
from src.logger_setup import setup_logging
from src.config_loader import get_config

class CrawlerModule:
    """
    Module for crawling websites to detect broken links and missing meta tags.
    Uses YiraBot for crawling and SEO analysis functionality.
    """
    
    def __init__(self, config_path=None):
        """
        Initialize the crawler module.
        
        Args:
            config_path (str, optional): Path to the configuration file.
        """
        # If a specific config_path is provided for this instance, use it.
        if config_path:
            self.config = get_config(config_path=config_path) 
            self.logger = setup_logging(config_path=config_path)
        else:
            self.config = get_config() # Uses global/default config
            self.logger = setup_logging() # Uses global/default logger setup
            
        # Get user agent for logs and headers in requests
        self.user_agent = self.config.get('crawler_user_agent', 
                          self.config.get('playwright_user_agent', 
                          'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'))
        
        # Initialize YiraBot with default parameters
        # Note: YiraBot doesn't support user_agent in __init__, so we'll set it in headers during requests
        try:
            self.bot = Yirabot()  # Initialize with default settings
            self.logger.info(
                f"YiraBot initialized. Will use user agent in requests: {self.user_agent}"
            )
            # Patch YiraBot's random user agent helper to always return the configured one
            try:
                from yirabot import helper_functions

                helper_functions.get_random_user_agent = lambda mobile=False: self.user_agent
                self.logger.debug(
                    "Patched YiraBot helper to use custom user agent"
                )
            except Exception as inner_exc:
                self.logger.warning(
                    f"Could not patch YiraBot user agent: {inner_exc}"
                )
        except Exception as e:
            self.logger.error(f"Error initializing YiraBot: {e}", exc_info=True)
            # Create a fallback instance (same code since we're not passing custom params)
            self.bot = Yirabot()
            self.logger.warning("Using fallback YiraBot initialization")
        
        # Initialize database
        self._initialize_database()
        
    def _initialize_database(self):
        """Initialize the SQLite database for storing crawler results."""
        db_path = self.config.get('database_path', 'data/website_monitor.db')
        if not os.path.isabs(db_path):
            # Assuming project root is one level up from 'src' where this file is expected
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            db_path = os.path.join(project_root, db_path)
            
        # Create directory if it doesn't exist
        directory = os.path.dirname(db_path)
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory)
                self.logger.info(f"Created directory for database: {directory}")
            except OSError as e:
                self.logger.error(f"Error creating directory {directory} for database: {e}")
                raise
                
        self.db_path = db_path
        
        # Create tables if they don't exist
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if we need to run migrations
        self._check_and_migrate_schema(cursor)
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS crawl_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            website_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            broken_links_count INTEGER DEFAULT 0,
            missing_meta_tags_count INTEGER DEFAULT 0,
            total_pages_count INTEGER DEFAULT 0,
            results_json TEXT
        )
        ''')
        
        # Create table for all crawled pages
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS crawled_pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            crawl_id INTEGER NOT NULL,
            website_id TEXT NOT NULL,
            url TEXT NOT NULL,
            status_code INTEGER,
            content_type TEXT,
            title TEXT,
            is_broken BOOLEAN DEFAULT 0,
            error_message TEXT,
            referring_page TEXT,
            FOREIGN KEY (crawl_id) REFERENCES crawl_history(id)
        )
        ''')
        
        # Create indexes for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_crawl_website_id ON crawl_history (website_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_crawl_timestamp ON crawl_history (timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pages_crawl_id ON crawled_pages (crawl_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pages_website_id ON crawled_pages (website_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pages_status_code ON crawled_pages (status_code)')
        
        conn.commit()
        conn.close()
        self.logger.info(f"Database initialized at: {self.db_path}")
        
    def _check_and_migrate_schema(self, cursor):
        """Check database schema and perform migrations if needed."""
        try:
            # Check if total_pages_count column exists
            cursor.execute("PRAGMA table_info(crawl_history)")
            columns = cursor.fetchall()
            column_names = [column[1] for column in columns]
            
            # If table exists but missing total_pages_count column, add it
            if columns and "total_pages_count" not in column_names:
                self.logger.info("Migrating database: Adding total_pages_count column to crawl_history table")
                cursor.execute("ALTER TABLE crawl_history ADD COLUMN total_pages_count INTEGER DEFAULT 0")
                
                # Update existing records with length of all_pages array if possible
                cursor.execute("SELECT id, results_json FROM crawl_history")
                for row in cursor.fetchall():
                    try:
                        crawl_id = row[0]
                        results = json.loads(row[1])
                        all_pages_count = len(results.get("all_pages", []))
                        cursor.execute(
                            "UPDATE crawl_history SET total_pages_count = ? WHERE id = ?",
                            (all_pages_count, crawl_id)
                        )
                        self.logger.debug(f"Updated total_pages_count for crawl_id {crawl_id} to {all_pages_count}")
                    except Exception as e:
                        self.logger.error(f"Error updating total_pages_count for crawl_id {row[0]}: {e}")
        
        except Exception as e:
            # If the table doesn't exist yet, this will fail, which is fine
            self.logger.debug(f"Schema check: {e}")
            pass

    def _normalize_url(self, url: str) -> str:
        """Return a normalized form of the URL for deduplication."""
        try:
            parsed = urlparse(url)
            scheme = parsed.scheme.lower() if parsed.scheme else "http"
            netloc = parsed.netloc.lower()
            path = parsed.path or "/"
            path = re.sub(r"/+$", "", path)
            normalized_url = urlunparse((scheme, netloc, path or "/", "", "", ""))
            self.logger.debug(f"Normalizing URL: {url} -> {normalized_url}")
            return normalized_url
        except Exception as e:
            self.logger.error(f"Error normalizing URL {url}: {e}")
            return url

    def _should_filter_url(self, url: str) -> bool:
        """Return True if the URL should be skipped from crawling."""
        lowered = url.lower()
        if lowered.startswith(("mailto:", "tel:", "javascript:")):
            return True
        return False
        
    def crawl_website(self, website_id, url, max_depth=2, respect_robots=True, check_external_links=True, 
                   crawl_only=False, visual_check_only=False, create_baseline=False):
        """
        Crawl a website to detect broken links and missing meta tags.
        
        Args:
            website_id (str): The ID of the website to crawl.
            url (str): The URL of the website to crawl.
            max_depth (int, optional): The maximum depth to crawl. Defaults to 2.
            respect_robots (bool, optional): Whether to respect robots.txt. Defaults to True.
            check_external_links (bool, optional): Whether to check external links. Defaults to True.
            crawl_only (bool, optional): If True, only crawl without visual checks. Defaults to False.
            visual_check_only (bool, optional): If True, only do visual checks without crawling. Defaults to False.
            create_baseline (bool, optional): If True, creates baseline snapshots for all internal URLs. Defaults to False.
            
        Returns:
            dict: Results of the crawl, including broken links and missing meta tags.
        """
        self.logger.info(f"Starting crawl of website ID {website_id}: {url}")
        
        # Initialize results dictionary
        results = {
            "website_id": website_id,
            "url": url,
            "timestamp": datetime.now().isoformat(),
            "broken_links": [],
            "missing_meta_tags": [],
            "all_pages": [],  # All crawled pages
            "internal_urls": set(),  # Track internal URLs separately
            "external_urls": set(),  # Track external URLs separately
            "visual_baselines": [],   # Store snapshot paths
            "visual_baselines_count": 0,  # Counter for snapshots
            "crawl_stats": {
                "pages_crawled": 0,
                "total_links": 0,
                "total_images": 0,
                "status_code_counts": {},  # For status code statistics
                "sitemap_found": False
            }
        }
        
        try:
            # First try to find and parse sitemaps
            sitemap_found = self._check_sitemaps(url, results)
            results["crawl_stats"]["sitemap_found"] = sitemap_found
            
            if not visual_check_only:  # Skip crawling if only doing visual checks
                # Get all links from site via crawling
                self.logger.debug(f"Crawling {url} for links")
                
                # Start with the homepage
                self._crawl_url(url, url, results, max_depth, 1, respect_robots)
                
                # Update crawl stats
                results["crawl_stats"]["pages_crawled"] = len(results["internal_urls"]) 
                results["crawl_stats"]["total_links"] = (
                    len(results["internal_urls"]) + 
                    len(results["external_urls"])
                )
            else:
                self.logger.info(f"Skipping crawl for {url} (visual check only)")
                # For visual-only checks, add the main URL to internal_urls
                results["internal_urls"].add(url)
            
            # If we're only crawling, skip visual checks and baseline creation
            if not crawl_only:
                # Get SEO data including meta tag analysis for main page
                self.logger.debug(f"Running SEO analysis for {url}")
                seo_data = self.bot.seo_analysis(url)
                self._process_missing_meta_tags(url, seo_data, results)
                
                # If we're creating a baseline or doing visual checks, process visual snapshots
                if create_baseline or visual_check_only:
                    self._capture_visual_baselines(website_id, results)
            else:
                self.logger.info(f"Skipping visual checks and baseline creation for {url} (crawl-only mode)")
            
            # Update status code statistics
            status_counts = {}
            for page in results["all_pages"]:
                status = page.get("status_code", 0)
                status_counts[status] = status_counts.get(status, 0) + 1
            results["crawl_stats"]["status_code_counts"] = status_counts
            
            # Log results summary
            self.logger.info(
                f"Completed website analysis of {url}. Found {len(results['broken_links'])} broken links, "
                f"{len(results['missing_meta_tags'])} missing meta tags, "
                f"{len(results['all_pages'])} total pages, and "
                f"created {results['visual_baselines_count']} visual snapshots."
            )
            
            # Save results to database
            self._save_crawl_results(website_id, results)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error crawling website {url}: {e}", exc_info=True)
            results["error"] = str(e)
            
            # Still save the results even if there was an error
            self._save_crawl_results(website_id, results)
            
            return results
            
    def _check_sitemaps(self, url, results):
        """
        Check for and parse sitemaps to find URLs.
        
        Args:
            url (str): Base URL of the website
            results (dict): Results dictionary to update with found URLs
            
        Returns:
            bool: True if a sitemap was found and parsed, False otherwise
        """
        # Common sitemap paths to check
        sitemap_paths = [
            "/sitemap.xml", 
            "/sitemap_index.xml", 
            "/sitemap.php", 
            "/sitemap.txt", 
            "/sitemap/", 
            "/wp-sitemap.xml"
        ]
        
        # Parse the base URL
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        for path in sitemap_paths:
            sitemap_url = base_url + path
            
            try:
                self.logger.debug(f"Checking for sitemap at {sitemap_url}")
                # Simple GET request first to check if sitemap exists
                response = self.bot.fetch(sitemap_url)
                
                # Only process if we got a valid response
                if response and response.get('status_code') == 200:
                    content = response.get('content')
                    if content and ("<urlset" in content or "<sitemapindex" in content):
                        self.logger.info(f"Sitemap found at {sitemap_url}")
                        
                        # Parse sitemap to extract URLs
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(content, 'xml')
                        
                        # Check if it's a sitemap index
                        sitemaps = soup.find_all('sitemap')
                        if sitemaps:
                            self.logger.debug(f"Found sitemap index with {len(sitemaps)} sitemaps")
                            for sitemap in sitemaps:
                                loc = sitemap.find('loc')
                                if loc and loc.string:
                                    sub_sitemap_url = loc.string.strip()
                                    sub_response = self.bot.fetch(sub_sitemap_url)
                                    if sub_response and sub_response.get('status_code') == 200:
                                        self._parse_sitemap_content(sub_response.get('content'), base_url, results)
                        else:
                            # Parse regular sitemap
                            self._parse_sitemap_content(content, base_url, results)
                            
                        return True
            except Exception as e:
                self.logger.debug(f"Error checking sitemap at {sitemap_url}: {e}")
                
        self.logger.info(f"No sitemap found for {url}, will proceed with regular crawling")
        return False
        
    def _parse_sitemap_content(self, content, base_url, results):
        """Parse sitemap content and extract URLs."""
        try:
            from bs4 import BeautifulSoup
            
            soup = BeautifulSoup(content, 'xml')
            urls = soup.find_all('url')
            
            self.logger.debug(f"Found {len(urls)} URLs in sitemap")
            
            for url_tag in urls:
                loc = url_tag.find('loc')
                if loc and loc.string:
                    url_found = loc.string.strip()
                    if self._should_filter_url(url_found):
                        continue

                    normalized = self._normalize_url(url_found)
                    parsed_url = urlparse(normalized)

                    # Check if it's an internal URL
                    if parsed_url.netloc == urlparse(base_url).netloc:
                        results["internal_urls"].add(normalized)
                    else:
                        results["external_urls"].add(normalized)
        
        except Exception as e:
            self.logger.error(f"Error parsing sitemap content: {type(e).__name__}: {e}", exc_info=True)
    
    def _is_internal_url(self, url, base_url):
        """
        Check if a URL is internal to the website being crawled.
        
        Args:
            url (str): URL to check
            base_url (str): Base URL of the website being crawled
            
        Returns:
            bool: True if the URL is internal, False if external
        """
        try:
            # Parse both URLs
            parsed_url = urlparse(url)
            parsed_base = urlparse(base_url)
            
            # Get domain parts
            url_domain = parsed_url.netloc.lower()
            base_domain = parsed_base.netloc.lower()
            
            # Check if they're exactly the same
            is_internal_flag = False
            if url_domain == base_domain:
                is_internal_flag = True
            else:
                # Check if the URL is a subdomain of the base domain
                # Extract root domain (e.g., "example.com" from "www.example.com" or "blog.example.com")
                url_domain_parts = url_domain.split('.')
                base_domain_parts = base_domain.split('.')
                
                # Get the last two parts (or just the domain if it's a single-part domain)
                url_root_parts = url_domain_parts[-2:] if len(url_domain_parts) >= 2 else url_domain_parts
                base_root_parts = base_domain_parts[-2:] if len(base_domain_parts) >= 2 else base_domain_parts

                url_root_domain = '.'.join(url_root_parts)
                base_root_domain = '.'.join(base_root_parts)

                # If root domains match, consider internal
                # This handles cases like comparing www.example.com to blog.example.com
                if url_root_domain == base_root_domain:
                    is_internal_flag = True
            
            self.logger.debug(f"Checking internal status for {url} against base {base_url}. Result: {is_internal_flag}")
            return is_internal_flag
            
        except Exception as e:
            self.logger.error(f"Error checking if URL is internal: {e}")
            # Default to external in case of parsing error
            self.logger.debug(f"Checking internal status for {url} against base {base_url}. Result: False (due to error)")
            return False
    
    def _crawl_url(self, url, referring_url, results, max_depth, current_depth, respect_robots):
            # This section is removed as it's incorporated into the logic above
        """
        Crawl a specific URL and extract links.
        
        Args:
            url (str): URL to crawl
            referring_url (str): URL that referred to this URL
            results (dict): Results dictionary to update
            max_depth (int): Maximum crawl depth
            current_depth (int): Current crawl depth
            respect_robots (bool): Whether to respect robots.txt
        """
        # Normalize URL and check for duplicates or filters
        if self._should_filter_url(url):
            return

        normalized = self._normalize_url(url)

        # Skip if we've already processed this URL
        if normalized in results["internal_urls"] or normalized in results["external_urls"]:
            return
            
        # Check if it's internal or external
        is_internal = self._is_internal_url(normalized, results["url"])
        
        if current_depth == 1:
            self.logger.info(f"Initial URL processing: URL='{url}', Normalized='{normalized}', Base='{results['url']}', is_internal_check_result='{is_internal}'")
            # For the initial URL (depth 1), it must be treated as internal.
            # This overrides the result of _is_internal_url for the very first page,
            # ensuring it's crawled for links even if normalization/comparison subtleties exist.
            if not is_internal:
                self.logger.warning(f"Initial URL {normalized} was classified as external by _is_internal_url. Forcing to internal for initial crawl.")
                is_internal = True

        # Process the URL
        try:
            self.logger.debug(f"Checking URL: {url} (depth {current_depth}/{max_depth}) - Internal: {is_internal}")
            
            # Use YiraBot's crawl function to get page data if it's internal
            if is_internal:
                results["internal_urls"].add(normalized)
                
                try:
                    # Set up retry mechanism for HTTP2 protocol errors
                    max_retries = 3
                    retry_count = 0
                    crawl_data = None
                    
                    try:
                        while retry_count < max_retries:
                            try:
                                # Get the page content first using YiraBot crawl with appropriate options
                                # Set force=True to bypass robots.txt if respect_robots is False
                                # Note: YiraBot doesn't support custom user agent in crawl directly
                                crawl_data = self.bot.crawl(url, force=not respect_robots)
                                break  # If successful, exit the retry loop
                            except Exception as e:
                                error_message = str(e)
                                retry_count += 1
                                if "HTTP2" in error_message or "ERR_HTTP2_PROTOCOL_ERROR" in error_message:
                                    self.logger.warning(f"HTTP2 protocol error for {url}. Retry {retry_count}/{max_retries}")
                                    time.sleep(1)  # Wait before retrying
                                else:
                                    # For other errors, don't retry
                                    raise

                        if not crawl_data:
                            raise Exception(f"Failed to crawl URL after {max_retries} retries")
                    except Exception as e:
                        self.logger.error(f"YiraBot crawl failed for {url} with {type(e).__name__}: {e}")
                        error_message = f"YiraBot Crawl Error: {type(e).__name__} - {e}"
                        page_record = {
                            "url": normalized,
                            "status_code": 0,
                            "is_broken": True,
                            "error_message": error_message,
                            "referring_page": referring_url,
                            "is_internal": True, # Explicitly True for initial URL if current_depth == 1, otherwise determined by is_internal var
                            "crawl_depth": current_depth
                        }
                        if current_depth == 1: # Ensure initial URL record is marked internal
                            page_record["is_internal"] = True
                        results["all_pages"].append(page_record)
                        results["broken_links"].append({
                            "url": normalized,
                            "status_code": 0,
                            "error_message": error_message,
                            "referring_page": referring_url,
                            "is_internal": True # Explicitly True
                        })
                        # Add to missing_meta_tags for unreachable page
                        results["missing_meta_tags"].append({
                            "url": normalized,
                            "tag_type": "Page Unreachable",
                            "suggestion": f"Could not fetch page content to analyze meta tags. Error: {error_message}",
                            "importance": "critical",
                            "is_unreachable": True
                        })
                        return # Skip further processing for this URL
                    

                    # If it's the initial page (depth 1), log detailed link discovery
                    if current_depth == 1 and isinstance(crawl_data, dict):
                        self.logger.info(f"Initial page crawl data keys for {url}: {list(crawl_data.keys())}")
                        initial_internal_links = crawl_data.get('internal_links', [])
                        initial_external_links = crawl_data.get('external_links', [])
                        num_internal_links = len(initial_internal_links) if isinstance(initial_internal_links, list) else 0
                        num_external_links = len(initial_external_links) if isinstance(initial_external_links, list) else 0
                        self.logger.info(f"Initial page internal links from YiraBot for {url}: {initial_internal_links}")
                        self.logger.info(f"Initial page external links from YiraBot for {url}: {initial_external_links}")
                        self.logger.info(f"Initial page title from YiraBot for {url}: {crawl_data.get('title')}")
                        self.logger.info(f"YiraBot found {num_internal_links} internal links and {num_external_links} external links on initial page {url}.")
                    elif current_depth == 1: # crawl_data might not be a dict if something went wrong but didn't except
                        self.logger.warning(f"Initial page crawl_data for {url} was not a dictionary. Type: {type(crawl_data)}")

                    # Create a successful page record
                    page_record = {
                        "url": normalized,
                        "status_code": 200,  # Assume successful if we got crawl data
                        "is_internal": True, # Explicitly True for initial URL if current_depth == 1, otherwise determined by is_internal var
                        "referring_page": referring_url,
                        "crawl_depth": current_depth,
                        "title": crawl_data.get("title", "")
                    }
                    results["all_pages"].append(page_record)

                    # SEO analysis for every page
                    try:
                        seo_data = self.bot.seo_analysis(url)
                        page_record["seo_data"] = seo_data
                        self._process_missing_meta_tags(url, seo_data, results)
                    except Exception as e:
                        self.logger.warning(f"SEO analysis failed for {url}: {type(e).__name__}: {e}")
                    
                    # If within max depth, crawl linked pages
                    if current_depth < max_depth:
                        self.logger.debug(f"Crawling links from {url} (depth {current_depth}/{max_depth})")
                        
                        # Process internal links
                        for link in crawl_data.get("internal_links", []):
                            if link and link.strip():
                                self.logger.debug(f"Processing internal link from YiraBot: '{link}' (found on '{url}')")
                                raw_full_url = urljoin(url, link) # Keep raw for filter check before normalization
                                self.logger.debug(f"Absolute internal link: '{raw_full_url}'")
                                should_filter = self._should_filter_url(raw_full_url)
                                self.logger.debug(f"Filter check for '{raw_full_url}': {should_filter}")
                                if should_filter:
                                    continue

                                normalized_full_url = self._normalize_url(raw_full_url)
                                self.logger.debug(f"Normalized internal link to potentially crawl: '{normalized_full_url}'")
                                is_already_in_internal = normalized_full_url in results["internal_urls"]
                                self.logger.debug(f"Is '{normalized_full_url}' already in internal_urls: {is_already_in_internal}")

                                if not is_already_in_internal:
                                    self._crawl_url(normalized_full_url, url, results, max_depth, current_depth + 1, respect_robots)
                                
                        # Process external links - only check status codes, don't crawl content
                        for link in crawl_data.get("external_links", []):
                            if link and link.strip() and link.startswith(('http://', 'https://')):
                                self.logger.debug(f"Processing external link from YiraBot: '{link}' (found on '{url}')")
                                # For external links, YiraBot should provide absolute URLs.
                                # However, we pass it through urljoin just in case it's a //domain.com/path style link.
                                raw_full_url = urljoin(url, link)
                                self.logger.debug(f"Absolute external link: '{raw_full_url}'")
                                should_filter = self._should_filter_url(raw_full_url)
                                self.logger.debug(f"Filter check for '{raw_full_url}': {should_filter}")
                                if should_filter:
                                    continue

                                normalized_full_url = self._normalize_url(raw_full_url)
                                self.logger.debug(f"Normalized external link to check: '{normalized_full_url}'")

                                is_in_external = normalized_full_url in results["external_urls"]
                                is_in_internal = normalized_full_url in results["internal_urls"]
                                self.logger.debug(f"Is '{normalized_full_url}' already in external_urls: {is_in_external}, or internal_urls: {is_in_internal}")

                                if not is_in_external and not is_in_internal:
                                    # Check if the link is actually internal based on our enhanced detection
                                    if self._is_internal_url(normalized_full_url, results["url"]):
                                        self.logger.debug(f"Reclassifying 'external' link as internal: {normalized_full_url}")
                                        self._crawl_url(normalized_full_url, url, results, max_depth, current_depth + 1, respect_robots)
                                    else:
                                        results["external_urls"].add(normalized_full_url)
                                        # Just check the status code without crawling the external content
                                        self.logger.debug(f"Only checking status code for external URL: {normalized_full_url}")
                                        self._check_link_status(normalized_full_url, url, results, is_internal=False)
                
                except Exception as e: # This block should ideally not be reached if the above try/except for self.bot.crawl() is comprehensive
                    error_message = f"YiraBot Crawl Error: {type(e).__name__} - {e}"
                    self.logger.error(f"Error crawling page {url}: {error_message}")
                    # Mark as broken if we couldn't crawl it
                    page_record = {
                        "url": normalized,
                        "status_code": 0,
                        "is_broken": True,
                        "error_message": error_message,
                        "referring_page": referring_url,
                        "is_internal": True, # Explicitly True for initial URL if current_depth == 1, otherwise determined by is_internal var
                        "crawl_depth": current_depth
                    }
                    if current_depth == 1: # Ensure initial URL record is marked internal
                        page_record["is_internal"] = True
                    results["all_pages"].append(page_record)
                    results["broken_links"].append({
                        "url": normalized,
                        "status_code": 0,
                        "error_message": error_message,
                        "referring_page": referring_url,
                        "is_internal": True # Explicitly True
                    })
                    
            else:
                # For external URLs, just validate HTTP status without crawling
                self.logger.debug(f"External URL: {url} - checking status code only (not crawling content)")
                results["external_urls"].add(normalized)
                self._check_link_status(normalized, referring_url, results, is_internal=False)
                
        except Exception as e:
            # Handle connection errors for individual pages
            error_message = str(e) # Keep this for the page_record
            self.logger.error(f"Error processing URL {url}: {type(e).__name__}: {e}", exc_info=True)
            
            # Create a page record for the error
            page_record = {
                "url": normalized,
                "status_code": 0,
                "is_broken": True,
                "error_message": error_message,
                "referring_page": referring_url,
                "is_internal": True if current_depth == 1 else is_internal, # Ensure initial URL is internal
                "crawl_depth": current_depth
            }
            
            # Add to all_pages and broken_links
            results["all_pages"].append(page_record)
            results["broken_links"].append({
                "url": normalized,
                "status_code": 0,
                "error_message": error_message,
                "referring_page": referring_url,
                "is_internal": True if current_depth == 1 else is_internal # Ensure initial URL is internal
            })
            
            # Add to appropriate URL set
            if is_internal:
                results["internal_urls"].add(normalized)
            else:
                results["external_urls"].add(normalized)
    
    def _capture_visual_baselines(self, website_id, results):
        """
        Capture visual snapshots of all internal URLs as baselines.
        
        Args:
            website_id (str): The website ID
            results (dict): The results dictionary with internal URLs
        """
        try:
            from src.snapshot_tool import save_visual_snapshot
            
            self.logger.info(f"Capturing visual baselines for {len(results['internal_urls'])} internal URLs")
            
            # Import required modules
            from datetime import datetime
            import os
            
            # Make sure we have a snapshots directory
            snapshot_dir = self.config.get("snapshot_directory", os.path.join("data", "snapshots"))
            os.makedirs(os.path.join(snapshot_dir, website_id), exist_ok=True)
            
            baseline_captures = []
            for url in results["internal_urls"]:
                try:
                    timestamp = datetime.now()
                    visual_path = save_visual_snapshot(website_id, url, timestamp)
                    
                    if visual_path:
                        # Ensure the path is relative to data directory for web UI display
                        if visual_path.startswith("data/"):
                            visual_path = visual_path[5:]  # Remove "data/" prefix
                            
                        # For Windows paths, convert backslashes to forward slashes
                        visual_path = visual_path.replace("\\", "/")
                            
                        baseline_captures.append({
                            "url": url,
                            "visual_path": visual_path,
                            "timestamp": timestamp.isoformat()
                        })
                        self.logger.debug(f"Created visual baseline for {url}: {visual_path}")
                    else:
                        self.logger.warning(f"Failed to create visual baseline for {url}")
                
                except Exception as e:
                    self.logger.error(f"Error creating visual baseline for {url}: {e}", exc_info=True)
            
            # Add baseline information to results
            results["visual_baselines"] = baseline_captures
            results["visual_baselines_count"] = len(baseline_captures)
            
        except ImportError:
            self.logger.error("Could not import snapshot_tool module for visual baselines")
        except Exception as e:
            self.logger.error(f"Error capturing visual baselines: {e}", exc_info=True)
            
    def _process_missing_meta_tags(self, url, seo_data, results):
        """Process SEO data from YiraBot to find missing meta tags."""
        # YiraBot returns some values as tuples (value, status). Handle that here
        title_len = seo_data.get('title_length', 0)
        if isinstance(title_len, (list, tuple)):
            title_len = title_len[0]

        meta_len = seo_data.get('meta_desc_length', 0)
        if isinstance(meta_len, (list, tuple)):
            meta_len = meta_len[0]

        # Check for missing or too short title
        if not title_len:
            results["missing_meta_tags"].append({
                "url": url,
                "tag_type": "Title",
                "suggestion": "Add a concise and descriptive title tag to improve SEO.",
                "importance": "critical",
                "title_content": None
            })
        elif title_len < 30:
            results["missing_meta_tags"].append({
                "url": url,
                "tag_type": "Title Length",
                "suggestion": "Title is too short. Consider adding more descriptive content (30-60 characters recommended).",
                "importance": "high",
                "title_content": seo_data.get('title_text', '')
            })
        elif title_len > 60:
            results["missing_meta_tags"].append({
                "url": url,
                "tag_type": "Title Length",
                "suggestion": "Title is too long. Consider shortening it to 30-60 characters for optimal display in search results.",
                "importance": "medium",
                "title_content": seo_data.get('title_text', '')
            })
            
        # Check for missing meta description
        if not meta_len:
            results["missing_meta_tags"].append({
                "url": url,
                "tag_type": "Description",
                "suggestion": "Create a compelling meta description to summarize the page content.",
                "importance": "high",
                "meta_content": None
            })
        elif meta_len < 120:
            results["missing_meta_tags"].append({
                "url": url,
                "tag_type": "Description Length",
                "suggestion": "Meta description is too short. Consider adding more descriptive content (120-160 characters recommended).",
                "importance": "medium",
                "meta_content": seo_data.get('meta_desc_text', '')
            })
        elif meta_len > 160:
            results["missing_meta_tags"].append({
                "url": url,
                "tag_type": "Description Length",
                "suggestion": "Meta description is too long. Consider shortening it to 120-160 characters for optimal display in search results.",
                "importance": "low",
                "meta_content": seo_data.get('meta_desc_text', '')
            })
            
        # Check for images without alt text
        for img in seo_data.get('images_without_alt', []):
            results["missing_meta_tags"].append({
                "url": url,
                "tag_type": "Alt Text",
                "suggestion": "Ensure all images have descriptive alt text for accessibility and SEO.",
                "importance": "high",
                "image_url": img if isinstance(img, str) else "Unknown image"
            })
            
        # Check for heading structure (if available)
        headings = seo_data.get('headings', ({}, ''))
        if isinstance(headings, (list, tuple)):
            headings = headings[0]
        if not getattr(headings, 'get', lambda x, y=0: y)('h1', 0):
            results["missing_meta_tags"].append({
                "url": url,
                "tag_type": "H1 Heading",
                "suggestion": "Add an H1 heading to improve page structure and SEO.",
                "importance": "high",
                "heading_content": None
            })
            
        # Check for canonical tag (if available)
        if not seo_data.get('has_canonical', True):
            results["missing_meta_tags"].append({
                "url": url,
                "tag_type": "Canonical URL",
                "suggestion": "Add a canonical URL tag to prevent duplicate content issues.",
                "importance": "medium",
                "canonical_content": None
            })
    
    def _check_link_status(self, url, referring_url, results, is_internal=True):
        """Check the status of a link and add it to all_pages and broken_links if applicable."""
        try:
            # Use proper HTTP request to check link
            import requests
            # SSLError, ConnectTimeout, ReadTimeout, ConnectionError, TooManyRedirects, RequestException are already imported at the top
            
            self.logger.debug(f"Checking link status for: {url}")
            
            # Set up retry mechanism
            max_retries = 5  # Increased from 3 to 5
            retry_delay = 1  # seconds
            status_code = 0
            error_msg = "Unknown error"
            content_type = None
            
            # Prepare headers with realistic user agent and referrer
            headers = {
                'User-Agent': self.user_agent,
                'Referer': referring_url,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache',
                'Accept-Encoding': 'gzip, deflate'  # Added Accept-Encoding
            }
            
            for attempt in range(max_retries):
                try:
                    # Different approach based on attempt number
                    if attempt < 2:
                        # First attempts: Try HEAD request (faster)
                        response = requests.head(
                            url,
                            timeout=10,
                            allow_redirects=True,
                            headers=headers,
                            verify=True  # SSL verification
                        )
                        
                        # Some servers don't support HEAD requests properly
                        if response.status_code in (405, 404, 403, 400):
                            # Method not allowed or common errors - try GET
                            self.logger.debug(f"HEAD request returned {response.status_code} for {url}, trying GET")
                            response = requests.get(
                                url,
                                timeout=15,
                                allow_redirects=True,
                                headers=headers,
                                verify=True
                            )
                    else:
                        # Later attempts: Try GET request with different settings
                        timeout = 20 if attempt < 3 else 30  # Longer timeout on later attempts
                        
                        # Try disabling SSL verification on later attempts if that might be the issue
                        verify = True if attempt < 4 else False
                        if not verify:
                            self.logger.debug(f"Trying with SSL verification disabled on attempt {attempt+1} for {url}")
                            # Suppress only the specific InsecureRequestWarning
                            import urllib3
                            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                        
                        # Use GET request for all later attempts
                        response = requests.get(
                            url,
                            timeout=timeout,
                            allow_redirects=True,
                            headers=headers,
                            verify=verify,
                            stream=True  # To avoid downloading entire content
                        )
                        
                        # Just get headers and close connection to avoid downloading full content
                        response.close()
                    
                    status_code = response.status_code
                    content_type = response.headers.get('Content-Type', '')
                    
                    # If successful, break the retry loop
                    if status_code < 400:
                        error_msg = "" # Clear previous error messages
                        break
                    
                    error_msg = f"HTTP Error: {status_code}"
                    
                    # Only retry server errors (5xx), not client errors (4xx)
                    if status_code < 500:
                        break

                except SSLError as e:
                    self.logger.error(f"Caught SSLError for {url}: {e}")
                    status_code = 0
                    error_msg = "SSL Certificate Error"
                except ConnectTimeout as e:
                    self.logger.error(f"Caught ConnectTimeout for {url}: {e}")
                    status_code = 0
                    error_msg = "Connection Timeout"
                except ReadTimeout as e:
                    self.logger.error(f"Caught ReadTimeout for {url}: {e}")
                    status_code = 0
                    error_msg = "Read Timeout"
                except ConnectionError as e:
                    self.logger.error(f"Caught ConnectionError for {url}: {e}")
                    status_code = 0
                    error_msg = "Connection Refused"
                except TooManyRedirects as e:
                    self.logger.error(f"Caught TooManyRedirects for {url}: {e}")
                    status_code = 0
                    error_msg = "Too Many Redirects"
                except RequestException as e:
                    self.logger.error(f"Caught RequestException for {url}: {e}")
                    status_code = 0
                    error_msg = f"Request Exception: {type(e).__name__}"
                    # Break on generic RequestException as retrying might not help
                    break
                    
                # If not the last attempt, wait before retrying (only if not a specific RequestException that broke the loop)
                if attempt < max_retries - 1:
                    # Increase delay with each retry (backoff strategy)
                    current_delay = retry_delay * (attempt + 1)
                    self.logger.debug(f"Retrying {url} in {current_delay}s (attempt {attempt+1}/{max_retries}) due to: {error_msg}")
                    import time
                    time.sleep(current_delay)
            
            # Create a page record
            page_record = {
                "url": url,
                "status_code": status_code,
                "content_type": content_type,
                "is_internal": is_internal,
                "referring_page": referring_url
            }
            
            # Add the page to all_pages list
            results["all_pages"].append(page_record)
            
            # If it's a broken link, also add it to broken_links
            if status_code == 0 or status_code >= 400:
                broken_link = {
                    "url": url,
                    "status_code": status_code,
                    "error_message": error_msg,
                    "referring_page": referring_url,
                    "is_internal": is_internal
                }
                results["broken_links"].append(broken_link)
                
                # Update the page record with error info
                page_record["is_broken"] = True
                page_record["error_message"] = error_msg
                
                self.logger.debug(f"Found broken link: {url} (Status: {status_code}, Error: {error_msg}) referenced from {referring_url}")
                
        except Exception as e:
            # Handle unexpected errors
            error_message_for_record = str(e) # Keep this for the page_record
            
            # Create a page record for the error
            page_record = {
                "url": url,
                "status_code": 0,
                "is_broken": True,
                "error_message": error_message,
                "referring_page": referring_url,
                "is_internal": is_internal
            }
            
            # Add to all_pages and broken_links
            results["all_pages"].append(page_record)
            results["broken_links"].append({
                "url": url,
                "status_code": 0,
                "error_message": error_message_for_record,
                "referring_page": referring_url,
                "is_internal": is_internal
            })
            
            self.logger.error(f"Error checking link {url}: {type(e).__name__}: {e}", exc_info=True)
    
    def _save_crawl_results(self, website_id, results):
        """Save crawl results to database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Make sure all_pages is properly populated
            if not results.get("all_pages") and (results.get("internal_urls") or results.get("external_urls")):
                self.logger.warning(f"all_pages list is empty but URLs were found - fixing before save")
                results["all_pages"] = []
                
                # Convert URL sets to page objects
                for url in results.get("internal_urls", set()):
                    results["all_pages"].append({
                        "url": url,
                        "status_code": 200,  # Assume good status for logged URLs
                        "is_internal": True,
                        "referring_page": results.get("url", "")
                    })
                
                for url in results.get("external_urls", set()):
                    results["all_pages"].append({
                        "url": url,
                        "status_code": 200,  # Assume good status for logged URLs
                        "is_internal": False,
                        "referring_page": results.get("url", "")
                    })
            
            # Remove duplicate URLs from all_pages
            self._remove_duplicate_urls(results)
            
            # Ensure total_pages_count is accurate
            total_pages = len(results.get("all_pages", []))
            self.logger.info(f"Saving crawl with {total_pages} total pages")
            
            # Convert set objects to lists for JSON serialization
            json_safe_results = results.copy()
            if "internal_urls" in json_safe_results and isinstance(json_safe_results["internal_urls"], set):
                json_safe_results["internal_urls"] = list(json_safe_results["internal_urls"])
            if "external_urls" in json_safe_results and isinstance(json_safe_results["external_urls"], set):
                json_safe_results["external_urls"] = list(json_safe_results["external_urls"])
            
            # Insert into crawl_history table
            cursor.execute(
                "INSERT INTO crawl_history (website_id, timestamp, broken_links_count, missing_meta_tags_count, total_pages_count, results_json) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    website_id,
                    results["timestamp"],
                    len(results.get("broken_links", [])),
                    len(results.get("missing_meta_tags", [])),
                    total_pages,
                    json.dumps(json_safe_results)
                )
            )
            
            # Get the ID of the newly inserted crawl record
            crawl_id = cursor.lastrowid
            
            # Insert all pages into the crawled_pages table
            for page in results["all_pages"]:
                cursor.execute(
                    "INSERT INTO crawled_pages (crawl_id, website_id, url, status_code, is_broken, error_message, referring_page) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        crawl_id,
                        website_id,
                        page["url"],
                        page["status_code"],
                        page.get("is_broken", False),
                        page.get("error_message", None),
                        page["referring_page"]
                    )
                )
            
            conn.commit()
            self.logger.info(f"Saved crawl results for website ID {website_id} with {len(results['all_pages'])} pages")
            
        except Exception as e:
            self.logger.error(f"Error saving crawl results: {e}", exc_info=True)
            conn.rollback()
            
        finally:
            conn.close()
    
    def _remove_duplicate_urls(self, results):
        """
        Remove duplicate URLs from the crawl results.
        
        Args:
            results (dict): Crawl results dictionary to clean
            
        Returns:
            None: Results are modified in-place
        """
        if not results.get("all_pages"):
            return
            
        # Use a set to track unique normalized URLs
        seen_urls = set()
        unique_pages = []
        
        all_current_pages = results.get("all_pages", [])
        successful_page_entries = [p for p in all_current_pages if not p.get("is_broken", False)]
        broken_page_entries = [p for p in all_current_pages if p.get("is_broken", False)]

        # Process successful pages first
        for page in successful_page_entries:
            norm = self._normalize_url(page["url"])
            if norm not in seen_urls:
                seen_urls.add(norm)
                unique_pages.append(page)
        
        # Then process broken pages, only adding if not already seen as successful
        for page in broken_page_entries:
            norm = self._normalize_url(page["url"])
            if norm not in seen_urls: # Only add if a successful version of this page wasn't already added
                seen_urls.add(norm) # Add to seen_urls here too, in case of multiple broken entries for the same URL
                unique_pages.append(page)
        
        # Replace the all_pages list with the deduplicated list
        results["all_pages"] = unique_pages
        
        # Also deduplicate broken_links
        if results.get("broken_links"):
            seen_broken_urls = set()
            unique_broken_links = []
            
            for link in results["broken_links"]:
                norm = self._normalize_url(link["url"])
                if norm not in seen_broken_urls:
                    seen_broken_urls.add(norm)
                    unique_broken_links.append(link)
            
            results["broken_links"] = unique_broken_links
        
        self.logger.info(f"Removed duplicates from crawl results. Final count: {len(results['all_pages'])} pages, {len(results.get('broken_links', []))} broken links")
    
    def get_latest_crawl_results(self, website_id):
        """
        Get the latest crawl results for a website.
        
        Args:
            website_id (str): The ID of the website.
            
        Returns:
            dict: The latest crawl results, or None if no results are found.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "SELECT id, results_json FROM crawl_history WHERE website_id = ? ORDER BY timestamp DESC LIMIT 1",
                (website_id,)
            )
            result = cursor.fetchone()
            
            if result:
                crawl_id, results_json = result
                results = json.loads(results_json)
                
                # Add the crawl_id to the results
                results["crawl_id"] = crawl_id
                
                return results
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting latest crawl results: {e}", exc_info=True)
            return None
            
        finally:
            conn.close()
    
    def get_pages_by_status_code(self, crawl_id, status_code=None):
        """
        Get pages with a specific status code from a crawl.
        
        Args:
            crawl_id (int): The ID of the crawl.
            status_code (int, optional): The status code to filter by. If None, returns all pages.
            
        Returns:
            list: A list of pages with the specified status code.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            if status_code is not None:
                cursor.execute(
                    "SELECT url, status_code, is_broken, error_message, referring_page FROM crawled_pages " 
                    "WHERE crawl_id = ? AND status_code = ? ORDER BY url",
                    (crawl_id, status_code)
                )
            else:
                cursor.execute(
                    "SELECT url, status_code, is_broken, error_message, referring_page FROM crawled_pages " 
                    "WHERE crawl_id = ? ORDER BY url",
                    (crawl_id,)
                )
                
            pages = []
            for row in cursor.fetchall():
                pages.append({
                    "url": row[0],
                    "status_code": row[1],
                    "is_broken": bool(row[2]),
                    "error_message": row[3] or "",
                    "referring_page": row[4]
                })
                
            return pages
                
        except Exception as e:
            self.logger.error(f"Error getting pages by status code: {e}", exc_info=True)
            return []
            
        finally:
            conn.close()
    
    def get_status_code_counts(self, crawl_id):
        """
        Get counts of pages by status code for a specific crawl.
        
        Args:
            crawl_id (int): The ID of the crawl.
            
        Returns:
            dict: A dictionary mapping status codes to counts.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "SELECT status_code, COUNT(*) as count FROM crawled_pages " 
                "WHERE crawl_id = ? GROUP BY status_code ORDER BY status_code",
                (crawl_id,)
            )
                
            status_counts = {}
            for row in cursor.fetchall():
                status_counts[row[0]] = row[1]
                
            return status_counts
                
        except Exception as e:
            self.logger.error(f"Error getting status code counts: {e}", exc_info=True)
            return {}
            
        finally:
            conn.close()
            
    def get_crawl_history(self, website_id, limit=10):
        """
        Get the crawl history for a website.
        
        Args:
            website_id (str): The ID of the website.
            limit (int, optional): The maximum number of records to return. Defaults to 10.
            
        Returns:
            list: A list of crawl history records, with the most recent first.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "SELECT id, timestamp, broken_links_count, missing_meta_tags_count, total_pages_count FROM crawl_history " 
                "WHERE website_id = ? ORDER BY timestamp DESC LIMIT ?",
                (website_id, limit)
            )
            records = []
            
            for row in cursor.fetchall():
                records.append({
                    "id": row[0],
                    "timestamp": row[1],
                    "broken_links_count": row[2],
                    "missing_meta_tags_count": row[3],
                    "total_pages_count": row[4]
                })
                
            return records
            
        except Exception as e:
            self.logger.error(f"Error getting crawl history: {e}", exc_info=True)
            return []
            
        finally:
            conn.close()
            
    def get_crawl_stats(self, website_id=None):
        """
        Get statistics about crawl results.
        
        Args:
            website_id (str, optional): If provided, get stats only for this website.
            
        Returns:
            dict: Statistics about crawl results.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            if website_id:
                # Stats for a specific website
                cursor.execute(
                    "SELECT COUNT(*), SUM(broken_links_count), SUM(missing_meta_tags_count), SUM(total_pages_count) "
                    "FROM crawl_history WHERE website_id = ?",
                    (website_id,)
                )
                row = cursor.fetchone()
                
                if row and row[0] > 0:
                    return {
                        "total_crawls": row[0],
                        "total_broken_links": row[1] or 0,
                        "total_missing_meta_tags": row[2] or 0,
                        "total_pages_crawled": row[3] or 0
                    }
                else:
                    return {
                        "total_crawls": 0,
                        "total_broken_links": 0,
                        "total_missing_meta_tags": 0,
                        "total_pages_crawled": 0
                    }
                    
            else:
                # Overall stats for all websites
                cursor.execute(
                    "SELECT COUNT(*), SUM(broken_links_count), SUM(missing_meta_tags_count), SUM(total_pages_count) FROM crawl_history"
                )
                row = cursor.fetchone()
                
                # Get stats per website
                cursor.execute(
                    "SELECT website_id, COUNT(*), SUM(broken_links_count), SUM(missing_meta_tags_count), SUM(total_pages_count) "
                    "FROM crawl_history GROUP BY website_id"
                )
                site_stats = {}
                
                for site_row in cursor.fetchall():
                    site_stats[site_row[0]] = {
                        "total_crawls": site_row[1],
                        "total_broken_links": site_row[2] or 0,
                        "total_missing_meta_tags": site_row[3] or 0,
                        "total_pages_crawled": site_row[4] or 0
                    }
                
                if row and row[0] > 0:
                    return {
                        "total_crawls": row[0],
                        "total_broken_links": row[1] or 0,
                        "total_missing_meta_tags": row[2] or 0,
                        "total_pages_crawled": row[3] or 0,
                        "site_stats": site_stats
                    }
                else:
                    return {
                        "total_crawls": 0,
                        "total_broken_links": 0,
                        "total_missing_meta_tags": 0,
                        "total_pages_crawled": 0,
                        "site_stats": {}
                    }
                    
        except Exception as e:
            self.logger.error(f"Error getting crawl stats: {e}", exc_info=True)
            return {
                "total_crawls": 0,
                "total_broken_links": 0,
                "total_missing_meta_tags": 0,
                "total_pages_crawled": 0,
                "error": str(e)
            }
            
        finally:
            conn.close() 