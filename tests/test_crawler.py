#!/usr/bin/env python
"""Test script for the Greenflare crawler integration."""
import os
import sys
import json

# Ensure the src directory is in the Python path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from src.crawler_module import CrawlerModule

def main():
    """Run a test crawl and print the results."""
    print("Testing Greenflare crawler integration...")
    
    # Initialize the crawler
    crawler = CrawlerModule()
    
    # Test website to crawl (use a reliable site for testing)
    test_url = "https://example.com"
    website_id = "test-site"
    
    # Run the crawl
    print(f"Crawling {test_url}...")
    results = crawler.crawl_website(
        website_id=website_id,
        url=test_url,
        max_depth=1,  # Keep depth small for testing
        respect_robots=False,
        check_external_links=True
    )
    
    # Print summary of results
    print("\nCrawl Results Summary:")
    print(f"Total pages crawled: {len(results['all_pages'])}")
    print(f"Broken links found: {len(results['broken_links'])}")
    print(f"Missing meta tags found: {len(results['missing_meta_tags'])}")
    
    # Print details of broken links (if any)
    if results['broken_links']:
        print("\nBroken Links:")
        for link in results['broken_links']:
            print(f"  - {link['url']} (Status: {link['status_code']}, Referring page: {link['referring_page']})")
    
    # Print details of missing meta tags (if any)
    if results['missing_meta_tags']:
        print("\nMissing Meta Tags:")
        for tag in results['missing_meta_tags']:
            print(f"  - {tag['url']}: {tag['type']} - {tag['details']}")
    
    # Save full results to a JSON file for inspection
    with open('test_crawl_results.json', 'w') as f:
        # Convert sets to lists for JSON serialization
        json_safe_results = results.copy()
        if "internal_urls" in json_safe_results and isinstance(json_safe_results["internal_urls"], set):
            json_safe_results["internal_urls"] = list(json_safe_results["internal_urls"])
        if "external_urls" in json_safe_results and isinstance(json_safe_results["external_urls"], set):
            json_safe_results["external_urls"] = list(json_safe_results["external_urls"])
        
        json.dump(json_safe_results, f, indent=2)
    
    print("\nFull results saved to test_crawl_results.json")

if __name__ == "__main__":
    main() 