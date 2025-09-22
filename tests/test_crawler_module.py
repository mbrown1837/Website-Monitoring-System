#!/usr/bin/env python
"""
Test script for the CrawlerModule with enhanced Greenflare integration.
This script verifies that the CrawlerModule correctly uses the enhanced Greenflare integration.
"""

import os
import sys
import json
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Ensure the src directory is in the Python path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# Import our crawler module
from src.crawler_module import CrawlerModule
from src.greenflare_crawler import GREENFLARE_AVAILABLE

def test_crawler_module_initialization():
    """Test that the crawler module initializes correctly."""
    logger.info("Testing crawler module initialization...")
    
    try:
        # Initialize the crawler module
        crawler_module = CrawlerModule()
        assert crawler_module is not None, "CrawlerModule failed to initialize"
        assert crawler_module.bot is not None, "Bot is not initialized"
        
        logger.info(f"Using official Greenflare: {GREENFLARE_AVAILABLE}")
        logger.info("✓ Crawler module initialization successful")
        return crawler_module
    except Exception as e:
        logger.error(f"✗ Crawler module initialization failed: {e}")
        raise

def test_crawl_website(crawler_module, url="https://example.com", max_depth=1):
    """Test crawling a website with the crawler module."""
    logger.info(f"Testing crawl of {url} with max_depth={max_depth}...")
    
    try:
        # Perform the crawl
        start_time = datetime.now()
        results = crawler_module.crawl_website(
            website_id="test-site",
            url=url,
            max_depth=max_depth,
            respect_robots=True,
            check_external_links=True
        )
        end_time = datetime.now()
        elapsed = (end_time - start_time).total_seconds()
        
        # Verify results
        assert results is not None, "Crawl results should not be None"
        assert "all_pages" in results, "Results should contain 'all_pages'"
        assert len(results["all_pages"]) > 0, "No pages were crawled"
        
        # Log key statistics
        logger.info(f"Crawl completed in {elapsed:.2f} seconds")
        logger.info(f"Pages crawled: {results['crawl_stats']['pages_crawled']}")
        logger.info(f"Broken links found: {len(results['broken_links'])}")
        logger.info(f"Missing meta tags found: {len(results['missing_meta_tags'])}")
        logger.info(f"Status code counts: {results['crawl_stats']['status_code_counts']}")
        
        # Save results to a file for inspection
        output_file = f"crawl_results_{url.replace('https://', '').replace('http://', '').replace('/', '_')}.json"
        with open(output_file, 'w') as f:
            # Convert sets to lists for JSON serialization
            serializable_results = results.copy()
            if isinstance(serializable_results.get("internal_urls"), set):
                serializable_results["internal_urls"] = list(serializable_results["internal_urls"])
            if isinstance(serializable_results.get("external_urls"), set):
                serializable_results["external_urls"] = list(serializable_results["external_urls"])
            
            json.dump(serializable_results, f, indent=2)
            
        logger.info(f"✓ Crawl successful - results saved to {output_file}")
        
        # Return the results for further inspection
        return results
    except Exception as e:
        logger.error(f"✗ Crawl failed: {e}")
        raise

def main():
    """Run all tests."""
    logger.info("Starting crawler module tests")
    
    try:
        # Test crawler module initialization
        crawler_module = test_crawler_module_initialization()
        
        # Test crawling example.com
        example_results = test_crawl_website(crawler_module, "https://example.com", max_depth=1)
        
        # Test crawling tpcbuild.com
        if input("Do you want to test crawling tpcbuild.com? (y/n): ").lower() == 'y':
            tpcbuild_results = test_crawl_website(crawler_module, "https://tpcbuild.com", max_depth=2)
        
        logger.info("All tests completed successfully!")
        
    except Exception as e:
        logger.error(f"Tests failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 