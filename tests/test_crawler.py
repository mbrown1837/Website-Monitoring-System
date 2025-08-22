import sys
import os
# Add src to path to allow direct import of CrawlerModule
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.', 'src')))

from crawler_module import CrawlerModule
from logger_setup import setup_logging
import logging

# Setup basic logging to capture output for review
# You might need to adjust logger setup if it's complex in the actual project
# For simplicity, we'll try to use the project's logger if possible,
# otherwise, a basic stdout logger.
try:
    # Assuming logger_setup.py is in src and callable
    logger = setup_logging(log_level_console=logging.DEBUG, log_to_file=False)
except Exception as e:
    print(f"Could not set up project logging, using basic: {e}")
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)


if __name__ == "__main__":
    # Ensure the 'data' directory exists for the database
    if not os.path.exists('data'):
        os.makedirs('data')

    crawler = CrawlerModule()
    website_id = "test_tpcbuild"
    url_to_crawl = "https://tpcbuild.com/"

    logger.info(f"Starting test crawl for {url_to_crawl}")

    try:
        results = crawler.crawl_website(
            website_id=website_id,
            url=url_to_crawl,
            max_depth=2,  # Keep depth limited for testing
            respect_robots=False, # Try to crawl more for testing
            check_external_links=True,
            crawl_only=False # We want SEO analysis too
        )

        logger.info("Crawl completed. Results summary:")
        logger.info(f"Total pages found: {len(results.get('all_pages', []))}")
        logger.info(f"Broken links: {len(results.get('broken_links', []))}")
        for link in results.get('broken_links', []):
            logger.info(f"  Broken: {link.get('url')}, Status: {link.get('status_code')}, Error: {link.get('error_message')}, Internal: {link.get('is_internal')}, Referring: {link.get('referring_page')}")

        logger.info(f"Missing meta tags entries: {len(results.get('missing_meta_tags', []))}")
        for tag_info in results.get('missing_meta_tags', []):
            logger.info(f"  Meta Issue: URL: {tag_info.get('url')}, Type: {tag_info.get('tag_type')}, Suggestion: {tag_info.get('suggestion')}, Unreachable: {tag_info.get('is_unreachable')}")

        # Log some normalization and internal/external check examples if they appear in DEBUG logs
        # This part will rely on the logs produced by the crawler itself.
        logger.info("Check DEBUG logs for normalization and internal/external URL checks.")

    except Exception as e:
        logger.error(f"Test crawl failed with exception: {type(e).__name__}: {e}", exc_info=True)
