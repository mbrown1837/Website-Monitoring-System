"""
Enhanced Greenflare integration for the Website Monitoring System.
This module provides a robust wrapper around the official Greenflare SEO crawler
with proper error handling, comprehensive link checking, and meta tag extraction.
"""

import os
import time
import logging
import threading
import queue
from urllib.parse import urlparse, urljoin, urlunparse
import requests
from bs4 import BeautifulSoup

# Define GREENFLARE_AVAILABLE as a global variable
GREENFLARE_AVAILABLE = False

# Try to import the official Greenflare package
try:
    # First try the main package structure
    try:
        from greenflare.greenflare import GFlareCrawler
        from greenflare.core.gflareresponse import GFlareResponse
        from greenflare.core.gflarerobots import GFlareRobots
        GREENFLARE_AVAILABLE = True
    except ImportError:
        try:
            # Then try alternative module structure
            from greenflare.core.gflarecrawler import GFlareCrawler
            from greenflare.core.gflareresponse import GFlareResponse
            from greenflare.core.gflarerobots import GFlareRobots
            GREENFLARE_AVAILABLE = True
        except ImportError:
            # Last attempt
            from greenflare import GFlareCrawler
            from greenflare.gflareresponse import GFlareResponse
            from greenflare.gflarerobots import GFlareRobots
            GREENFLARE_AVAILABLE = True
except ImportError:
    # If all imports fail, use our fallback implementation
    GREENFLARE_AVAILABLE = False
    GFlareCrawler = None
    GFlareResponse = None
    GFlareRobots = None

logger = logging.getLogger(__name__)

