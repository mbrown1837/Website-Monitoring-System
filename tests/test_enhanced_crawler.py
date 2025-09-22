#!/usr/bin/env python
"""
Test script for the enhanced Greenflare crawler implementation.
This script verifies that our crawler correctly handles all the issues identified
in the performance discrepancy between standalone Greenflare and our integration.
"""

import os
import sys
import json
import logging
from urllib.parse import urlparse

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
from src.greenflare_crawler import GreenflareWrapper

def test_crawler_initialization():
    """Test that the crawler initializes correctly."""
    logger.info("Testing crawler initialization...")
    
    try:
        # Initialize the crawler module
        crawler_module = CrawlerModule()
        assert crawler_module is not None, "CrawlerModule failed to initialize"
        assert crawler_module.bot is not None, "Bot is not initialized"
        
        logger.info("✓ Crawler initialization successful")
        return crawler_module
    except Exception as e:
        logger.error(f"✗ Crawler initialization failed: {e}")
        raise

def test_direct_crawler():
    """Test the GreenflareWrapper directly."""
    logger.info("Testing direct GreenflareWrapper...")
    
    try:
        # Initialize the wrapper
        crawler = GreenflareWrapper(
            user_agent="Test Crawler/1.0",
            retries=3,
            timeout=30,
            max_depth=2,
            check_external_links=True
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
        
        # Run the crawler
        logger.info(f"Starting test crawl of {test_url}")
        results = crawler.run()
        
        # Verify results
        assert 'pages' in results, "Results should contain 'pages'"
        assert len(results['pages']) > 0, "No pages were crawled"
        
        # Log results
        logger.info(f"✓ Direct crawler test successful - found {len(results['pages'])} pages")
        
        # Return the results for further inspection
        return results
    except Exception as e:
        logger.error(f"✗ Direct crawler test failed: {e}")
        raise

def test_full_crawl(crawler_module, test_url="https://tpcbuild.com"):
    """Test a full crawl with the CrawlerModule."""
    logger.info(f"Testing full crawl of {test_url}...")
    
    try:
        # Perform the crawl
        results = crawler_module.crawl_website(
            website_id="test-site",
            url=test_url,
            max_depth=2,
            respect_robots=True,
            check_external_links=True
        )
        
        # Verify results
        assert results is not None, "Crawl results should not be None"
        assert "all_pages" in results, "Results should contain 'all_pages'"
        assert len(results["all_pages"]) > 0, "No pages were crawled"
        
        # Log key statistics
        logger.info(f"Pages crawled: {results['crawl_stats']['pages_crawled']}")
        logger.info(f"Broken links found: {len(results['broken_links'])}")
        logger.info(f"Missing meta tags found: {len(results['missing_meta_tags'])}")
        logger.info(f"Status code counts: {results['crawl_stats']['status_code_counts']}")
        
        # Save results to a file for inspection
        with open('enhanced_crawl_results.json', 'w') as f:
            # Convert sets to lists for JSON serialization
            serializable_results = results.copy()
            if isinstance(serializable_results.get("internal_urls"), set):
                serializable_results["internal_urls"] = list(serializable_results["internal_urls"])
            if isinstance(serializable_results.get("external_urls"), set):
                serializable_results["external_urls"] = list(serializable_results["external_urls"])
            
            json.dump(serializable_results, f, indent=2)
            
        logger.info(f"✓ Full crawl test successful - results saved to enhanced_crawl_results.json")
        
        # Return the results for further inspection
        return results
    except Exception as e:
        logger.error(f"✗ Full crawl test failed: {e}")
        raise

def test_broken_link_detection(crawler_module, test_url="https://httpstat.us"):
    """Test detection of broken links."""
    logger.info(f"Testing broken link detection using {test_url}...")
    
    try:
        # Perform the crawl
        results = crawler_module.crawl_website(
            website_id="test-broken-links",
            url=test_url,
            max_depth=1,
            respect_robots=True,
            check_external_links=True
        )
        
        # Verify results
        assert results is not None, "Crawl results should not be None"
        assert "broken_links" in results, "Results should contain 'broken_links'"
        
        # Check if any 4xx or 5xx links were detected
        broken_links = results["broken_links"]
        has_broken_links = any(
            link.get("status_code", 0) >= 400 
            for link in broken_links
        )
        
        if has_broken_links:
            logger.info(f"✓ Successfully detected {len(broken_links)} broken links")
            
            # Log the first few broken links
            for i, link in enumerate(broken_links[:5]):
                logger.info(f"  Broken link {i+1}: {link['url']} - Status: {link['status_code']}")
                
            # Save broken links to a file
            with open('broken_links_test.json', 'w') as f:
                json.dump(broken_links, f, indent=2)
                
            logger.info("Broken links saved to broken_links_test.json")
        else:
            logger.warning(f"No broken links detected at {test_url}")
        
        return broken_links
    except Exception as e:
        logger.error(f"✗ Broken link detection test failed: {e}")
        raise

def test_meta_tag_detection(crawler_module, test_url="https://example.com"):
    """Test detection of missing meta tags."""
    logger.info(f"Testing meta tag detection using {test_url}...")
    
    try:
        # Perform the crawl
        results = crawler_module.crawl_website(
            website_id="test-meta-tags",
            url=test_url,
            max_depth=1,
            respect_robots=True,
            check_external_links=False
        )
        
        # Verify results
        assert results is not None, "Crawl results should not be None"
        assert "missing_meta_tags" in results, "Results should contain 'missing_meta_tags'"
        
        # Check if any missing meta tags were detected
        missing_tags = results["missing_meta_tags"]
        
        logger.info(f"Found {len(missing_tags)} missing meta tags")
        
        # Log the missing meta tags
        for i, tag in enumerate(missing_tags):
            logger.info(f"  Missing tag {i+1}: {tag['url']} - Type: {tag['type']}")
            
        # Save missing tags to a file
        with open('missing_meta_tags_test.json', 'w') as f:
            json.dump(missing_tags, f, indent=2)
            
        logger.info("Missing meta tags saved to missing_meta_tags_test.json")
        
        return missing_tags
    except Exception as e:
        logger.error(f"✗ Meta tag detection test failed: {e}")
        raise

def test_connection_error_handling(crawler_module):
    """Test handling of connection errors."""
    logger.info("Testing connection error handling...")
    
    try:
        # Use a non-existent domain that should cause a connection error
        test_url = "https://this-domain-should-not-exist-12345.com"
        
        # Perform the crawl
        results = crawler_module.crawl_website(
            website_id="test-connection-error",
            url=test_url,
            max_depth=1,
            respect_robots=True,
            check_external_links=False
        )
        
        # Verify results
        assert results is not None, "Crawl results should not be None"
        
        # Check if the error was properly handled
        if "error" in results:
            logger.info(f"✓ Connection error properly handled: {results['error']}")
        else:
            # Check broken links for connection errors
            connection_errors = [
                link for link in results.get("broken_links", [])
                if link.get("error_type") == "Connection Error"
            ]
            
            if connection_errors:
                logger.info(f"✓ Connection error properly recorded as broken link: {connection_errors[0]}")
            else:
                logger.warning("No connection error detected in results")
        
        return results
    except Exception as e:
        logger.error(f"✗ Connection error handling test failed: {e}")
        raise

def test_tel_url_handling(crawler_module, test_url="https://tpcbuild.com"):
    """Test handling of tel: URLs."""
    logger.info(f"Testing tel: URL handling using {test_url}...")
    
    try:
        # Perform the crawl
        results = crawler_module.crawl_website(
            website_id="test-tel-urls",
            url=test_url,
            max_depth=2,
            respect_robots=True,
            check_external_links=True
        )
        
        # Look for tel: URLs in all pages and broken links
        tel_urls = []
        
        # Check in broken links
        for link in results.get("broken_links", []):
            if link.get("url", "").startswith("tel:"):
                tel_urls.append(link)
        
        # Check in all pages
        for page in results.get("all_pages", []):
            if page.get("url", "").startswith("tel:"):
                tel_urls.append(page)
        
        if tel_urls:
            logger.info(f"✓ Found {len(tel_urls)} tel: URLs")
            for url in tel_urls[:5]:  # Show first 5
                logger.info(f"  Tel URL: {url.get('url')} - Status: {url.get('status_code')}")
        else:
            logger.warning(f"No tel: URLs found on {test_url}")
        
        return tel_urls
    except Exception as e:
        logger.error(f"✗ Tel URL handling test failed: {e}")
        raise

def compare_with_previous_results():
    """Compare the new results with previous test results."""
    logger.info("Comparing with previous results...")
    
    try:
        # Check if previous results exist
        if not os.path.exists('test_crawl_results.json'):
            logger.warning("No previous test results found to compare")
            return
        
        # Check if new results exist
        if not os.path.exists('enhanced_crawl_results.json'):
            logger.warning("No new test results found to compare")
            return
        
        # Load both result sets
        with open('test_crawl_results.json', 'r') as f:
            previous_results = json.load(f)
            
        with open('enhanced_crawl_results.json', 'r') as f:
            new_results = json.load(f)
        
        # Compare key metrics
        logger.info("Comparing key metrics:")
        
        prev_pages = len(previous_results.get("all_pages", []))
        new_pages = len(new_results.get("all_pages", []))
        logger.info(f"  Pages crawled: {prev_pages} -> {new_pages}")
        
        prev_broken = len(previous_results.get("broken_links", []))
        new_broken = len(new_results.get("broken_links", []))
        logger.info(f"  Broken links: {prev_broken} -> {new_broken}")
        
        prev_missing = len(previous_results.get("missing_meta_tags", []))
        new_missing = len(new_results.get("missing_meta_tags", []))
        logger.info(f"  Missing meta tags: {prev_missing} -> {new_missing}")
        
        # Compare status code counts
        prev_status = previous_results.get("crawl_stats", {}).get("status_code_counts", {})
        new_status = new_results.get("crawl_stats", {}).get("status_code_counts", {})
        
        logger.info("  Status code counts:")
        all_codes = set(list(prev_status.keys()) + list(new_status.keys()))
        for code in sorted(all_codes):
            prev_count = prev_status.get(code, 0)
            new_count = new_status.get(code, 0)
            logger.info(f"    {code}: {prev_count} -> {new_count}")
        
        # Check for improvements
        if new_pages > prev_pages:
            logger.info("✓ IMPROVEMENT: More pages crawled")
        
        if new_broken > prev_broken:
            logger.info("✓ IMPROVEMENT: More broken links detected")
        
        if new_missing > prev_missing:
            logger.info("✓ IMPROVEMENT: More missing meta tags detected")
        
        if '0' in prev_status and ('0' not in new_status or new_status['0'] < prev_status['0']):
            logger.info("✓ IMPROVEMENT: Fewer connection errors")
            
    except Exception as e:
        logger.error(f"✗ Comparison failed: {e}")

def main():
    """Run all tests."""
    logger.info("Starting enhanced Greenflare crawler tests")
    
    try:
        # Test crawler initialization
        crawler_module = test_crawler_initialization()
        
        # Test direct crawler
        direct_results = test_direct_crawler()
        
        # Test full crawl
        full_results = test_full_crawl(crawler_module)
        
        # Test broken link detection
        broken_links = test_broken_link_detection(crawler_module)
        
        # Test meta tag detection
        missing_tags = test_meta_tag_detection(crawler_module)
        
        # Test connection error handling
        connection_results = test_connection_error_handling(crawler_module)
        
        # Test tel: URL handling
        tel_urls = test_tel_url_handling(crawler_module)
        
        # Compare with previous results
        compare_with_previous_results()
        
        logger.info("All tests completed successfully!")
        
    except Exception as e:
        logger.error(f"Tests failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 