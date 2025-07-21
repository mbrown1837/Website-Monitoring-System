import sys
import os
import logging
import json # For potentially pretty-printing dicts in logs if needed

# Add src to path to allow direct import of CrawlerModule
# Assuming test script is in project root, so '.' should work for src.
# If test_crawler_links.py is in /app, and src is in /app/src, this is fine.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from src.crawler_module import CrawlerModule
from src.logger_setup import setup_logging # Assuming logger_setup is in src

# Setup logging to capture DEBUG level
try:
    # Attempt to use the project's logger setup, configured for DEBUG
    logger = setup_logging(config_path='src/config/config.yaml', log_level_console=logging.DEBUG, log_to_file=False)
    # Ensure the logger for crawler_module itself is also at DEBUG
    logging.getLogger('src.crawler_module').setLevel(logging.DEBUG)
    # Also set the root logger to DEBUG to catch everything if specific loggers are not hit.
    logging.getLogger().setLevel(logging.DEBUG)
    logger.info("Project-specific logger setup complete with DEBUG level.")
except Exception as e:
    print(f"Could not set up project logging with DEBUG, using basic: {e}")
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger("TestRunner")
    # Ensure the module's logger is also set to DEBUG if basicConfig is used
    logging.getLogger('src.crawler_module').setLevel(logging.DEBUG)
    logger.info("Basic logger setup complete with DEBUG level.")


if __name__ == "__main__":
    # Ensure the 'data' directory exists for the database
    data_dir = 'data'
    if not os.path.exists(data_dir):
        try:
            os.makedirs(data_dir)
            logger.info(f"Created data directory: {os.path.abspath(data_dir)}")
        except Exception as e:
            logger.error(f"Failed to create data directory {data_dir}: {e}")
            sys.exit(1) # Exit if we can't create essential directory

    # Instantiate CrawlerModule - this might pick up config from a default path
    # It seems CrawlerModule looks for 'config/config.yaml' relative to its own location if no path is given.
    # Let's assume src/config/config.yaml is the intended default.
    # If CrawlerModule's __init__ has default config_path='config/config.yaml',
    # and it's relative to project root, this should be fine if test script is at root.
    # If it's relative to crawler_module.py, it would be 'config/config.yaml' from 'src/'
    # The provided logger setup uses 'src/config/config.yaml', so we assume this path is valid from project root.

    # To be safe, let's ensure CrawlerModule can find its config if it uses a relative path from its own location.
    # However, the logger setup implies config is at 'src/config/config.yaml' from project root.
    # We will rely on the default constructor of CrawlerModule which should use get_config()
    # which in turn tries to find 'config/config.yaml' or 'src/config/config.yaml'.

    crawler = CrawlerModule()
    website_id = "test_tpcbuild_links"
    url_to_crawl = "https://tpcbuild.com/"

    logger.info(f"Starting test crawl for {url_to_crawl} with DEBUG logging enabled for relevant modules.")

    try:
        results = crawler.crawl_website(
            website_id=website_id,
            url=url_to_crawl,
            max_depth=2,
            respect_robots=False,
            check_external_links=True, # Set to True to check processing of external links
            crawl_only=False
        )

        logger.info("Crawl completed. Results summary:")
        logger.info(f"Total pages found in results['all_pages']: {len(results.get('all_pages', []))}")

        # Display initial page's classification from 'all_pages'
        # Normalize the target URL the same way the crawler does for a fair comparison
        normalized_initial_url = crawler._normalize_url(url_to_crawl)
        logger.info(f"Normalized initial URL for lookup: {normalized_initial_url}")

        initial_page_info = next((p for p in results.get('all_pages', []) if p['url'] == normalized_initial_url), None)
        if initial_page_info:
            logger.info(f"Initial URL ({normalized_initial_url}) classification in all_pages: is_internal={initial_page_info.get('is_internal')}")
            if not initial_page_info.get('is_internal'):
                logger.error(f"CRITICAL: Initial URL {normalized_initial_url} IS MARKED AS EXTERNAL IN RESULTS!")
        else:
            logger.warning(f"Initial URL ({normalized_initial_url}) not found in all_pages list. This is unexpected.")
            # Log all page URLs if initial not found, for debugging
            all_page_urls_in_results = [p.get('url') for p in results.get('all_pages', [])]
            logger.debug(f"All page URLs found in results: {all_page_urls_in_results}")


        logger.info(f"Broken links: {len(results.get('broken_links', []))}")
        # Verbose broken link logging, uncomment if needed during intense debugging
        # for link in results.get('broken_links', []):
        #     logger.debug(f"  Broken: {link.get('url')}, Status: {link.get('status_code')}, Error: {link.get('error_message')}, Internal: {link.get('is_internal')}, Referring: {link.get('referring_page')}")

        logger.info(f"Missing meta tags entries: {len(results.get('missing_meta_tags', []))}")
        # Verbose meta tag logging, uncomment if needed
        # for tag_info in results.get('missing_meta_tags', []):
        #    logger.debug(f"  Meta Issue: URL: {tag_info.get('url')}, Type: {tag_info.get('tag_type')}, Suggestion: {tag_info.get('suggestion')}, Unreachable: {tag_info.get('is_unreachable')}")

    except Exception as e:
        logger.error(f"Test crawl failed with exception: {type(e).__name__}: {e}", exc_info=True)
