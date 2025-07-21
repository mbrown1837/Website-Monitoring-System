import os
import json
import sqlite3
<<<<<<< HEAD
from datetime import datetime, timezone
=======
from datetime import datetime
>>>>>>> b22721c337b3f3f392c6637ab2d71c3ccf804727
from urllib.parse import urljoin, urlparse, urlunparse
import time
import re

<<<<<<< HEAD
from src.greenflare_crawler import GreenflareWrapper, GREENFLARE_AVAILABLE
=======
# Import the required libraries
try:
    from yirabot import Yirabot
except ImportError:
    raise ImportError("YiraBot library not installed. Install it using: pip install yirabot")

from requests.exceptions import SSLError, ConnectTimeout, ReadTimeout, ConnectionError, TooManyRedirects, RequestException
>>>>>>> b22721c337b3f3f392c6637ab2d71c3ccf804727
from src.logger_setup import setup_logging
from src.config_loader import get_config
from src.comparators import compare_screenshots_percentage, compare_screenshots_ssim, OPENCV_SKIMAGE_AVAILABLE
from src.website_manager import WebsiteManager

logger = setup_logging()

class CrawlerModule:
    def __init__(self, config_path=None):
        self.logger = logger
        self.config = get_config(config_path=config_path)
        
        if GREENFLARE_AVAILABLE:
            self.logger.info("Using official Greenflare crawler implementation")
        else:
            self.logger.info("Using fallback Greenflare crawler implementation")
        
<<<<<<< HEAD
        self.bot = GreenflareWrapper(
            user_agent=self.config.get('user_agent', 'Website Monitoring System Crawler/1.0'),
            retries=self.config.get('greenflare_retries', 3),
            backoff_base=self.config.get('greenflare_backoff_base', 0.3),
            timeout=self.config.get('greenflare_timeout', 30),
            max_depth=self.config.get('max_crawl_depth', 3),
            respect_robots=self.config.get('respect_robots_txt', True),
            check_external_links=self.config.get('check_external_links', True)
=======
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
>>>>>>> b22721c337b3f3f392c6637ab2d71c3ccf804727
        )
        self.logger.info("CrawlerModule initialized with enhanced Greenflare crawler")
        
        self.website_manager = WebsiteManager()
        
    def _get_db_connection(self):
        db_path = os.path.join('data', 'website_monitor.db')
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        conn = sqlite3.connect(db_path)
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
<<<<<<< HEAD
            self.logger.error(f"Error initializing database schema: {e}", exc_info=True)
        finally:
            conn.close()

    def crawl_website(self, website_id, url, check_config=None, is_scheduled=False, **options):
