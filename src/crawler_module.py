import os
import sys
import time
import json
import hashlib
import requests
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, urlunparse
from typing import Dict, List, Any, Optional, Tuple
import sqlite3
from src.website_manager_sqlite import WebsiteManager

import re

from src.greenflare_crawler import GreenflareWrapper, GREENFLARE_AVAILABLE
from src.logger_setup import setup_logging
from src.config_loader import get_config
from src.comparators import compare_screenshots_percentage, compare_screenshots_ssim, OPENCV_SKIMAGE_AVAILABLE
from src.path_utils import get_database_path, ensure_directory_exists

logger = setup_logging()

class CrawlerModule:
    def __init__(self, config_path=None):
        self.logger = logger
        self.config = get_config(config_path=config_path)
        
        if GREENFLARE_AVAILABLE:
            self.logger.info("Using official Greenflare crawler implementation")
        else:
            self.logger.info("Using fallback Greenflare crawler implementation")
        
        self.bot = GreenflareWrapper(
            user_agent=self.config.get('user_agent', 'Website Monitoring System Crawler/1.0'),
            retries=self.config.get('greenflare_retries', 3),
            backoff_base=self.config.get('greenflare_backoff_base', 0.3),
            timeout=self.config.get('greenflare_timeout', 30),
            max_depth=self.config.get('max_crawl_depth', 3),
            respect_robots=self.config.get('respect_robots_txt', True),
            check_external_links=self.config.get('check_external_links', True)
        )
        
        # Initialize website manager (use SQLite version)
        from src.website_manager_sqlite import WebsiteManagerSQLite
        self.website_manager = WebsiteManagerSQLite(config_path=config_path)
        
        # Initialize database
        self._initialize_database()
        
    def _initialize_database(self):
        """Initialize the SQLite database for storing crawler results."""
        # Use centralized path resolution
        self.db_path = get_database_path()
        # Ensure the directory exists (db_path is a string)
        db_dir = os.path.dirname(self.db_path)
        ensure_directory_exists(db_dir)
        
        self.logger.info(f"Database path: {self.db_path}")
        
        # Create tables if they don't exist and configure SQLite to reduce lock contention
        conn = sqlite3.connect(self.db_path, timeout=30)
        try:
            cursor = conn.cursor()
            # Enable WAL for better concurrency and set a reasonable busy timeout
            try:
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute("PRAGMA synchronous=NORMAL;")
                cursor.execute("PRAGMA busy_timeout=5000;")
            except Exception:
                pass
            
            # Check if we need to run migrations
            # self._check_and_migrate_schema(cursor)  # Comment out this line
            
            # Legacy/history table (kept for compatibility)
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
            
            # New normalized tables used by crawler and reporting
            cursor.execute('CREATE TABLE IF NOT EXISTS crawl_results (id INTEGER PRIMARY KEY, website_id TEXT, url TEXT, timestamp TEXT, pages_crawled INTEGER, broken_links_count INTEGER, missing_meta_tags_count INTEGER, crawl_data TEXT)')
            cursor.execute('CREATE TABLE IF NOT EXISTS broken_links (id INTEGER PRIMARY KEY, crawl_id INTEGER, url TEXT, status_code INTEGER, referring_page TEXT, error_type TEXT, error_message TEXT, is_internal BOOLEAN, FOREIGN KEY (crawl_id) REFERENCES crawl_results (id))')
            cursor.execute('CREATE TABLE IF NOT EXISTS missing_meta_tags (id INTEGER PRIMARY KEY, crawl_id INTEGER, url TEXT, type TEXT, element TEXT, details TEXT, FOREIGN KEY (crawl_id) REFERENCES crawl_results (id))')
            
            conn.commit()
            self.logger.info("Database schema initialized successfully (WAL enabled, tables ensured).")
        except Exception as e:
            self.logger.error(f"Error initializing database schema: {e}", exc_info=True)
        finally:
            conn.close()
        
        self.logger.info("CrawlerModule initialized with enhanced Greenflare crawler")
        
    def _check_and_migrate_schema(self, cursor):
        """Check and migrate database schema if needed."""
        try:
            # Check if crawl_history table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='crawl_history'")
            if not cursor.fetchone():
                self.logger.info("Creating crawl_history table...")
                cursor.execute('''
                CREATE TABLE crawl_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    website_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    broken_links_count INTEGER DEFAULT 0,
                    missing_meta_tags_count INTEGER DEFAULT 0,
                    total_pages_count INTEGER DEFAULT 0,
                    results_json TEXT
                )
                ''')
                self.logger.info("crawl_history table created successfully.")
            else:
                self.logger.debug("crawl_history table already exists.")
                
        except Exception as e:
            self.logger.error(f"Error during schema migration: {e}")
            # Don't raise the exception, just log it
            pass

    def _get_db_connection(self):
        """Get database connection using centralized path resolution."""
        db_path = get_database_path()
        # Ensure the directory exists (db_path is a string)
        db_dir = os.path.dirname(db_path)
        ensure_directory_exists(db_dir)
        conn = sqlite3.connect(str(db_path))
        return conn

    def _init_db_schema(self):
        conn = self._get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('CREATE TABLE IF NOT EXISTS crawl_results (id INTEGER PRIMARY KEY, website_id TEXT, url TEXT, timestamp TEXT, pages_crawled INTEGER, broken_links_count INTEGER, missing_meta_tags_count INTEGER, crawl_data TEXT)')
            cursor.execute('CREATE TABLE IF NOT EXISTS broken_links (id INTEGER PRIMARY KEY, crawl_id INTEGER, url TEXT, status_code INTEGER, referring_page TEXT, error_type TEXT, error_message TEXT, is_internal BOOLEAN, FOREIGN KEY (crawl_id) REFERENCES crawl_results (id))')
            cursor.execute('CREATE TABLE IF NOT EXISTS missing_meta_tags (id INTEGER PRIMARY KEY, crawl_id INTEGER, url TEXT, type TEXT, element TEXT, details TEXT, FOREIGN KEY (crawl_id) REFERENCES crawl_results (id))')
            conn.commit()
            self.logger.info("Database schema initialized successfully.")
        except Exception as e:
            self.logger.error(f"Error initializing database schema: {e}", exc_info=True)
        finally:
            conn.close()

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
    
    def _should_exclude_url_for_checks(self, url: str, check_type: str = "all", website_id: str = None) -> bool:
        """
        Return True if the URL should be excluded from specific checks (visual, blur, baseline).
        This helps save resources by skipping resource-intensive checks on non-essential pages.
        
        Args:
            url (str): The URL to check
            check_type (str): Type of check ("visual", "blur", "baseline", "all")
            website_id (str): Optional website ID to check for per-site exclude pages
        
        Returns:
            bool: True if URL should be excluded from the specified check type
        """
        # First, check per-site exclude pages if website_id is provided
        if website_id:
            website = self.website_manager.get_website(website_id)
            if website and website.get('exclude_pages_keywords'):
                exclude_keywords = website['exclude_pages_keywords']
                self.logger.debug(f"Using per-site exclude keywords for website {website_id}: {exclude_keywords}")
            else:
                # Fall back to global config
                exclude_keywords = self.config.get('exclude_pages_keywords', ['products', 'blogs', 'blog', 'product'])
                self.logger.debug(f"Using global exclude keywords for website {website_id}: {exclude_keywords}")
        else:
            # Use global config only
            exclude_keywords = self.config.get('exclude_pages_keywords', ['products', 'blogs', 'blog', 'product'])
            self.logger.debug(f"Using global exclude keywords: {exclude_keywords}")
        
        # Convert to lowercase for case-insensitive matching
        url_lower = url.lower()
        
        # Check if URL contains any exclude keywords
        for keyword in exclude_keywords:
            if keyword.lower() in url_lower:
                self.logger.debug(f"Excluding URL from {check_type} checks due to keyword '{keyword}': {url}")
                return True
        
        return False
        
    def crawl_website(self, website_id, url, check_config=None, is_scheduled=False, **options):
        """
        Crawl a website to detect broken links and missing meta tags.
        Enhanced with single-site processing and rate limiting.
        
        Args:
            website_id (str): The ID of the website to crawl.
            url (str): The URL of the website to crawl.
            check_config (dict, optional): Configuration for the check.
            is_scheduled (bool, optional): Whether this is a scheduled check.
            **options: Additional options for crawling.
            
        Returns:
            dict: Results of the crawl, including broken links and missing meta tags.
        """
        # Get single-site processing configuration
        single_site_config = self.config.get('single_site_processing', {})
        request_delay = single_site_config.get('request_delay_seconds', 2)
        check_delay = single_site_config.get('check_delay_seconds', 5)
        retry_attempts = single_site_config.get('retry_attempts', 3)
        retry_delay = single_site_config.get('retry_delay_seconds', 10)
        
        self.logger.info(f"🚀 Starting SINGLE-SITE crawl of website ID {website_id}: {url}")
        self.logger.info(f"⚙️ Rate limiting: {request_delay}s between requests, {check_delay}s between checks")
        
        # Get appropriate configuration
        if check_config is None:
            if is_scheduled:
                check_config = self.website_manager.get_automated_check_config(website_id)
                if not check_config:
                    self.logger.error(f"Could not get automated check config for website {website_id}")
                    return {"website_id": website_id, "url": url, "timestamp": datetime.now().isoformat(), "error": "Website not found"}
            else:
                # For manual checks, use the proper manual check configuration
                check_config = self.website_manager.get_manual_check_config(website_id, options.get('check_type', 'full'))
                if not check_config:
                    self.logger.error(f"Could not get manual check config for website {website_id}")
                    return {"website_id": website_id, "url": url, "timestamp": datetime.now().isoformat(), "error": "Website not found"}
                self.logger.info(f"Using manual check configuration for website {website_id}: {check_config}")
        
        # Store the original options to pass down to check methods
        original_options = dict(options)
        original_options['check_config'] = check_config
        original_options['performance_check_only'] = options.get('performance_check_only', False)
        original_options['visual_check_only'] = options.get('visual_check_only', False)
        original_options['blur_check_only'] = options.get('blur_check_only', False)
        original_options['is_scheduled'] = is_scheduled
        
        # Legacy support for old parameter names
        create_baseline = options.get('create_baseline', False)
        crawl_only = not check_config.get('visual_enabled', True) and not check_config.get('blur_enabled', False) and not check_config.get('performance_enabled', False)
        visual_check_only = not check_config.get('crawl_enabled', True) and check_config.get('visual_enabled', True) and not check_config.get('blur_enabled', False) and not check_config.get('performance_enabled', False)
        blur_check_only = not check_config.get('crawl_enabled', True) and not check_config.get('visual_enabled', True) and check_config.get('blur_enabled', True) and not check_config.get('performance_enabled', False)
        
        self.logger.info(f"Check configuration: {check_config} (scheduled: {is_scheduled})")

        results = {
            "website_id": website_id, "url": url, "timestamp": datetime.now().isoformat(),
            "broken_links": [], "missing_meta_tags": [], "all_pages": [],
            "internal_urls": set(), "external_urls": set(), "processed_urls": set(),
            "visual_baselines": [], "latest_snapshots": {},
            "crawl_stats": {"pages_crawled": 0, "total_links": 0, "total_images": 0, "status_code_counts": {}, "sitemap_found": False},
            "check_config": check_config
        }
        
        try:
            # If this is a visual check only, we don't need to crawl the whole site.
            # We just need to check the single URL provided.
            if visual_check_only:
                self.logger.info(f"Performing visual-only check for {url}. Crawling is skipped.")
                # Manually add the main page to the list of pages to be processed for snapshots.
                # This simulates a crawl result for a single page.
                page_record = {
                    "url": url, 
                    "status_code": 200, # Assume it's reachable
                    "title": "Visual Check Target", 
                    "is_internal": True, 
                    "referring_page": None,
                    "meta": {},
                    "images": []
                }
                results["all_pages"].append(page_record)
                results["processed_urls"].add(url)
                results["internal_urls"].add(url)
                results["crawl_stats"]["pages_crawled"] = 1

            elif blur_check_only:
                self.logger.info(f"Performing blur-only check for {url}. Checking for existing crawl data first.")
                
                # Try to get existing crawl results first
                existing_results = self.get_latest_crawl_results(website_id)
                
                # Check if existing results have images for blur detection
                has_images = False
                if existing_results and existing_results.get('all_pages'):
                    # Safely calculate total images, handling None values
                    total_images = 0
                    for page in existing_results['all_pages']:
                        page_images = page.get('images', [])
                        if page_images is not None:
                            total_images += len(page_images)
                    
                    if total_images > 0:
                        has_images = True
                        self.logger.info(f"Using existing crawl data for blur detection ({len(existing_results['all_pages'])} pages, {total_images} images)")
                        # Use existing crawl data - no new crawling needed
                        results["all_pages"] = existing_results['all_pages']
                        results["processed_urls"] = set(page['url'] for page in existing_results['all_pages'])
                        results["internal_urls"] = set(page['url'] for page in existing_results['all_pages'] if page.get('is_internal'))
                        results["external_urls"] = set(page['url'] for page in existing_results['all_pages'] if not page.get('is_internal'))
                        results["crawl_stats"]["pages_crawled"] = len(existing_results['all_pages'])
                    else:
                        self.logger.info(f"Existing crawl data found but contains no images ({len(existing_results['all_pages'])} pages, {total_images} images). Running new crawl for blur detection.")
                
                if not has_images:
                    self.logger.info("No existing crawl data found for blur detection. Running minimal crawl to collect image data.")
                    # For blur-only checks, run a minimal crawl if no existing data
                    greenflare_config = {
                        'start_urls': [url], 
                        'max_depth': min(options.get('max_depth', 2), 2),  # Limit depth for blur-only checks
                        'respect_robots_txt': options.get('respect_robots', True), 
                        'check_external_links': False,  # Don't check external links for blur-only
                        'extract_images': True,  # Essential for blur detection
                        'extract_alt_text': True,  # Also useful for accessibility
                        'meta_tags': self.config.get('meta_tags_to_check', ["title", "description"])  # Use configured meta tags for blur-only
                    }
                    
                    crawler = self.bot.configure(greenflare_config)
                    
                    start_time = time.time()
                    crawl_results = crawler.run()
                    self.logger.info(f"Minimal crawl for blur detection completed in {time.time() - start_time:.2f} seconds.")
                    
                    for page in crawl_results.get('pages', []):
                        self._process_page(page, results, url)

            else:
                # Full crawl logic remains the same
                greenflare_config = {
                    'start_urls': [url], 
                    'max_depth': options.get('max_depth', 2), 
                    'respect_robots_txt': options.get('respect_robots', True), 
                    'check_external_links': options.get('check_external_links', True),
                    'extract_images': True,  # Enable image extraction for blur detection
                    'extract_alt_text': True,  # Also extract alt text for accessibility checks
                                            'meta_tags': self.config.get('meta_tags_to_check', ["title", "description"])  # Use configured meta tags
                }
                
                # Run crawl if crawl is enabled OR performance check is enabled (need pages for performance analysis)
                performance_enabled = check_config.get('performance_enabled', False) or options.get('performance_check_only', False)
                
                if check_config.get('crawl_enabled', True) or performance_enabled:
                    # Use appropriate crawl depth based on check type
                    if performance_enabled and not check_config.get('crawl_enabled', True):
                        # For performance-only checks, use limited depth but still discover pages
                        greenflare_config['max_depth'] = min(greenflare_config.get('max_depth', 2), 2)
                        self.logger.info(f"Running crawl for performance check with max_depth={greenflare_config['max_depth']}")
                    
                    crawler = self.bot.configure(greenflare_config)
                    
                    start_time = time.time()
                    crawl_results = crawler.run()
                    self.logger.info(f"Crawl completed in {time.time() - start_time:.2f} seconds.")
                    
                    for page in crawl_results.get('pages', []):
                        self._process_page(page, results, url)
                else:
                    self.logger.info("Crawling disabled for this check - using existing data or single page")
                    
                    # Check if we need to extract images for blur detection
                    need_images = (check_config.get('blur_enabled', False) or 
                                 blur_check_only or 
                                 options.get('check_config', {}).get('blur_enabled', False))
                    
                    if need_images:
                        self.logger.info("Extracting images from main page for blur detection")
                        # Use minimal crawler to get images from the main page
                        minimal_config = {
                            'start_urls': [url], 
                            'max_depth': 1,  # Only main page
                            'respect_robots_txt': options.get('respect_robots', True), 
                            'check_external_links': False,
                            'extract_images': True,  # Essential for blur detection
                            'extract_alt_text': True,
                            'meta_tags': ["title"]  # Minimal meta tags
                        }
                        
                        try:
                            crawler = self.bot.configure(minimal_config)
                            crawl_results = crawler.run()
                            
                            # Process the main page to get images
                            if crawl_results.get('pages'):
                                main_page = crawl_results['pages'][0]
                                self._process_page(main_page, results, url)
                                self.logger.info(f"Extracted {len(main_page.get('images', []))} images from main page")
                            else:
                                # Fallback to empty page if extraction fails
                                page_record = {
                                    "url": url, 
                                    "status_code": 200, 
                                    "title": "Main Page", 
                                    "is_internal": True, 
                                    "referring_page": None,
                                    "meta": {},
                                    "images": []
                                }
                                results["all_pages"].append(page_record)
                                results["processed_urls"].add(url)
                                results["internal_urls"].add(url)
                                results["crawl_stats"]["pages_crawled"] = 1
                        except Exception as e:
                            self.logger.error(f"Error extracting images from main page: {e}")
                            # Fallback to empty page
                            page_record = {
                                "url": url, 
                                "status_code": 200, 
                                "title": "Main Page", 
                                "is_internal": True, 
                                "referring_page": None,
                                "meta": {},
                                "images": []
                            }
                            results["all_pages"].append(page_record)
                            results["processed_urls"].add(url)
                            results["internal_urls"].add(url)
                            results["crawl_stats"]["pages_crawled"] = 1
                    else:
                        # For checks that don't need images, use the simple page record
                        page_record = {
                            "url": url, 
                            "status_code": 200, 
                            "title": "Main Page", 
                            "is_internal": True, 
                            "referring_page": None,
                            "meta": {},
                            "images": []
                        }
                        results["all_pages"].append(page_record)
                        results["processed_urls"].add(url)
                        results["internal_urls"].add(url)
                        results["crawl_stats"]["pages_crawled"] = 1

            results["crawl_stats"]["total_links"] = len(results["internal_urls"]) + len(results["external_urls"])

            # Debug logging for check types
            self.logger.info(f"Check type flags - crawl_only: {crawl_only}, visual_check_only: {visual_check_only}, blur_check_only: {blur_check_only}")

            # Run visual checks if enabled
            # For visual-only checks, always run visual comparison regardless of other check types
            visual_check_only = options.get('visual_check_only', False)
            if check_config.get('visual_enabled', True) and not crawl_only and (not blur_check_only or visual_check_only):
                if create_baseline:
                    self.logger.info(f"Creating visual baselines for website {website_id}")
                    self._create_visual_baselines(results)
                else:
                    # Check if baselines exist before doing visual check
                    website_config = self.website_manager.get_website(website_id)
                    all_baselines = website_config.get('all_baselines', {}) if website_config else {}
                    
                    if not all_baselines:
                        # No baselines exist, return error message
                        self.logger.warning(f"No baselines found for website {website_id}. Cannot perform visual check.")
                        results['error'] = "Please first create baselines, then do the visual check."
                        results['status'] = 'error'
                        return results
                    else:
                        self.logger.info(f"Found {len(all_baselines)} baselines for website {website_id}. Proceeding with visual check.")
                        self.logger.info(f"Capturing latest snapshots for website {website_id}")
                        self._capture_latest_snapshots(results)
            else:
                self.logger.info(f"Skipping visual snapshots - visual_enabled: {check_config.get('visual_enabled', True)}, crawl_only: {crawl_only}, blur_check_only: {blur_check_only}, visual_check_only: {visual_check_only}")
            
            # IMPORTANT: For baseline creation, we still need to run other checks (crawl, blur, performance)
            # even though we created visual baselines above. This ensures comprehensive baseline data.

            # Save crawl results first to get crawl_id
            crawl_id = self._save_crawl_results(results)
            results['crawl_id'] = crawl_id

            # Run blur detection if enabled for this website (after saving to get crawl_id)
            blur_enabled = check_config.get('blur_enabled', False)
            self.logger.info(f"Blur check evaluation - blur_check_only: {blur_check_only}, blur_enabled: {blur_enabled}")
            
            # Add delay between check types for single-site processing
            if check_delay > 0:
                self.logger.info(f"⏳ Waiting {check_delay}s before running blur detection...")
                time.sleep(check_delay)
            
            if blur_check_only:
                # For blur-only checks, always run blur detection regardless of website settings
                self.logger.info(f"Running blur-only check for website {website_id}")
                self._run_blur_detection_for_blur_check(results, website_id, original_options)
            elif blur_enabled:
                # For other checks, run blur detection if enabled in configuration
                self.logger.info(f"Running blur detection (enabled in config) for website {website_id}")
                self._run_blur_detection_if_enabled(results, website_id, original_options)
            else:
                self.logger.debug(f"Blur detection disabled - blur_check_only: {blur_check_only}, blur_enabled: {blur_enabled}")
            
            # Add delay between check types for single-site processing
            if check_delay > 0:
                self.logger.info(f"⏳ Waiting {check_delay}s before running performance check...")
                time.sleep(check_delay)
            
            # Run performance checks if enabled
            performance_enabled = check_config.get('performance_enabled', False)
            performance_check_only = options.get('performance_check_only', False)
            self.logger.info(f"Performance check evaluation - performance_enabled: {performance_enabled}, performance_check_only: {performance_check_only}, check_config: {check_config}")
            
            # For performance-only checks, always run regardless of other settings
            # For other checks, only run if performance is enabled in the check configuration
            if performance_check_only or performance_enabled:
                self.logger.info(f"Running performance check for website {website_id} (performance_check_only: {performance_check_only}, performance_enabled: {performance_enabled})")
                self._run_performance_check_if_enabled(results, website_id, original_options)
            else:
                self.logger.debug(f"Performance check disabled - performance_enabled: {performance_enabled}, performance_check_only: {performance_check_only}")

            results["internal_urls"] = list(results["internal_urls"])
            results["external_urls"] = list(results["external_urls"])
            self.logger.info(f"Crawl of {url} completed. Found {len(results['broken_links'])} broken links.")
            
            # Add cleanup delay for single-site processing
            cleanup_delay = single_site_config.get('cleanup_delay_seconds', 2)
            if cleanup_delay > 0:
                self.logger.info(f"🧹 Cleanup delay: {cleanup_delay}s before next site...")
                time.sleep(cleanup_delay)
            
            # Email notifications are handled by the scheduler after all checks are complete
            # This ensures emails contain complete data from all check types
            self.logger.info(f"Crawl completed for website {website_id}. Email will be sent after all checks are complete.")
            
            # For individual check types, send email immediately
            if visual_check_only or blur_check_only or performance_check_only or crawl_only:
                # Get website object for email notification
                website = self.website_manager.get_website(website_id)
                if website:
                    # Determine the check type for email notification
                    if visual_check_only:
                        check_type_name = "visual"
                    elif blur_check_only:
                        check_type_name = "blur"
                    elif performance_check_only:
                        check_type_name = "performance"
                    elif crawl_only:
                        check_type_name = "crawl"
                    else:
                        check_type_name = "check"
                    
                    self.logger.info(f"Sending individual {check_type_name} email notification for website {website_id}")
                    self._send_single_check_email_notification(website, results, check_type_name)
                else:
                    self.logger.warning(f"Could not load website {website_id} for email notification")
            
            return results
                
        except Exception as e:
            self.logger.error(f"Error during crawl of {url}: {e}", exc_info=True)
            return {"website_id": website_id, "url": url, "timestamp": datetime.now().isoformat(), "error": str(e)}

    def _process_page(self, page, results, base_url):
        normalized_url = self._normalize_url(page.get('url'))
        if not normalized_url or normalized_url in results['processed_urls']:
            return
        results['processed_urls'].add(normalized_url)
        page['url'] = normalized_url

        is_internal = self._is_internal_url(normalized_url, base_url)
        (results["internal_urls"] if is_internal else results["external_urls"]).add(normalized_url)

        page_record = {"url": normalized_url, "status_code": page.get('status_code'), "title": page.get('title', ''), "is_internal": is_internal, "referring_page": page.get('referring_page', ''), "meta": page.get('meta'), "images": page.get('images')}
        results["all_pages"].append(page_record)
        
        results["crawl_stats"]["pages_crawled"] += 1
        status_str = str(page.get('status_code') or 'unknown')
        results["crawl_stats"]["status_code_counts"][status_str] = results["crawl_stats"]["status_code_counts"].get(status_str, 0) + 1
        
        # Handle broken links
        status_code = page.get('status_code')
        if (status_code and (400 <= status_code < 600)) or page.get('is_broken'):
            results["broken_links"].append({"url": normalized_url, "status_code": status_code, "referring_page": page.get('referring_page', ''), "error_type": "HTTP Error" if status_code else "Connection Error", "error_message": page.get('error_message', ''), "is_internal": is_internal})
        
        # Handle missing meta tags
        page_missing_meta = page.get('missing_meta_tags', {})
        if page_missing_meta:
            for tag_type, details in page_missing_meta.items():
                # Generate appropriate suggestions based on tag type
                suggestion = self._get_meta_tag_suggestion(tag_type, details)
                
                results["missing_meta_tags"].append({
                    "url": normalized_url,
                    "tag_type": tag_type,  # Changed from "type" to "tag_type" to match template
                    "element": tag_type,
                    "details": details,
                    "suggestion": suggestion
                })

    def _create_visual_baselines(self, results):
        self.logger.info(f"DEBUG: _create_visual_baselines called for website {results.get('website_id')}")
        self._creating_baseline = True
        try:
            # Only create baselines for pages that will do visual checks
            self._handle_snapshots(results, is_baseline=True, visual_check_only=True)
            self.logger.info(f"DEBUG: _create_visual_baselines completed for website {results.get('website_id')}")
        finally:
            self._creating_baseline = False

    def _capture_latest_snapshots(self, results):
        self._handle_snapshots(results, is_baseline=False)

    def _handle_snapshots(self, results, is_baseline, visual_check_only=False):
        from src.snapshot_tool import save_visual_snapshot
        from src.comparators import compare_screenshots_percentage # Import our comparison function

        # Use the existing website_manager instance instead of creating a new one
        website_config = self.website_manager.get_website(results['website_id'])
        
        # Handle case where website_config is None
        if website_config is None:
            self.logger.error(f"Website config not found for ID: {results['website_id']}. Cannot capture snapshots.")
            return
            
        all_baselines = website_config.get('all_baselines', {})
        
        log_action = "baseline" if is_baseline else "latest"
        self.logger.info(f"Starting to capture {log_action} snapshots for website ID: {results['website_id']}")

        # --- FIX: Filter out direct links to images and excluded pages ---
        image_ext_pattern = re.compile(r'\.(png|jpg|jpeg|gif|webp|svg|bmp)$', re.IGNORECASE)
        
        if visual_check_only:
            # For baseline creation, only create baselines for pages that will do visual checks
            # This means excluding pages that would be excluded from visual checks
            pages_to_snapshot = [
                p for p in results.get('all_pages', []) 
                if (p.get('is_internal') and 
                    p.get('status_code') == 200 and 
                    not image_ext_pattern.search(p['url']) and
                    not self._should_exclude_url_for_checks(p['url'], 'visual', results['website_id']))
            ]
            self.logger.info(f"Creating baselines only for pages that will do visual checks: {len(pages_to_snapshot)} pages")
        else:
            # For regular visual checks, use all valid pages
            pages_to_snapshot = [
                p for p in results.get('all_pages', []) 
                if (p.get('is_internal') and 
                    p.get('status_code') == 200 and 
                    not image_ext_pattern.search(p['url']) and
                    not self._should_exclude_url_for_checks(p['url'], 'visual', results['website_id']))
            ]
        
        if not pages_to_snapshot:
            self.logger.warning(f"No valid internal pages found to capture {log_action} snapshots.")
            return
            
        snapshot_map = {}
        page_results = results.get('page_results', {}) # Get or create page_results

        for page in pages_to_snapshot:
            url = page['url']
            try:
                url_path = (urlparse(url).path.strip('/') or 'home').replace('/', '_')
                url_path = re.sub(r'\.(html|htm|php|aspx|jsp)$', '', url_path, flags=re.IGNORECASE).lower()

                # Save the snapshot (this part is the same for baseline and latest)
                snapshot_path = save_visual_snapshot(site_id=results['website_id'], url=url, is_baseline=is_baseline, url_path=url_path)
                
                if snapshot_path:
                    snapshot_map[url] = snapshot_path
                    # Ensure page_results has an entry for this URL
                    if url not in page_results:
                        page_results[url] = {}
                    
                    page_results[url]['url_path'] = url_path
                    
                    # If this is the main URL, update the top-level results dictionary
                    if url == results['url']:
                        key = 'baseline_visual_path' if is_baseline else 'latest_visual_snapshot_path'
                        results[key] = snapshot_path

                    # --- NEW COMPARISON LOGIC ---
                    # If we are capturing the LATEST snapshot (not creating a baseline)
                    if not is_baseline:
                        # Find the corresponding baseline path for this URL
                        # Try exact match first
                        baseline_info = all_baselines.get(url)
                        
                        # If no exact match, try normalized URL matching
                        if not baseline_info:
                            normalized_url = self._normalize_url(url)
                            for stored_url, stored_info in all_baselines.items():
                                if self._normalize_url(stored_url) == normalized_url:
                                    baseline_info = stored_info
                                    self.logger.info(f"Found baseline match using normalized URL: {stored_url} -> {url}")
                                    break
                        
                        if baseline_info and 'path' in baseline_info and os.path.exists(baseline_info['path']):
                            baseline_path = baseline_info['path']
                            self.logger.info(f"Comparing latest snapshot for {url} against baseline: {baseline_path}")

                            # Call the percentage comparison function
                            results['visual_diff_percent'], results['visual_diff_image_path'] = compare_screenshots_percentage(
                                image_path1=baseline_path,
                                image_path2=snapshot_path,
                                ignore_regions=self.website_manager.get_website(results['website_id']).get('ignore_regions', [])
                            )
                            
                            # Store the results
                            page_results[url]['visual_diff_percent'] = results['visual_diff_percent']
                            if url == results['url']: # If it's the main page, also store it at the top level
                                results['visual_diff_percent'] = results['visual_diff_percent']
                            
                            if results['visual_diff_image_path']:
                                page_results[url]['visual_diff_image_path'] = results['visual_diff_image_path']

                            self.logger.info(f"Visual comparison for {url} complete. Difference: {results['visual_diff_percent']:.2f}%")

                            # For backward compatibility and other potential checks, let's keep ssim if available.
                            if OPENCV_SKIMAGE_AVAILABLE:
                                results['ssim_score'] = compare_screenshots_ssim(
                                    image_path1=baseline_path,
                                    image_path2=snapshot_path
                                )
                        else:
                            # Only warn if we're not in baseline creation mode
                            if not hasattr(self, '_creating_baseline') or not self._creating_baseline:
                                self.logger.warning(f"No baseline found for URL {url} to compare against the latest snapshot.")
                    else:
                        # If we're creating baselines, log that baseline was created
                        self.logger.info(f"Baseline snapshot created for URL {url}: {snapshot_path}")

            except Exception as e:
                self.logger.error(f"Error processing snapshot for URL {url}: {e}", exc_info=True)
        
        # Update results with the detailed page_results
        results['page_results'] = page_results

        if is_baseline:
            results['visual_baselines'] = [{'url': u, 'path': p} for u, p in snapshot_map.items()]
            self.logger.info(f"DEBUG: About to call _update_website_with_baselines with {len(snapshot_map)} baselines")
            self._update_website_with_baselines(results['website_id'], snapshot_map)
            self.logger.info(f"DEBUG: _update_website_with_baselines completed")
        else:
            results['latest_snapshots'] = snapshot_map
        
        self.logger.info(f"Captured {len(snapshot_map)} {log_action} snapshots.")
    
    def _update_website_with_baselines(self, website_id, baselines_by_url):
        self.logger.info(f"DEBUG: _update_website_with_baselines called with website_id: {website_id}, baselines_by_url: {baselines_by_url}")
        if not baselines_by_url:
            self.logger.warning(f"DEBUG: No baselines to update for website {website_id}")
            return
            
        # Use the existing website_manager instance instead of creating a new one
        website = self.website_manager.get_website(website_id)
        
        if not website:
            return

        all_baselines = website.get("all_baselines", {})
        current_time = datetime.now(timezone.utc).isoformat()
        
        # Log baseline URLs for debugging
        self.logger.info(f"Processing {len(baselines_by_url)} baseline URLs: {list(baselines_by_url.keys())}")
        self.logger.info(f"Website main URL: {website.get('url')}")
        
        for url, path in baselines_by_url.items():
            all_baselines[url] = {'path': path, 'timestamp': current_time}
        
        self.logger.info(f"DEBUG: Storing all_baselines: {all_baselines}")
        updates = {"all_baselines": all_baselines, "has_subpage_baselines": True}
        
        # Enhanced logic to find the main page baseline
        website_url = website.get('url')
        main_baseline_path = None
        
        # First, try exact URL match
        if website_url in all_baselines:
            main_baseline_path = all_baselines[website_url]['path']
            self.logger.info(f"Found exact URL match for baseline: {website_url}")
        else:
            # Try to find the homepage by checking common variations
            homepage_candidates = [
                website_url,
                website_url.rstrip('/'),
                website_url + '/',
            ]
            
            # Also check for any URL that matches the domain and has 'home' in the path
            for url in all_baselines.keys():
                if url.startswith(website_url.rstrip('/')) and ('home' in url.lower() or url.rstrip('/') == website_url.rstrip('/')):
                    homepage_candidates.append(url)
            
            for candidate in homepage_candidates:
                if candidate in all_baselines:
                    main_baseline_path = all_baselines[candidate]['path']
                    self.logger.info(f"Found baseline match for candidate URL: {candidate}")
                    break
        
        # Update the main baseline path if found and not already set
        if main_baseline_path and not website.get('baseline_visual_path'):
            updates['baseline_visual_path'] = main_baseline_path
            updates['baseline_captured_utc'] = current_time
            self.logger.info(f"Updated baseline_visual_path: {main_baseline_path}")
        elif website.get('baseline_visual_path'):
            self.logger.info(f"Baseline already exists: {website.get('baseline_visual_path')}")
        else:
            self.logger.warning(f"Could not find main page baseline for website: {website_url}")
            self.logger.warning(f"Available baseline URLs: {list(all_baselines.keys())}")
        
        self.logger.info(f"DEBUG: About to update website {website_id} with updates: {updates}")
        result = self.website_manager.update_website(website_id, updates)
        self.logger.info(f"DEBUG: Website update result: {result}")
        
        # Verify the update worked
        updated_website = self.website_manager.get_website(website_id)
        self.logger.info(f"DEBUG: Updated website all_baselines: {updated_website.get('all_baselines', {})}")
            
    def _normalize_url(self, url):
        if not url:
            return url
        try:
            parsed = urlparse(url)
            path = parsed.path.rstrip('/') or '/'
            return urlunparse((parsed.scheme, parsed.netloc.lower(), path, parsed.params, parsed.query, parsed.fragment))
        except Exception:
            return url
    
    def _is_internal_url(self, url, base_url):
        if not url:
            return False
        try:
            return urlparse(url).netloc.lower().replace('www.', '') == urlparse(base_url).netloc.lower().replace('www.', '')
        except:
            return False
    
    def _get_meta_tag_suggestion(self, tag_type, details):
        """Generate appropriate suggestions for missing meta tags."""
        suggestions = {
            'title': 'Add a descriptive page title between 30-60 characters that accurately describes the page content.',
            'description': 'Add a meta description between 120-160 characters that summarizes the page content and encourages clicks.',
            'keywords': 'Add relevant meta keywords (though less important for SEO, still useful for content organization).',
            'robots': 'Add meta robots tag to control how search engines crawl and index this page.',
            'canonical': 'Add canonical URL to prevent duplicate content issues.',
            'h1': 'Add an H1 heading tag that clearly describes the main topic of the page.',
            'alt_text': 'Add descriptive alt text to images for accessibility and SEO benefits.'
        }
        
        # Handle specific cases based on details
        if 'too short' in details.lower():
            if tag_type == 'title':
                return 'Expand the title to be more descriptive (recommended: 30-60 characters).'
            elif tag_type == 'description':
                return 'Expand the meta description to better describe the page (recommended: 120-160 characters).'
        elif 'too long' in details.lower():
            if tag_type == 'title':
                return 'Shorten the title to improve readability (recommended: 30-60 characters).'
            elif tag_type == 'description':
                return 'Shorten the meta description to fit search result displays (recommended: 120-160 characters).'
        
        return suggestions.get(tag_type, f'Add the missing {tag_type} tag to improve SEO and accessibility.')
                
    def _save_crawl_results(self, results):
        conn = self._get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO crawl_results (website_id, url, timestamp, pages_crawled, broken_links_count, missing_meta_tags_count, crawl_data) VALUES (?, ?, ?, ?, ?, ?, ?)',
                           (results["website_id"], results["url"], results["timestamp"], results["crawl_stats"]["pages_crawled"], len(results["broken_links"]), len(results["missing_meta_tags"]), json.dumps({"crawl_stats": results["crawl_stats"], "all_pages": results["all_pages"]})))
            crawl_id = cursor.lastrowid
            
            for link in results.get("broken_links", []):
                cursor.execute('INSERT INTO broken_links (crawl_id, url, status_code, referring_page, error_type, error_message, is_internal) VALUES (?, ?, ?, ?, ?, ?, ?)',
                               (crawl_id, link["url"], link.get("status_code"), link.get("referring_page"), link.get("error_type"), link.get("error_message"), link.get("is_internal")))
            
            for tag in results.get("missing_meta_tags", []):
                cursor.execute('INSERT INTO missing_meta_tags (crawl_id, url, type, element, details) VALUES (?, ?, ?, ?, ?)',
                               (crawl_id, tag["url"], tag.get("tag_type"), tag.get("element"), tag.get("details")))

            conn.commit()
            self.logger.info(f"Crawl results for {results['url']} saved to database with crawl_id: {crawl_id}")
            return crawl_id
        except Exception as e:
            self.logger.error(f"Error saving crawl results to database: {e}", exc_info=True)
            conn.rollback()
        finally:
            conn.close()

    def get_latest_crawl_stats(self, website_id):
        conn = self._get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT pages_crawled, broken_links_count, missing_meta_tags_count FROM crawl_results WHERE website_id = ? ORDER BY timestamp DESC LIMIT 1', (website_id,))
            row = cursor.fetchone()
            if row:
                return {"pages_crawled": row[0], "total_broken_links": row[1], "total_missing_meta_tags": row[2]}
            return {"pages_crawled": 0, "total_broken_links": 0, "total_missing_meta_tags": 0}
        except Exception as e:
            self.logger.error(f"Error getting latest crawl stats for website_id {website_id}: {e}", exc_info=True)
            return {"pages_crawled": 0, "total_broken_links": 0, "total_missing_meta_tags": 0}
        finally:
            conn.close()

    def get_latest_crawl_results(self, website_id):
        conn = self._get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT id, timestamp, crawl_data FROM crawl_results WHERE website_id = ? ORDER BY timestamp DESC LIMIT 1', (website_id,))
            row = cursor.fetchone()
            if not row:
                return None
            
            crawl_id, timestamp, crawl_data_json = row
            crawl_data = json.loads(crawl_data_json)

            cursor.execute('SELECT url, status_code, referring_page, error_type, error_message, is_internal FROM broken_links WHERE crawl_id = ?', (crawl_id,))
            broken_links = [{"url": r[0], "status_code": r[1], "referring_page": r[2], "error_type": r[3], "error_message": r[4], "is_internal": r[5]} for r in cursor.fetchall()]

            cursor.execute('SELECT url, type, element, details FROM missing_meta_tags WHERE crawl_id = ?', (crawl_id,))
            missing_meta_tags = [{"url": r[0], "tag_type": r[1], "element": r[2], "details": r[3]} for r in cursor.fetchall()]

            return {
                "crawl_id": crawl_id, "timestamp": timestamp, **crawl_data,
                "broken_links": broken_links, "missing_meta_tags": missing_meta_tags
            }
        except Exception as e:
            self.logger.error(f"Error getting latest crawl results for website_id {website_id}: {e}", exc_info=True)
            return None
        finally:
            conn.close()

    def get_crawl_results_by_id(self, crawl_id):
        """Get crawl results for a specific crawl ID."""
        conn = self._get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT id, timestamp, crawl_data, website_id FROM crawl_results WHERE id = ?', (crawl_id,))
            row = cursor.fetchone()
            if not row:
                return None
            
            crawl_id, timestamp, crawl_data_json, website_id = row
            crawl_data = json.loads(crawl_data_json)

            cursor.execute('SELECT url, status_code, referring_page, error_type, error_message, is_internal FROM broken_links WHERE crawl_id = ?', (crawl_id,))
            broken_links = [{"url": r[0], "status_code": r[1], "referring_page": r[2], "error_type": r[3], "error_message": r[4], "is_internal": r[5]} for r in cursor.fetchall()]

            cursor.execute('SELECT url, type, element, details FROM missing_meta_tags WHERE crawl_id = ?', (crawl_id,))
            missing_meta_tags = [{"url": r[0], "tag_type": r[1], "element": r[2], "details": r[3]} for r in cursor.fetchall()]

            return {
                "crawl_id": crawl_id, "timestamp": timestamp, "website_id": website_id, **crawl_data,
                "broken_links": broken_links, "missing_meta_tags": missing_meta_tags
            }
        except Exception as e:
            self.logger.error(f"Error getting crawl results for crawl_id {crawl_id}: {e}", exc_info=True)
            return None
        finally:
            conn.close()

    def get_status_code_counts(self, crawl_id):
        conn = self._get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT crawl_data FROM crawl_results WHERE id = ?', (crawl_id,))
            row = cursor.fetchone()
            if row:
                crawl_data = json.loads(row[0])
                return crawl_data.get("crawl_stats", {}).get("status_code_counts", {})
            return {}
        except Exception as e:
            self.logger.error(f"Error getting status code counts for crawl_id {crawl_id}: {e}", exc_info=True)
            return {}
        finally:
            conn.close()

    def get_pages_by_status_code(self, crawl_id):
        conn = self._get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT crawl_data FROM crawl_results WHERE id = ?', (crawl_id,))
            row = cursor.fetchone()
            if row:
                crawl_data = json.loads(row[0])
                return crawl_data.get("all_pages", [])
            return []
        except Exception as e:
            self.logger.error(f"Error getting pages for crawl_id {crawl_id}: {e}", exc_info=True)
            return []
        finally:
            conn.close()

    def _send_blur_detection_notification(self, website, total_images, blurry_images):
        """Send email notification about blurry images detected."""
        try:
            # Use the existing alerter module for email notifications
            from src.alerter import send_email_alert
            
            from src.config_loader import get_config
            
            config = get_config()
            
            # Get email template from config
            email_template = config.get('blur_detection_email_template', 
                'Subject: Blurry Images Detected - {website_name}\n\n'
                'Dear Administrator,\n\n'
                'Our website monitoring system has detected {blurry_count} blurry images on {website_name}.\n\n'
                'Details:\n'
                '- Total images analyzed: {total_images}\n'
                '- Blurry images found: {blurry_count}\n'
                '- Blur percentage: {blur_percentage}%\n\n'
                'Please review the images in your dashboard for more details.\n\n'
                'Best regards,\n'
                'Website Monitoring System'
            )
            
            # Format email content
            blur_percentage = round((blurry_images / total_images * 100) if total_images > 0 else 0, 1)
            
            email_content = email_template.format(
                website_name=website.get('name', website.get('url', 'Unknown')),
                blurry_count=blurry_images,
                total_images=total_images,
                blur_percentage=blur_percentage
            )
            
            # Extract subject and body
            lines = email_content.split('\n')
            subject = lines[0].replace('Subject: ', '') if lines[0].startswith('Subject: ') else f"Blurry Images Detected - {website.get('name', 'Website')}"
            body = '\n'.join(lines[1:]).strip()
            
            # Get notification emails
            notification_emails = website.get('notification_emails', [])
            if not notification_emails:
                # Use the configured notification email instead of hardcoded fallback
                default_email = config.get('default_notification_email') or config.get('notification_email_to')
                if default_email:
                    notification_emails = [default_email]
                else:
                    self.logger.warning("No notification email configured - skipping blur detection notification")
                    return
            
            # Send email using existing alerter module
            if notification_emails:
                # Convert plain text body to HTML for better formatting
                body_html = f"<html><body><pre>{body}</pre></body></html>"
                
                success = send_email_alert(
                    subject=subject,
                    body_html=body_html,
                    recipient_emails=notification_emails
                )
                if success:
                    self.logger.info(f"Blur detection notification sent to {len(notification_emails)} recipients")
                else:
                    self.logger.warning("Failed to send blur detection notification")
            else:
                self.logger.warning("No notification emails configured for blur detection")
            
        except Exception as e:
            self.logger.error(f"Error sending blur detection notification: {e}", exc_info=True)

    def _run_blur_detection_if_enabled(self, results, website_id, options):
        """Run blur detection if enabled for this website and check type."""
        from src.blur_detector import BlurDetector
        from src.website_manager_sqlite import WebsiteManager
        
        # Get website configuration
        website_manager = WebsiteManager(config_path=self.config.get('config_path'))
        website = website_manager.get_website(website_id)
        
        if not website:
            self.logger.warning(f"Website {website_id} not found for blur detection")
            return
        
        # Check if blur detection should run based on check_config or website settings
        check_config = options.get('check_config', {})
        is_scheduled = options.get('is_scheduled', False)
        is_manual = not is_scheduled
        
        should_run = False
        
        # For manual checks, check_config overrides website settings
        if is_manual and check_config.get('blur_enabled', False):
            should_run = True
            self.logger.debug(f"Blur detection enabled via manual check config for website {website_id}")
        # For scheduled checks, respect new automated monitoring settings
        elif is_scheduled and website.get('auto_blur_enabled', False):
            should_run = True
            self.logger.debug(f"Blur detection enabled via automated monitoring settings for website {website_id}")
        # For manual checks when auto_blur_enabled is True (full check mode)
        elif is_manual and website.get('auto_blur_enabled', False):
            should_run = True
            self.logger.debug(f"Blur detection enabled via auto_blur_enabled setting for website {website_id}")
        # Backward compatibility: fallback to old blur detection settings
        elif is_manual and website.get('enable_blur_detection', False) and website.get('blur_detection_manual', True):
            should_run = True
            self.logger.debug(f"Blur detection enabled via legacy manual settings for website {website_id}")
        
        if not should_run:
            self.logger.debug(f"Blur detection not enabled for website {website_id} (scheduled: {is_scheduled}, check_config: {check_config})")
            return
        
        # Initialize blur detector
        blur_detector = BlurDetector()
        
        # Get crawl ID for database storage
        crawl_id = results.get('crawl_id')  # This will be set after _save_crawl_results
        
        # Collect ALL images from ALL pages first for batch processing
        all_images_data = []
        page_image_counts = {}
        
        # Track unique images by URL to avoid duplicates
        unique_image_urls = set()
        duplicates_found = 0
        
        self.logger.info(f"Starting blur detection for website {website_id}")
        
        for page in results.get('all_pages', []):
            page_url = page.get('url')
            page_images = page.get('images', [])
            
            # Only process images from internal pages (same logic as visual checks)
            if not page.get('is_internal', False):
                self.logger.debug(f"Skipping blur detection for external page: {page_url}")
                continue
            
            # Skip excluded pages to save resources
            if self._should_exclude_url_for_checks(page_url, 'blur', website_id):
                self.logger.debug(f"Skipping blur detection for excluded page: {page_url}")
                continue
            
            if not page_images:
                continue
            
            # Convert image data to list of URLs and filter for internal images only
            internal_image_urls = []
            for img in page_images:
                if isinstance(img, dict):
                    img_url = img.get('src')
                else:
                    img_url = str(img)
                
                if img_url:
                    # Make absolute URL if relative
                    if not img_url.startswith(('http://', 'https://')):
                        from urllib.parse import urljoin
                        img_url = urljoin(page_url, img_url)
                    
                    # Only include internal images (same domain as the website)
                    base_url = results.get('url') or website.get('url', '')
                    if self._is_internal_url(img_url, base_url):
                        # Check if this image URL has already been processed
                        if img_url in unique_image_urls:
                            duplicates_found += 1
                            self.logger.debug(f"Skipping duplicate image: {img_url} (already seen on another page)")
                            continue
                        
                        # Add to unique images set
                        unique_image_urls.add(img_url)
                        internal_image_urls.append(img_url)
                        
                        # Add to batch processing data with page context
                        all_images_data.append({
                            'image_url': img_url,
                            'page_url': page_url,
                            'page_title': page.get('title', '')
                        })
                    else:
                        self.logger.debug(f"Skipping external image: {img_url}")
            
            if internal_image_urls:
                page_image_counts[page_url] = len(internal_image_urls)
                self.logger.debug(f"Found {len(internal_image_urls)} internal images from {page_url} (filtered from {len(page_images)} total)")
            else:
                self.logger.debug(f"No internal images found on page: {page_url}")
        
        # Log deduplication results
        if duplicates_found > 0:
            self.logger.info(f"Image deduplication: Found {duplicates_found} duplicate images across pages, processing {len(all_images_data)} unique images")
        else:
            self.logger.info(f"No duplicate images found, processing {len(all_images_data)} unique images")
        
        # Process all images in a single batch operation
        if all_images_data:
            total_pages = len(page_image_counts)
            total_images = len(all_images_data)
            
            self.logger.info(f"Processing {total_images} internal images from {total_pages} pages in batch operation")
            
            try:
                # Run batch blur detection on all images
                all_blur_results = blur_detector.analyze_website_images(
                    website_id=website_id,
                    all_images_data=all_images_data,
                    crawl_id=crawl_id
                )
                
                # Organize results by page for storage in page data
                results_by_page = {}
                for result in all_blur_results:
                    page_url = result.get('page_url')
                    if page_url not in results_by_page:
                        results_by_page[page_url] = []
                    results_by_page[page_url].append(result)
                
                # Store blur results in the appropriate page data
                for page in results.get('all_pages', []):
                    page_url = page.get('url')
                    if page_url in results_by_page:
                        page['blur_detection_results'] = results_by_page[page_url]
                
                # Calculate statistics from all results
                total_images_processed = len(all_blur_results)
                total_blurry_images = sum(1 for r in all_blur_results if r.get('is_blurry', False))
                
                # Store blur detection summary in results
                results['blur_detection_summary'] = {
                    'enabled': True,
                    'total_images': total_images_processed,
                    'blurry_images': total_blurry_images,
                    'total_images_processed': total_images_processed,
                    'total_blurry_images': total_blurry_images,
                    'blur_percentage': round((total_blurry_images / total_images_processed * 100) if total_images_processed > 0 else 0, 1),
                    'duplicates_removed': duplicates_found,
                    'unique_images_processed': len(all_images_data),
                    'total_images_found': len(all_images_data) + duplicates_found
                }
                
                self.logger.info(f"Blur detection completed for website {website_id}. "
                                f"Processed {total_images_processed} unique images from {total_pages} pages, "
                                f"found {total_blurry_images} blurry images "
                                f"({results['blur_detection_summary']['blur_percentage']}%), "
                                f"removed {duplicates_found} duplicate images")
                
                # Note: Blur detection results are included in the combined email notification
                # No separate blur email notification needed
                
            except Exception as e:
                self.logger.error(f"Error running batch blur detection: {e}", exc_info=True)
                
        else:
            self.logger.info(f"No internal images found for blur detection on website {website_id}")
            
            # Store empty blur detection summary
            results['blur_detection_summary'] = {
                'enabled': True,
                'total_images': 0,
                'blurry_images': 0,
                'total_images_processed': 0,
                'total_blurry_images': 0,
                'blur_percentage': 0,
                'duplicates_removed': duplicates_found,
                'unique_images_processed': 0,
                'total_images_found': duplicates_found
            }

    def _run_blur_detection_for_blur_check(self, results, website_id, options):
        """Run blur detection for blur-only checks using batch processing."""
        from src.blur_detector import BlurDetector
        from src.website_manager_sqlite import WebsiteManager
        
        # Get website configuration
        website_manager = WebsiteManager(config_path=self.config.get('config_path'))
        website = website_manager.get_website(website_id)
        
        if not website:
            self.logger.warning(f"Website {website_id} not found for blur detection")
            return
        
        # Initialize blur detector
        blur_detector = BlurDetector()
        
        # Get crawl ID for database storage
        crawl_id = results.get('crawl_id')  # This will be set after _save_crawl_results
        
        # Collect ALL images from ALL pages first for batch processing
        all_images_data = []
        page_image_counts = {}
        
        self.logger.info(f"Starting blur detection for website {website_id}")
        
        for page in results.get('all_pages', []):
            page_url = page.get('url')
            page_images = page.get('images', [])
            
            # Only process images from internal pages (same logic as visual checks)
            if not page.get('is_internal', False):
                self.logger.debug(f"Skipping blur detection for external page: {page_url}")
                continue
            
            # Skip excluded pages to save resources
            if self._should_exclude_url_for_checks(page_url, 'blur', website_id):
                self.logger.debug(f"Skipping blur detection for excluded page: {page_url}")
                continue
            
            if not page_images:
                continue
            
            # Convert image data to list of URLs and filter for internal images only
            internal_image_urls = []
            for img in page_images:
                if isinstance(img, dict):
                    img_url = img.get('src')
                else:
                    img_url = str(img)
                
                if img_url:
                    # Make absolute URL if relative
                    if not img_url.startswith(('http://', 'https://')):
                        from urllib.parse import urljoin
                        img_url = urljoin(page_url, img_url)
                    
                    # Only include internal images (same domain as the website)
                    base_url = results.get('url') or website.get('url', '')
                    if self._is_internal_url(img_url, base_url):
                        internal_image_urls.append(img_url)
                        # Add to batch processing data with page context
                        all_images_data.append({
                            'image_url': img_url,
                            'page_url': page_url,
                            'page_title': page.get('title', '')
                        })
                    else:
                        self.logger.debug(f"Skipping external image: {img_url}")
            
            if internal_image_urls:
                page_image_counts[page_url] = len(internal_image_urls)
                self.logger.debug(f"Found {len(internal_image_urls)} internal images from {page_url} (filtered from {len(page_images)} total)")
            else:
                self.logger.debug(f"No internal images found on page: {page_url}")
        
        # Process all images in a single batch operation
        if all_images_data:
            total_pages = len(page_image_counts)
            total_images = len(all_images_data)
            
            self.logger.info(f"Processing {total_images} internal images from {total_pages} pages in batch operation")
            
            try:
                # Run batch blur detection on all images
                all_blur_results = blur_detector.analyze_website_images(
                    website_id=website_id,
                    all_images_data=all_images_data,
                    crawl_id=crawl_id
                )
                
                # Organize results by page for storage in page data
                results_by_page = {}
                for result in all_blur_results:
                    page_url = result.get('page_url')
                    if page_url not in results_by_page:
                        results_by_page[page_url] = []
                    results_by_page[page_url].append(result)
                
                # Store blur results in the appropriate page data
                for page in results.get('all_pages', []):
                    page_url = page.get('url')
                    if page_url in results_by_page:
                        page['blur_detection_results'] = results_by_page[page_url]
                
                # Calculate statistics from all results
                total_images_processed = len(all_blur_results)
                total_blurry_images = sum(1 for r in all_blur_results if r.get('is_blurry', False))
                
                # Store blur detection summary in results
                results['blur_detection_summary'] = {
                    'enabled': True,
                    'total_images': total_images_processed,
                    'blurry_images': total_blurry_images,
                    'total_images_processed': total_images_processed,
                    'total_blurry_images': total_blurry_images,
                    'blur_percentage': round((total_blurry_images / total_images_processed * 100) if total_images_processed > 0 else 0, 1)
                }
                
                self.logger.info(f"Blur detection completed for website {website_id}. "
                                f"Processed {total_images_processed} images from {total_pages} pages, "
                                f"found {total_blurry_images} blurry images "
                                f"({results['blur_detection_summary']['blur_percentage']}%)")
                
            except Exception as e:
                self.logger.error(f"Error running batch blur detection: {e}", exc_info=True)
                
        else:
            self.logger.info(f"No internal images found for blur detection on website {website_id}")
            
            # Store empty blur detection summary
            results['blur_detection_summary'] = {
                'enabled': True,
                'total_images': 0,
                'blurry_images': 0,
                'total_images_processed': 0,
                'total_blurry_images': 0,
                'blur_percentage': 0
            }

    def _run_performance_check_if_enabled(self, results, website_id, options):
        """Run performance check if enabled for this website and check type."""
        from src.performance_checker import PerformanceChecker
        from src.website_manager_sqlite import WebsiteManager
        
        self.logger.info(f"_run_performance_check_if_enabled called for website {website_id} with options: {options}")
        
        # Get website configuration
        website_manager = WebsiteManager(config_path=self.config.get('config_path'))
        website = website_manager.get_website(website_id)
        
        if not website:
            self.logger.warning(f"Website {website_id} not found for performance check")
            return
        
        # Check if this is a performance-only check or if performance is enabled in automated monitoring
        check_config = options.get('check_config', {})
        performance_only = options.get('performance_check_only', False)
        performance_enabled = check_config.get('performance_enabled', False)
        
        self.logger.info(f"Performance check conditions - performance_only: {performance_only}, performance_enabled: {performance_enabled}")
        
        # For performance-only checks, always run regardless of website settings
        # For other checks, check if performance is enabled in the check configuration
        if not performance_only and not performance_enabled:
            self.logger.debug(f"Performance check disabled for website {website_id} (performance_only: {performance_only}, performance_enabled: {performance_enabled})")
            return
        
        try:
            # Initialize performance checker with production config
            self.logger.info(f"Initializing performance checker for website {website_id}")
            from src.config_loader import get_config_path_for_environment
            config_path = get_config_path_for_environment()
            performance_checker = PerformanceChecker(config_path=config_path)
            
            # Get the main website URL
            website_url = website.get('url')
            if not website_url:
                self.logger.warning(f"No URL found for website {website_id}")
                return
            
            # Prepare pages to check (internal pages only)
            pages_to_check = []
            
            # Add main page
            pages_to_check.append({
                'url': website_url,
                'title': website.get('name', 'Homepage')
            })
            
            # Add internal pages from crawl results (excluding direct image links)
            image_ext_pattern = re.compile(r'\.(png|jpg|jpeg|gif|webp|svg|bmp|ico|tiff)$', re.IGNORECASE)
            
            all_pages = results.get('all_pages', [])
            self.logger.info(f"Found {len(all_pages)} total pages in crawl results")
            
            for page in all_pages:
                page_url = page.get('url')
                # Skip if same as main URL, not internal, direct image link, or excluded by keywords
                if (page_url and 
                    page_url != website_url and 
                    page.get('is_internal', False) and 
                    not image_ext_pattern.search(page_url) and
                    not self._should_exclude_url_for_checks(page_url, 'performance', website_id)):
                    pages_to_check.append({
                        'url': page_url,
                        'title': page.get('title', 'Unknown Page')
                    })
                    self.logger.debug(f"Added page for performance check: {page_url}")
                else:
                    if page_url:
                        excluded = self._should_exclude_url_for_checks(page_url, 'performance', website_id)
                        self.logger.debug(f"Skipped page: {page_url} (same_as_main: {page_url == website_url}, internal: {page.get('is_internal', False)}, is_image: {image_ext_pattern.search(page_url) is not None}, excluded: {excluded})")
            
            self.logger.info(f"Total pages to check for performance: {len(pages_to_check)}")
            
            # Limit to reasonable number of pages to avoid API limits and timeouts
            max_pages = 5  # Reduced limit to prevent timeouts
            if len(pages_to_check) > max_pages:
                self.logger.info(f"Limiting performance check to {max_pages} pages (found {len(pages_to_check)})")
                pages_to_check = pages_to_check[:max_pages]
            
            self.logger.info(f"Running performance check for {len(pages_to_check)} pages")
            
            # Run performance check on all internal pages
            performance_results = performance_checker.check_website_performance(
                website_id=website_id,
                crawl_id=results.get('crawl_id'),
                pages_to_check=pages_to_check
            )
            
            self.logger.info(f"Performance check returned: {type(performance_results)} with keys: {list(performance_results.keys()) if isinstance(performance_results, dict) else 'Not a dict'}")
            
            # Store performance results in the crawl results
            if performance_results:
                results['performance_check'] = performance_results
                
                # Log summary
                pages_analyzed = performance_results.get('performance_check_summary', {}).get('pages_analyzed', 0)
                self.logger.info(f"Performance check completed for website {website_id}. "
                               f"Analyzed {pages_analyzed} pages.")
                
                # Performance email notification is handled by the main email logic above
            else:
                self.logger.warning(f"Performance check returned no results for website {website_id}")
                
        except Exception as e:
            self.logger.error(f"Error running performance check for website {website_id}: {e}", exc_info=True)
            results['performance_check'] = {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _send_single_check_email_notification(self, website, check_results, check_type):
        """Send single check email notification using the existing alerter module."""
        try:
            from src.alerter import (
                _send_visual_check_email, 
                _send_crawl_check_email, 
                _send_blur_check_email, 
                send_performance_email,
                _send_baseline_check_email
            )

            # Use the specific email function for each check type
            if check_type == "visual":
                success = _send_visual_check_email(website, check_results)
            elif check_type == "crawl":
                success = _send_crawl_check_email(website, check_results)
            elif check_type == "blur":
                success = _send_blur_check_email(website, check_results)
            elif check_type == "performance":
                success = send_performance_email(website, check_results)
            elif check_type == "baseline":
                success = _send_baseline_check_email(website, check_results)
            else:
                # Fallback to general send_report
                from src.alerter import send_report
                success = send_report(website, check_results)
            
            if success:
                self.logger.info(f"{check_type.title()} email notification sent for website {website.get('name', 'Unknown')}")
            else:
                self.logger.warning(f"Failed to send {check_type} email notification for website {website.get('name', 'Unknown')}")
        except Exception as e:
            self.logger.error(f"Error sending {check_type} email notification: {e}", exc_info=True)
