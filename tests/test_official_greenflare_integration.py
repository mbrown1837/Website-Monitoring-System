#!/usr/bin/env python
"""
Test script for the enhanced Greenflare integration with the official code.
This script verifies that our integration correctly leverages the official Greenflare crawler.
"""

import os
import sys
import json
import logging
from urllib.parse import urlparse
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Ensure the src directory is in the Python path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# Import our enhanced Greenflare wrapper
from src.greenflare_crawler import GreenflareWrapper, GREENFLARE_AVAILABLE

def test_greenflare_availability():
    """Test if the official Greenflare package is available."""
    logger.info("Testing Greenflare availability...")
    
    if GREENFLARE_AVAILABLE:
        logger.info("✓ Official Greenflare package is available")
    else:
        logger.warning("✗ Official Greenflare package is NOT available - will use fallback implementation")
    
    return GREENFLARE_AVAILABLE

def test_crawler_initialization():
    """Test that the crawler initializes correctly."""
    logger.info("Testing crawler initialization...")
    
    try:
        # Initialize the crawler
        crawler = GreenflareWrapper(
            user_agent="Test Crawler/1.0",
            retries=3,
            timeout=30,
            max_depth=2
        )
        
        assert crawler is not None, "Crawler failed to initialize"
        
        if GREENFLARE_AVAILABLE:
            assert crawler.official_crawler is not None, "Official crawler component is not initialized"
            assert crawler.lock is not None, "Thread lock is not initialized"
            assert crawler.settings is not None, "Settings are not initialized"
        
        logger.info("✓ Crawler initialization successful")
        return crawler
    except Exception as e:
        logger.error(f"✗ Crawler initialization failed: {e}")
        raise

def test_crawler_configuration():
    """Test that the crawler configures correctly."""
    logger.info("Testing crawler configuration...")
    
    try:
        # Initialize the crawler
        crawler = GreenflareWrapper(
            user_agent="Test Crawler/1.0",
            retries=3,
            timeout=30,
            max_depth=2
        )
        
        # Configure for a test crawl
        test_url = "https://example.com"
        crawler.configure({
            'start_urls': [test_url],
            'max_depth': 2,
            'check_external_links': True,
            'meta_tags': ["title", "description", "keywords"],
            'extract_images': True,
            'extract_alt_text': True
        })
        
        assert crawler.start_urls == [test_url], "Start URLs not configured correctly"
        assert crawler.max_depth == 2, "Max depth not configured correctly"
        assert crawler.extract_meta_tags == ["title", "description", "keywords"], "Meta tags not configured correctly"
        
        if GREENFLARE_AVAILABLE:
            assert crawler.settings['CUSTOM_CRAWL_DEPTH'] == 2, "Official crawler depth not configured correctly"
            assert crawler.settings['CHECK_EXTERNAL_LINKS'] == True, "External links check not configured correctly"
            assert crawler.settings['STARTING_URL'] == test_url, "Starting URL not configured correctly"
        
        logger.info("✓ Crawler configuration successful")
        return crawler
    except Exception as e:
        logger.error(f"✗ Crawler configuration failed: {e}")
        raise

def test_crawl_example_site():
    """Test crawling a simple site like example.com."""
    logger.info("Testing crawl of example.com...")
    
    try:
        # Initialize and configure the crawler
        crawler = GreenflareWrapper(
            user_agent="Test Crawler/1.0",
            retries=3,
            timeout=30,
            max_depth=1
        )
        
        crawler.configure({
            'start_urls': ["https://example.com"],
            'max_depth': 1,
            'check_external_links': True,
            'meta_tags': ["title", "description", "keywords"],
            'extract_images': True,
            'extract_alt_text': True
        })
        
        # Run the crawl
        start_time = time.time()
        results = crawler.run()
        end_time = time.time()
        
        # Verify results
        assert results is not None, "Crawl results should not be None"
        assert 'pages' in results, "Results should contain 'pages'"
        assert len(results['pages']) > 0, "No pages were crawled"
        
        # Log results
        logger.info(f"Crawl completed in {end_time - start_time:.2f} seconds")
        logger.info(f"Pages found: {len(results['pages'])}")
        
        # Check the first page
        first_page = results['pages'][0]
        logger.info(f"First page URL: {first_page['url']}")
        logger.info(f"First page title: {first_page.get('title', 'No title')}")
        logger.info(f"First page status code: {first_page.get('status_code', 0)}")
        
        # Save results to file
        with open('example_crawl_results.json', 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info("✓ Example site crawl successful")
        return results
    except Exception as e:
        logger.error(f"✗ Example site crawl failed: {e}")
        raise

def test_crawl_tpcbuild():
    """Test crawling tpcbuild.com (the site from the user's example)."""
    logger.info("Testing crawl of tpcbuild.com...")
    
    try:
        # Initialize and configure the crawler
        crawler = GreenflareWrapper(
            user_agent="Test Crawler/1.0",
            retries=3,
            timeout=30,
            max_depth=2
        )
        
        crawler.configure({
            'start_urls': ["https://tpcbuild.com"],
            'max_depth': 2,
            'check_external_links': True,
            'meta_tags': ["title", "description", "keywords"],
            'extract_images': True,
            'extract_alt_text': True
        })
        
        # Run the crawl
        start_time = time.time()
        results = crawler.run()
        end_time = time.time()
        
        # Verify results
        assert results is not None, "Crawl results should not be None"
        assert 'pages' in results, "Results should contain 'pages'"
        assert len(results['pages']) > 0, "No pages were crawled"
        
        # Log results
        logger.info(f"Crawl completed in {end_time - start_time:.2f} seconds")
        logger.info(f"Pages found: {len(results['pages'])}")
        
        # Count status codes
        status_counts = {}
        for page in results['pages']:
            status = page.get('status_code', 0)
            status_counts[status] = status_counts.get(status, 0) + 1
        
        logger.info(f"Status code counts: {status_counts}")
        
        # Count missing meta tags
        missing_title = sum(1 for page in results['pages'] if page.get('missing_title', False))
        missing_description = sum(1 for page in results['pages'] if page.get('missing_description', False))
        missing_keywords = sum(1 for page in results['pages'] if page.get('missing_keywords', False))
        
        logger.info(f"Missing titles: {missing_title}")
        logger.info(f"Missing descriptions: {missing_description}")
        logger.info(f"Missing keywords: {missing_keywords}")
        
        # Save results to file
        with open('tpcbuild_crawl_results.json', 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info("✓ tpcbuild.com crawl successful")
        return results
    except Exception as e:
        logger.error(f"✗ tpcbuild.com crawl failed: {e}")
        raise

def main():
    """Run all tests."""
    logger.info("Starting enhanced Greenflare integration tests")
    
    try:
        # Test Greenflare availability
        greenflare_available = test_greenflare_availability()
        
        # Test initialization
        crawler = test_crawler_initialization()
        
        # Test configuration
        configured_crawler = test_crawler_configuration()
        
        # Test crawling example.com
        example_results = test_crawl_example_site()
        
        # Test crawling tpcbuild.com
        if input("Do you want to test crawling tpcbuild.com? (y/n): ").lower() == 'y':
            tpcbuild_results = test_crawl_tpcbuild()
        
        logger.info("All tests completed successfully!")
        
    except Exception as e:
        logger.error(f"Tests failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 