=======
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
>>>>>>> b22721c337b3f3f392c6637ab2d71c3ccf804727
        self.logger.info(f"Starting crawl of website ID {website_id}: {url}")
        
        # Get appropriate configuration
        if check_config is None:
            if is_scheduled:
                check_config = self.website_manager.get_automated_check_config(website_id)
                if not check_config:
                    self.logger.error(f"Could not get automated check config for website {website_id}")
                    return {"website_id": website_id, "url": url, "timestamp": datetime.now().isoformat(), "error": "Website not found"}
            else:
                # For manual checks, use legacy options for backward compatibility
                check_config = {
                    'crawl_enabled': not options.get('visual_check_only', False) and not options.get('blur_check_only', False),
                    'visual_enabled': not options.get('crawl_only', False) and not options.get('blur_check_only', False),
                    'blur_enabled': options.get('blur_check_only', False),
                    'performance_enabled': options.get('performance_check_only', False)
                }
        
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
                        'meta_tags': ["title", "description"]  # Minimal meta tags for blur-only
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
                    'meta_tags': ["title", "description", "keywords", "robots", "canonical"]  # Standard meta tags
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
            if check_config.get('visual_enabled', True) and not crawl_only and not blur_check_only:
                if create_baseline:
                    self._create_visual_baselines(results)
                else:
                    self._capture_latest_snapshots(results)
            else:
                self.logger.info(f"Skipping visual snapshots - visual_enabled: {check_config.get('visual_enabled', True)}, crawl_only: {crawl_only}, blur_check_only: {blur_check_only}")

            # Save crawl results first to get crawl_id
            crawl_id = self._save_crawl_results(results)
            results['crawl_id'] = crawl_id

            # Run blur detection if enabled for this website (after saving to get crawl_id)
            if blur_check_only:
                # For blur-only checks, always run blur detection regardless of website settings
                self._run_blur_detection_for_blur_check(results, website_id, original_options)
            elif check_config.get('blur_enabled', False):
                # For other checks, run blur detection if enabled in configuration
                self._run_blur_detection_if_enabled(results, website_id, original_options)
            else:
                self.logger.debug(f"Blur detection disabled for this check type")
            
            # Run performance checks if enabled
            performance_enabled = check_config.get('performance_enabled', False)
            performance_check_only = options.get('performance_check_only', False)
            self.logger.info(f"Performance check evaluation - performance_enabled: {performance_enabled}, performance_check_only: {performance_check_only}, check_config: {check_config}")
            
            if performance_enabled or performance_check_only:
                self.logger.info(f"Running performance check for website {website_id}")
                self._run_performance_check_if_enabled(results, website_id, original_options)
            else:
                self.logger.debug(f"Performance check disabled - performance_enabled: {performance_enabled}, performance_check_only: {performance_check_only}")

            results["internal_urls"] = list(results["internal_urls"])
            results["external_urls"] = list(results["external_urls"])
            self.logger.info(f"Crawl of {url} completed. Found {len(results['broken_links'])} broken links.")
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
        self._handle_snapshots(results, is_baseline=True)

    def _capture_latest_snapshots(self, results):
        self._handle_snapshots(results, is_baseline=False)

    def _handle_snapshots(self, results, is_baseline):
        from src.snapshot_tool import save_visual_snapshot
        from src.comparators import compare_screenshots_percentage # Import our comparison function
        from src.website_manager import WebsiteManager # To get baseline paths

        website_manager = WebsiteManager()
        website_config = website_manager.get_website(results['website_id'])
        all_baselines = website_config.get('all_baselines', {})
        
        log_action = "baseline" if is_baseline else "latest"
        self.logger.info(f"Starting to capture {log_action} snapshots for website ID: {results['website_id']}")

        # --- FIX: Filter out direct links to images ---
        image_ext_pattern = re.compile(r'\.(png|jpg|jpeg|gif|webp|svg|bmp)$', re.IGNORECASE)
        pages_to_snapshot = [
            p for p in results.get('all_pages', []) 
            if p.get('is_internal') and p.get('status_code') == 200 and not image_ext_pattern.search(p['url'])
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
                
<<<<<<< HEAD
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
                        baseline_info = all_baselines.get(url)
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
                            self.logger.warning(f"No baseline found for URL {url} to compare against the latest snapshot.")

            except Exception as e:
                self.logger.error(f"Error processing snapshot for URL {url}: {e}", exc_info=True)
        
        # Update results with the detailed page_results
        results['page_results'] = page_results

        if is_baseline:
            results['visual_baselines'] = [{'url': u, 'path': p} for u, p in snapshot_map.items()]
            self._update_website_with_baselines(results['website_id'], snapshot_map)
        else:
            results['latest_snapshots'] = snapshot_map
        
        self.logger.info(f"Captured {len(snapshot_map)} {log_action} snapshots.")
    
    def _update_website_with_baselines(self, website_id, baselines_by_url):
        if not baselines_by_url:
            return
            
        website_manager = WebsiteManager()
        website = website_manager.get_website(website_id)
        
        if not website:
            return

        all_baselines = website.get("all_baselines", {})
        for url, path in baselines_by_url.items():
            all_baselines[url] = {'path': path, 'timestamp': datetime.now(timezone.utc).isoformat()}
        
        updates = {"all_baselines": all_baselines, "has_subpage_baselines": True}
        if not website.get('baseline_visual_path') and website.get('url') in all_baselines:
            updates['baseline_visual_path'] = all_baselines[website.get('url')]['path']
        
        website_manager.update_website(website_id, updates)
            
    def _normalize_url(self, url):
        if not url:
            return url
        try:
            parsed = urlparse(url)
            path = parsed.path.rstrip('/') or '/'
            return urlunparse((parsed.scheme, parsed.netloc.lower(), path, parsed.params, parsed.query, parsed.fragment))
        except Exception:
            return url
=======
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
>>>>>>> b22721c337b3f3f392c6637ab2d71c3ccf804727
    
    def _is_internal_url(self, url, base_url):
        if not url:
            return False
        try:
<<<<<<< HEAD
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
=======
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
>>>>>>> b22721c337b3f3f392c6637ab2d71c3ccf804727
            crawl_id = cursor.lastrowid
            
            for link in results.get("broken_links", []):
                cursor.execute('INSERT INTO broken_links (crawl_id, url, status_code, referring_page, error_type, error_message, is_internal) VALUES (?, ?, ?, ?, ?, ?, ?)',
                               (crawl_id, link["url"], link.get("status_code"), link.get("referring_page"), link.get("error_type"), link.get("error_message"), link.get("is_internal")))
            
            for tag in results.get("missing_meta_tags", []):
                cursor.execute('INSERT INTO missing_meta_tags (crawl_id, url, type, element, details) VALUES (?, ?, ?, ?, ?)',
                               (crawl_id, tag["url"], tag.get("type"), tag.get("element"), tag.get("details")))

            conn.commit()
            self.logger.info(f"Crawl results for {results['url']} saved to database with crawl_id: {crawl_id}")
            return crawl_id
        except Exception as e:
            self.logger.error(f"Error saving crawl results to database: {e}", exc_info=True)
            conn.rollback()
        finally:
            conn.close()
<<<<<<< HEAD

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

=======
    
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
    
>>>>>>> b22721c337b3f3f392c6637ab2d71c3ccf804727
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
            missing_meta_tags = [{"url": r[0], "type": r[1], "element": r[2], "details": r[3]} for r in cursor.fetchall()]

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
            missing_meta_tags = [{"url": r[0], "type": r[1], "element": r[2], "details": r[3]} for r in cursor.fetchall()]

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
            # Try to import email sender - make it optional
            try:
                from src.email_sender import EmailSender
                email_sender = EmailSender()
            except ImportError:
                self.logger.warning("Email sender module not available. Skipping email notification.")
                return
            
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
                notification_emails = [config.get('default_notification_email', 'admin@example.com')]
            
            # Send email to each recipient
            for email in notification_emails:
                if email.strip():
                    email_sender.send_email(
                        to_email=email.strip(),
                        subject=subject,
                        body=body
                    )
            
            self.logger.info(f"Blur detection notification sent to {len(notification_emails)} recipients")
            
        except Exception as e:
            self.logger.error(f"Error sending blur detection notification: {e}", exc_info=True)

    def _run_blur_detection_if_enabled(self, results, website_id, options):
        """Run blur detection if enabled for this website and check type."""
        from src.blur_detector import BlurDetector
        from src.website_manager import WebsiteManager
        
        # Get website configuration
        website_manager = WebsiteManager()
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
        
        self.logger.info(f"Starting blur detection for website {website_id}")
        
        for page in results.get('all_pages', []):
            page_url = page.get('url')
            page_images = page.get('images', [])
            
            # Only process images from internal pages (same logic as visual checks)
            if not page.get('is_internal', False):
                self.logger.debug(f"Skipping blur detection for external page: {page_url}")
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
                
                # Send email notification if blurry images found
                if total_blurry_images > 0:
                    self._send_blur_detection_notification(website, total_images_processed, total_blurry_images)
                
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

    def _run_blur_detection_for_blur_check(self, results, website_id, options):
        """Run blur detection for blur-only checks using batch processing."""
        from src.blur_detector import BlurDetector
        from src.website_manager import WebsiteManager
        
        # Get website configuration
        website_manager = WebsiteManager()
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
        from src.website_manager import WebsiteManager
        
        self.logger.info(f"_run_performance_check_if_enabled called for website {website_id} with options: {options}")
        
        # Get website configuration
        website_manager = WebsiteManager()
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
            # Initialize performance checker
            self.logger.info(f"Initializing performance checker for website {website_id}")
            performance_checker = PerformanceChecker()
            
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
                # Skip if same as main URL, not internal, or direct image link
                if (page_url and 
                    page_url != website_url and 
                    page.get('is_internal', False) and 
                    not image_ext_pattern.search(page_url)):
                    pages_to_check.append({
                        'url': page_url,
                        'title': page.get('title', 'Unknown Page')
                    })
                    self.logger.debug(f"Added page for performance check: {page_url}")
                else:
                    if page_url:
                        self.logger.debug(f"Skipped page: {page_url} (same_as_main: {page_url == website_url}, internal: {page.get('is_internal', False)}, is_image: {image_ext_pattern.search(page_url) is not None})")
            
            self.logger.info(f"Total pages to check for performance: {len(pages_to_check)}")
            
            # Limit to reasonable number of pages to avoid API limits
            max_pages = 10  # Reasonable limit for performance testing
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
            else:
                self.logger.warning(f"Performance check returned no results for website {website_id}")
                
        except Exception as e:
            self.logger.error(f"Error running performance check for website {website_id}: {e}", exc_info=True)
            results['performance_check'] = {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