class GreenflareWrapper:
    """
    Enhanced wrapper for Greenflare SEO crawler with robust error handling,
    comprehensive link checking, and improved meta tag extraction.
    """
    
    def __init__(self, user_agent=None, retries=3, backoff_base=0.3, timeout=30, 
                 max_urls=None, max_depth=3, respect_robots=True, check_external_links=True):
        """Initialize the crawler with configurable parameters."""
        self.user_agent = user_agent or "Greenflare/1.0 Website Monitoring System"
        self.retries = retries
        self.backoff_base = backoff_base
        self.timeout = timeout
        self.max_urls = max_urls
        self.max_depth = max_depth
        self.respect_robots = respect_robots
        self.check_external_links = check_external_links
        
        # Initialize the official Greenflare crawler if available
        self.official_crawler = None
        self.crawl_data = []
        
        if GREENFLARE_AVAILABLE:
            try:
                # Create a lock for thread safety
                self.lock = threading.RLock()
                
                # Initialize settings
                self.settings = {
                    'MODE': 'Spider',
                    'THREADS': 5,
                    'URLS_PER_SECOND': 0,
                    'USER_AGENT': self.user_agent,
                    'MAX_RETRIES': self.retries,
                    'CRAWL_ITEMS': [
                        'url',
                        'crawl_status',
                        'status_code',
                        'content_type',
                        'page_title',
                        'meta_description',
                        'h1',
                        'canonical_tag',
                        'robots_txt',
                        'redirect_url',
                        'meta_robots',
                        'x_robots_tag',
                    ],
                    'EXTRACTION_SEPARATOR': ' | '
                }
                
                # Add optional crawl items
                if self.respect_robots:
                    self.settings['CRAWL_ITEMS'].append('respect_robots_txt')
                if self.check_external_links:
                    self.settings['CRAWL_ITEMS'].append('external_links')
                
                # Initialize the official crawler
                self.official_crawler = GFlareCrawler(settings=self.settings, lock=self.lock)
                logger.info("Using official Greenflare crawler")
                
                # Initialize robots.txt handler
                self.robots_handler = GFlareRobots('', self.user_agent)
                
            except Exception as e:
                logger.error(f"Failed to initialize official Greenflare crawler: {e}")
                self.official_crawler = None
                # Don't set GREENFLARE_AVAILABLE to False here, as it's a module-level variable
    
    def configure(self, config):
        """Configure the crawler with specific settings."""
        self.start_urls = config.get('start_urls', [])
        self.max_depth = config.get('max_depth', self.max_depth)
        self.respect_robots = config.get('respect_robots_txt', self.respect_robots)
        self.check_external_links = config.get('check_external_links', self.check_external_links)
        self.extract_meta_tags = config.get('meta_tags', ["title", "description", "keywords", "robots", "canonical"])
        self.extract_images = config.get('extract_images', True)
        self.extract_alt_text = config.get('extract_alt_text', True)
        
        # Configure the official crawler if available
        if self.official_crawler:
            try:
                # Update settings
                self.settings['CUSTOM_CRAWL_DEPTH'] = self.max_depth
                self.settings['CHECK_EXTERNAL_LINKS'] = self.check_external_links
                self.settings['RESPECT_ROBOTS'] = self.respect_robots
                self.settings['FOLLOW_REDIRECTS'] = True
                
                if self.start_urls:
                    self.settings['STARTING_URL'] = self.start_urls[0]
                    self.settings['ROOT_DOMAIN'] = self._get_domain(self.start_urls[0])
                
                # Configure extraction settings
                if "title" in self.extract_meta_tags:
                    self.settings['CRAWL_ITEMS'].append('page_title')
                if "description" in self.extract_meta_tags:
                    self.settings['CRAWL_ITEMS'].append('meta_description')
                if "keywords" in self.extract_meta_tags:
                    self.settings['CRAWL_ITEMS'].append('meta_keywords')
                if "robots" in self.extract_meta_tags:
                    self.settings['CRAWL_ITEMS'].append('robots_tag')
                if "canonical" in self.extract_meta_tags:
                    self.settings['CRAWL_ITEMS'].append('canonical_tag')
                
                # Always extract H1 tags for SEO analysis
                self.settings['CRAWL_ITEMS'].append('h1_tag')
                
                if self.extract_images:
                    self.settings['CRAWL_ITEMS'].append('images')
                    if self.extract_alt_text:
                        self.settings['CRAWL_ITEMS'].append('images_missing_alt')
                
                # Update the crawler settings
                self.official_crawler.settings = self.settings
                
                # Initialize the session
                self.official_crawler.init_crawl_headers()
                self.official_crawler.init_session()
                
                logger.info("Official Greenflare crawler configured successfully")
            except Exception as e:
                logger.error(f"Failed to configure official Greenflare crawler: {e}")
                self.official_crawler = None
        
        return self
    
    def _normalize_url(self, url: str) -> str:
        """
        Normalizes a URL by removing trailing slashes from the path.
        e.g., 'http://a.com/b/' becomes 'http://a.com/b'.
        The root path 'http://a.com/' is not changed if it's just the root.
        It properly handles query strings and fragments.
        """
        url = url.strip()
        try:
            parsed = urlparse(url)
            path = parsed.path
            
            # Remove trailing slash if path is not just "/"
            if len(path) > 1 and path.endswith('/'):
                path = path.rstrip('/')
            
            if not path:
                path = '/'

            # Reconstruct the URL
            normalized_parsed = parsed._replace(path=path)
            return urlunparse(normalized_parsed)
        except Exception as e:
            logger.warning(f"Could not normalize URL '{url}': {e}")
            return url # Return original url on failure

    def run(self):
        """Run the crawler with the configured settings."""
        if not self.start_urls:
            raise ValueError("No start URLs configured. Use configure() method first.")
        
        start_url = self.start_urls[0]
        logger.info(f"Starting crawl of {start_url}")
        
        # Use our custom implementation directly since it works reliably
        logger.info(f"Using custom crawler implementation for {start_url}")
        return self._run_custom_crawler(start_url)
    
    def _process_official_results(self, crawl_data):
        """Process the results from the official Greenflare crawler."""
        results = {
            'pages': []
        }
        
        # Debug: Log the first row to see what data we're getting
        if crawl_data:
            logger.info(f"DEBUG: First row keys from greenflare: {list(crawl_data[0].keys()) if crawl_data[0] else 'No data'}")
            logger.info(f"DEBUG: First row sample data: {dict(list(crawl_data[0].items())[:5]) if crawl_data[0] else 'No data'}")
        
        # Process each page
        for row in crawl_data:
            # Skip tel: and mailto: links
            if row.get('url', '').lower().startswith(('tel:', 'mailto:')):
                continue
                
            page = {
                'url': row.get('url', ''),
                'status_code': row.get('status_code'),
                'title': row.get('page_title', ''),
                'referring_page': row.get('referring_url', '')
            }
            
            # Add meta information
            meta = {}
            if 'page_title' in row and row['page_title']:
                meta['title'] = row['page_title']
            if 'meta_description' in row and row['meta_description']:
                meta['description'] = row['meta_description']
            if 'meta_keywords' in row and row['meta_keywords']:
                meta['keywords'] = row['meta_keywords']
            if 'canonical_tag' in row and row['canonical_tag']:
                meta['canonical'] = row['canonical_tag']
            if 'meta_robots' in row and row['meta_robots']:
                meta['robots'] = row['meta_robots']
            if 'h1' in row and row['h1']:
                meta['h1'] = row['h1']
            if meta:
                page['meta'] = meta
            
            # Check for missing meta tags
            missing_meta_tags = {}
            # Only check internal pages and only check title and description
            # Also exclude image URLs from meta tag analysis
            is_image_url = any(page['url'].lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp', '.ico', '.tiff', '.tif'])
            if page['is_internal'] and not is_image_url:  # Only check meta tags for internal pages, exclude images
                if 'page_title' not in row or not row.get('page_title'):
                    missing_meta_tags['title'] = 'Missing page title'
                elif len(row.get('page_title', '')) < 10:
                    missing_meta_tags['title'] = f"Title too short ({len(row.get('page_title', ''))} chars)"
                elif len(row.get('page_title', '')) > 60:
                    missing_meta_tags['title'] = f"Title too long ({len(row.get('page_title', ''))} chars)"
                    
                if 'meta_description' not in row or not row.get('meta_description'):
                    missing_meta_tags['description'] = 'Missing meta description'
                elif len(row.get('meta_description', '')) < 50:
                    missing_meta_tags['description'] = f"Description too short ({len(row.get('meta_description', ''))} chars)"
                elif len(row.get('meta_description', '')) > 160:
                    missing_meta_tags['description'] = f"Description too long ({len(row.get('meta_description', ''))} chars)"
                
            if missing_meta_tags:
                page['missing_meta_tags'] = missing_meta_tags
            
            # Add image information if available
            if 'images' in row and row['images']:
                images = row['images'].split(self.settings['EXTRACTION_SEPARATOR'])
                page['images'] = images
                
                # Check for missing alt text
                if 'images_missing_alt' in row and row['images_missing_alt']:
                    missing_alt = row['images_missing_alt'].split(self.settings['EXTRACTION_SEPARATOR'])
                    page['images_missing_alt'] = missing_alt
            
            # Determine if it's an internal URL
            page['is_internal'] = self._is_same_domain(page['url'], self.start_urls[0])
            
            # Mark broken links (4xx and 5xx status codes)
            status_code = page.get('status_code')
            if status_code and (status_code >= 400):
                page['is_broken'] = True
                if status_code >= 400 and status_code < 500:
                    page['error_type'] = 'Client Error'
                    page['error_message'] = f'HTTP {status_code} Client Error'
                elif status_code >= 500:
                    page['error_type'] = 'Server Error'
                    page['error_message'] = f'HTTP {status_code} Server Error'
            
            # Add to results
            results['pages'].append(page)
        
        return results
    
    def _run_custom_crawler(self, start_url):
        """Custom crawler implementation as fallback."""
        results = {'pages': []}
        visited_urls = set()
        urls_to_crawl = [(start_url, '', 0)]  # (url, referring_url, depth)
        
        base_domain = self._get_domain(start_url)
        
        while urls_to_crawl:
            url, referring_url, depth = urls_to_crawl.pop(0)
            
            # Normalize the URL to handle trailing slashes consistently
            url = self._normalize_url(url)

            # Skip if already visited or max depth reached
            if url in visited_urls or depth > self.max_depth:
                continue
            
            visited_urls.add(url)
            
            # Check if we've reached the maximum number of URLs to crawl
            if self.max_urls and len(visited_urls) >= self.max_urls:
                break
            
            try:
                # Fetch the page with retry logic
                response = self._fetch_with_retry(url)
                
                # Determine if the URL is internal or external
                is_internal = self._get_domain(url) == base_domain
                
                # Extract page data
                page_data = {
                    'url': url,
                    'status_code': response.status_code,
                    'title': '',
                    'is_internal': is_internal,
                    'referring_page': referring_url
                }
                
                # Only process content for successful responses
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Extract title
                    title_tag = soup.find('title')
                    page_data['title'] = title_tag.text.strip() if title_tag else ''
                    
                    # Extract meta tags
                    meta = {}
                    for tag_name in self.extract_meta_tags:
                        if tag_name == 'title':
                            continue  # Already handled above
                        
                        meta_tag = soup.find('meta', attrs={'name': tag_name}) or soup.find('meta', attrs={'property': tag_name})
                        if meta_tag and meta_tag.get('content'):
                            meta[tag_name] = meta_tag.get('content')
                    
                    # Check for missing meta tags - use same format as official crawler
                    # Only check internal pages and only check title and description
                    missing_meta_tags = {}
                    if is_internal:  # Only check meta tags for internal pages
                        if 'title' in self.extract_meta_tags:
                            if not page_data['title']:
                                missing_meta_tags['title'] = 'Missing page title'
                            elif len(page_data['title']) < 10:
                                missing_meta_tags['title'] = f"Title too short ({len(page_data['title'])} chars)"
                            elif len(page_data['title']) > 60:
                                missing_meta_tags['title'] = f"Title too long ({len(page_data['title'])} chars)"
                        
                        if 'description' in self.extract_meta_tags:
                            if 'description' not in meta:
                                missing_meta_tags['description'] = 'Missing meta description'
                            elif len(meta.get('description', '')) < 50:
                                missing_meta_tags['description'] = f"Description too short ({len(meta.get('description', ''))} chars)"
                            elif len(meta.get('description', '')) > 160:
                                missing_meta_tags['description'] = f"Description too long ({len(meta.get('description', ''))} chars)"
                    
                    if missing_meta_tags:
                        page_data['missing_meta_tags'] = missing_meta_tags
                    
                    # Add meta data if available
                    if meta:
                        page_data['meta'] = meta
                    
                    # Extract images if configured
                    if self.extract_images:
                        images = []
                        images_missing_alt = []
                        
                        for img in soup.find_all('img'):
                            src = img.get('src')
                            if not src:
                                continue
                                
                            img_data = {
                                'src': src,
                                'alt': img.get('alt', '')
                            }
                            images.append(img_data)
                            
                            # Check for missing alt text
                            if self.extract_alt_text and not img.get('alt'):
                                images_missing_alt.append(src)
                        
                        if images:
                            page_data['images'] = images
                        if images_missing_alt:
                            page_data['images_missing_alt'] = images_missing_alt
                    
                    # Extract links for further crawling if internal
                    if is_internal and depth < self.max_depth:
                        for a in soup.find_all('a'):
                            href = a.get('href')
                            if not href or href.startswith('#') or href.startswith('javascript:'):
                                continue
                                
                            # Skip tel: and mailto: links
                            if href.lower().startswith(('tel:', 'mailto:')):
                                continue
                                
                            # Normalize URL
                            if not href.startswith(('http://', 'https://')):
                                href = urljoin(url, href)
                            
                            href = self._normalize_url(href)

                            # Only add to crawl queue if it's internal or we're checking external links
                            is_link_internal = self._get_domain(href) == base_domain
                            if is_link_internal or self.check_external_links:
                                if href not in visited_urls:
                                    urls_to_crawl.append((href, url, depth + 1))
                
                # Add the page to results
                results['pages'].append(page_data)
                
            except Exception as e:
                # Add as broken page
                logger.error(f"Error crawling {url}: {e}")
                results['pages'].append({
                    'url': url,
                    'status_code': 0,
                    'title': '',
                    'is_internal': self._get_domain(url) == base_domain,
                    'referring_page': referring_url,
                    'is_broken': True,
                    'error_message': str(e)
                })
        
        return results
    
    def _fetch_with_retry(self, url):
        """Fetch a URL with retry logic and exponential backoff."""
        headers = {'User-Agent': self.user_agent}
        
        for attempt in range(self.retries):
            try:
                response = requests.get(url, headers=headers, timeout=self.timeout)
                return response
            except Exception as e:
                if attempt < self.retries - 1:
                    # Wait with exponential backoff
                    wait_time = self.backoff_base * (2 ** attempt)
                    time.sleep(wait_time)
                else:
                    raise
    
    def _get_domain(self, url):
        """Extract domain from URL."""
        try:
            return urlparse(url).netloc.lower().replace('www.', '')
        except:
            return ''
    
    def _is_same_domain(self, url, base_url):
        """Check if two URLs have the same domain, accounting for www subdomain."""
        try:
            url_domain = self._get_domain(url)
            base_domain = self._get_domain(base_url)
            
            # Remove www. if present for comparison
            if url_domain.startswith('www.'):
                url_domain = url_domain[4:]
            if base_domain.startswith('www.'):
                base_domain = base_domain[4:]
                
            return url_domain == base_domain
        except:
            return False
    
    def crawl(self, url):
        """Legacy method for compatibility with the previous API."""
        self.configure({'start_urls': [url]})
        result = self.run()
        
        # Find the page data for this URL
        page_data = next((page for page in result.get('pages', []) if page['url'] == url), None)
        
        if not page_data:
            # If URL wasn't found in results, create a basic result
            return {
                'url': url,
                'status_code': 0,
                'title': '',
                'internal_links': [],
                'external_links': []
            }
        
        # Extract internal and external links
        internal_links = []
        external_links = []
        
        base_domain = self._get_domain(url)
        
        for link_page in result.get('pages', []):
            link_url = link_page.get('url')
            if not link_url or link_url == url:
                continue
                
            is_internal = self._get_domain(link_url) == base_domain
            if is_internal:
                internal_links.append(link_url)
            else:
                external_links.append(link_url)
        
        return {
            'url': url,
            'status_code': page_data.get('status_code', 0),
            'title': page_data.get('title', ''),
            'internal_links': internal_links,
            'external_links': external_links
        }
    
    def fetch(self, url):
        """Fetch a URL and return basic information."""
        try:
            response = self._fetch_with_retry(url)
            return {
                'status_code': response.status_code,
                'content': response.text
            }
        except Exception as e:
            return {
                'status_code': 0,
                'error': str(e)
            }

# Create a singleton instance for easy import
crawler = GreenflareWrapper() 