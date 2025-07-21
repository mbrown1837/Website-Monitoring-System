"""
Mock implementation of the Greenflare library for testing purposes.
This is a simplified version of the Greenflare crawler library.
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
import random

class Crawler:
    """Mock Greenflare Crawler class."""
    
    def __init__(self, user_agent=None, retries=3, backoff_base=0.3, timeout=30):
        """Initialize the crawler with configurable parameters."""
        self.user_agent = user_agent or "Greenflare/1.0"
        self.retries = retries
        self.backoff_base = backoff_base
        self.timeout = timeout
        self.config = {}
        
    def configure(self, config):
        """Configure the crawler with specific settings."""
        self.config = config
        return self
        
    def run(self):
        """Run the crawler and return results."""
        results = {
            'pages': []
        }
        
        # Get the start URLs from the configuration
        start_urls = self.config.get('start_urls', [])
        max_depth = self.config.get('max_depth', 2)
        
        # Process each start URL
        for url in start_urls:
            self._crawl_url(url, results, 0, max_depth)
            
        return results
        
    def _crawl_url(self, url, results, current_depth, max_depth):
        """Crawl a URL and add it to the results."""
        # Skip if we've reached the maximum depth
        if current_depth > max_depth:
            return
            
        # Skip if we've already processed this URL
        if any(page['url'] == url for page in results['pages']):
            return
            
        try:
            # Fetch the page
            response = self._fetch(url)
            
            # Extract page data
            page_data = {
                'url': url,
                'status_code': response.status_code,
                'title': self._extract_title(response.text),
                'meta': self._extract_meta_tags(response.text),
                'images': self._extract_images(response.text, url),
                'referring_page': '',
                'internal_links': [],
                'external_links': []
            }
            
            # Extract links
            if current_depth < max_depth:
                internal_links, external_links = self._extract_links(response.text, url)
                page_data['internal_links'] = internal_links
                page_data['external_links'] = external_links
                
                # Add the page to the results
                results['pages'].append(page_data)
                
                # Process internal links
                for link in internal_links[:5]:  # Limit to 5 links for testing
                    self._crawl_url(link, results, current_depth + 1, max_depth)
                    
                # Check external links if configured
                if self.config.get('check_external_links', False):
                    for link in external_links[:3]:  # Limit to 3 links for testing
                        try:
                            ext_response = self._fetch(link, timeout=5)
                            results['pages'].append({
                                'url': link,
                                'status_code': ext_response.status_code,
                                'title': '',
                                'referring_page': url,
                                'is_external': True
                            })
                        except Exception:
                            # Add as broken link
                            results['pages'].append({
                                'url': link,
                                'status_code': 0,
                                'title': '',
                                'referring_page': url,
                                'is_external': True,
                                'is_broken': True
                            })
            else:
                # Just add the page without processing links
                results['pages'].append(page_data)
                
        except Exception as e:
            # Add as broken page
            results['pages'].append({
                'url': url,
                'status_code': 0,
                'title': '',
                'referring_page': '',
                'is_broken': True,
                'error_message': str(e)
            })
            
    def _fetch(self, url, timeout=None):
        """Fetch a URL with retry logic."""
        headers = {'User-Agent': self.user_agent}
        timeout = timeout or self.timeout
        
        for attempt in range(self.retries):
            try:
                response = requests.get(url, headers=headers, timeout=timeout)
                return response
            except Exception:
                if attempt < self.retries - 1:
                    # Wait with exponential backoff
                    wait_time = self.backoff_base * (2 ** attempt)
                    time.sleep(wait_time)
                else:
                    raise
                    
    def _extract_title(self, html):
        """Extract the title from HTML."""
        soup = BeautifulSoup(html, 'html.parser')
        title_tag = soup.find('title')
        return title_tag.text if title_tag else ''
        
    def _extract_meta_tags(self, html):
        """Extract meta tags from HTML."""
        soup = BeautifulSoup(html, 'html.parser')
        meta_tags = {}
        
        # Extract standard meta tags
        for tag in soup.find_all('meta'):
            name = tag.get('name', tag.get('property', ''))
            content = tag.get('content', '')
            if name and content:
                meta_tags[name] = content
                
        return meta_tags
        
    def _extract_images(self, html, base_url):
        """Extract images from HTML."""
        soup = BeautifulSoup(html, 'html.parser')
        images = []
        
        for img in soup.find_all('img'):
            src = img.get('src', '')
            if src:
                images.append({
                    'src': urljoin(base_url, src),
                    'alt': img.get('alt', '')
                })
                
        return images
        
    def _extract_links(self, html, base_url):
        """Extract links from HTML."""
        soup = BeautifulSoup(html, 'html.parser')
        internal_links = []
        external_links = []
        
        base_domain = urlparse(base_url).netloc
        
        for a in soup.find_all('a'):
            href = a.get('href', '')
            if href and not href.startswith('#') and not href.startswith('javascript:'):
                absolute_url = urljoin(base_url, href)
                domain = urlparse(absolute_url).netloc
                
                if domain == base_domain:
                    internal_links.append(absolute_url)
                else:
                    external_links.append(absolute_url)
                    
        return internal_links, external_links
        
    def crawl(self, url, force=False):
        """Legacy method for compatibility with YiraBot."""
        response = self._fetch(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        internal_links, external_links = self._extract_links(response.text, url)
        
        return {
            'url': url,
            'status_code': response.status_code,
            'title': self._extract_title(response.text),
            'internal_links': internal_links,
            'external_links': external_links
        }
        
    def fetch(self, url):
        """Fetch a URL and return basic information."""
        try:
            response = self._fetch(url)
            return {
                'status_code': response.status_code,
                'content': response.text
            }
        except Exception as e:
            return {
                'status_code': 0,
                'error': str(e)
            }
            
    def seo_analysis(self, url):
        """Legacy method for compatibility with YiraBot."""
        try:
            response = self._fetch(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract title
            title = self._extract_title(response.text)
            
            # Extract meta description
            meta_desc = ''
            meta_desc_tag = soup.find('meta', attrs={'name': 'description'})
            if meta_desc_tag:
                meta_desc = meta_desc_tag.get('content', '')
                
            # Find images without alt text
            images_without_alt = []
            for img in soup.find_all('img'):
                if not img.get('alt'):
                    src = img.get('src', '')
                    if src:
                        images_without_alt.append(urljoin(url, src))
                        
            return {
                'title_text': title,
                'title_length': len(title) if title else 0,
                'meta_desc_text': meta_desc,
                'meta_desc_length': len(meta_desc) if meta_desc else 0,
                'images_without_alt': images_without_alt,
                'has_h1': bool(soup.find('h1')),
                'has_canonical': bool(soup.find('link', attrs={'rel': 'canonical'}))
            }
        except Exception:
            return {
                'title_text': '',
                'title_length': 0,
                'meta_desc_text': '',
                'meta_desc_length': 0,
                'images_without_alt': [],
                'has_h1': False,
                'has_canonical': False
            } 