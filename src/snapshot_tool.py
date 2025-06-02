import os
import hashlib
from datetime import datetime, timezone
import time
from urllib.parse import urlparse
from src.config_loader import get_config
from src.logger_setup import setup_logging

# Playwright imports
from playwright.sync_api import sync_playwright

logger = setup_logging()
config = get_config()

DEFAULT_SNAPSHOT_DIR = "data/snapshots"

def get_snapshot_directory():
    """Gets the snapshot directory from config, with a fallback."""
    path = config.get('snapshot_directory', DEFAULT_SNAPSHOT_DIR)
    if not os.path.isabs(path):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(project_root, path)
    
    if not os.path.exists(path):
        try:
            os.makedirs(path, exist_ok=True)
            logger.info(f"Created snapshot directory: {path}")
        except OSError as e:
            logger.error(f"Error creating snapshot directory {path}: {e}")
            raise # Or handle by returning a default/temp path
    return path

def save_html_snapshot(site_id: str, url: str, html_content: str, timestamp: datetime = None, is_baseline: bool = False) -> tuple[str | None, str | None]:
    """
    Saves a snapshot of the HTML content to a file.
    If is_baseline is True, saves to a dedicated baseline location with a fixed name.

    Args:
        site_id (str): The unique identifier for the website.
        url (str): The URL from which the content was fetched (for logging/metadata).
        html_content (str): The HTML content to save.
        timestamp (datetime, optional): The timestamp of when the content was fetched.
                                        Defaults to current UTC time if not provided.
                                        Used for regular snapshots, ignored for baseline filename.
        is_baseline (bool, optional): If True, save as a baseline snapshot.

    Returns:
        tuple[str | None, str | None]: (file_path, content_hash) if successful, (None, None) otherwise.
                                       file_path is the path to the saved HTML file.
                                       content_hash is the SHA256 hash of the HTML content.
    """
    if not html_content:
        logger.warning(f"Attempted to save an empty HTML snapshot for site ID {site_id} ({url}).")
        return None, None

    parsed_url = urlparse(url)
    domain_name = parsed_url.netloc.replace('.', '_').replace(':', '_')
    site_base_dir = os.path.join(get_snapshot_directory(), domain_name, site_id)

    if is_baseline:
        site_snapshot_dir = os.path.join(site_base_dir, "baseline")
        filename = "baseline.html"
        log_prefix = "Baseline HTML"
    else:
        site_snapshot_dir = os.path.join(site_base_dir, "html")
        if timestamp is None: # Should be provided for non-baseline, but fallback
            timestamp = datetime.now(timezone.utc)
        filename = f"{timestamp.strftime('%Y%m%d_%H%M%S_%f')}_utc.html"
        log_prefix = "HTML"
    
    try:
        os.makedirs(site_snapshot_dir, exist_ok=True)
    except OSError as e:
        logger.error(f"Could not create directory {site_snapshot_dir} for HTML snapshots: {e}")
        return None, None

    file_path = os.path.join(site_snapshot_dir, filename)

    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        content_hash = hashlib.sha256(html_content.encode('utf-8')).hexdigest()
        logger.info(f"Saved {log_prefix.lower()} snapshot for site ID {site_id} ({url}) to: {file_path}. Hash: {content_hash}")
        return file_path, content_hash
    except IOError as e:
        logger.error(f"Error writing HTML snapshot to {file_path} for site ID {site_id}: {e}")
        return None, None
    except Exception as e:
        logger.error(f"An unexpected error occurred while saving {log_prefix.lower()} snapshot for site ID {site_id}: {e}", exc_info=True)
        return None, None

def save_visual_snapshot(site_id: str, url: str, timestamp: datetime = None, is_baseline: bool = False) -> str | None:
    """
    Saves a visual snapshot (screenshot) of a web page using Playwright.
    If is_baseline is True, saves to a dedicated baseline location with a fixed name.

    Args:
        site_id (str): The unique identifier for the website.
        url (str): The URL to capture.
        timestamp (datetime, optional): Timestamp for the snapshot file name.
                                        Defaults to current UTC time. Used for regular snapshots.
        is_baseline (bool, optional): If True, save as a baseline snapshot.

    Returns:
        str | None: Path to the saved image file if successful, None otherwise.
    """
    logger.info(f"Attempting to capture visual snapshot for site ID {site_id} ({url}) using Playwright")

    parsed_url = urlparse(url)
    domain_name = parsed_url.netloc.replace('.', '_').replace(':', '_')
    site_base_dir = os.path.join(get_snapshot_directory(), domain_name, site_id)

    if is_baseline:
        site_visual_dir = os.path.join(site_base_dir, "baseline")
        # For baseline, we might use a consistent name, but a timestamped intermediate 
        # can prevent issues if the process is interrupted or run multiple times quickly.
        # The final stored path in websites.json should be the generic baseline.png.
        # For simplicity here, we'll use a fixed name directly.
        filename = "baseline.png" 
        log_prefix = "Baseline visual"
    else:
        site_visual_dir = os.path.join(site_base_dir, "visual")
        if timestamp is None: # Should be provided for non-baseline, but fallback
            timestamp = datetime.now(timezone.utc)
        filename = f"{timestamp.strftime('%Y%m%d_%H%M%S_%f')}_utc.png"
        log_prefix = "Visual"

    image_path = os.path.join(site_visual_dir, filename)

    try:
        os.makedirs(site_visual_dir, exist_ok=True)
    except OSError as e:
        logger.error(f"Could not create directory {site_visual_dir} for visual snapshots: {e}")
        return None

    try:
        with sync_playwright() as p:
            browser_type = config.get('playwright_browser_type', 'chromium') # chromium, firefox, webkit
            headless_mode = config.get('playwright_headless_mode', True)
            user_agent = config.get('playwright_user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36')
            render_delay_ms = config.get('playwright_render_delay_ms', 3000) # milliseconds

            browser = None
            if browser_type == 'chromium':
                browser = p.chromium.launch(headless=headless_mode)
            elif browser_type == 'firefox':
                browser = p.firefox.launch(headless=headless_mode)
            elif browser_type == 'webkit':
                browser = p.webkit.launch(headless=headless_mode)
            else:
                logger.error(f"Unsupported browser type '{browser_type}' in config. Using Chromium.")
                browser = p.chromium.launch(headless=headless_mode)
            
            context = browser.new_context(user_agent=user_agent)
            page = context.new_page()
            
            logger.debug(f"Navigating to {url} with Playwright ({browser_type})")
            page.goto(url, wait_until='load', timeout=config.get('playwright_navigation_timeout_ms', 60000))
            
            if render_delay_ms > 0:
                logger.debug(f"Waiting for {render_delay_ms}ms for page rendering.")
                time.sleep(render_delay_ms / 1000)

            page.screenshot(path=image_path, full_page=True)
            logger.info(f"Successfully saved {log_prefix.lower()} snapshot for site ID {site_id} to: {image_path}")
            
            browser.close()
            return image_path

    except Exception as e:
        logger.error(f"Error capturing {log_prefix.lower()} snapshot for site ID {site_id} ({url}) with Playwright: {e}", exc_info=True)
        return None

if __name__ == '__main__':
    logger.info("----- Snapshot Tool Demo (Playwright) -----")

    snapshot_base_dir = get_snapshot_directory()
    print(f"Using snapshot base directory: {snapshot_base_dir}")

    test_site_id = "test-site-playwright-001"
    test_url = "https://example.com" # A reliable public URL for testing
    sample_html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Sample Page</title>
    </head>
    <body>
        <h1>Hello, Snapshot!</h1>
        <p>This is a test page for Playwright.</p>
    </body>
    </html>
    """

    logger.info(f"\nAttempting to save HTML snapshot for {test_url}")
    html_file_path, html_hash = save_html_snapshot(test_site_id, test_url, sample_html_content)

    if html_file_path and html_hash:
        logger.info(f"HTML snapshot saved successfully: {html_file_path}, Hash: {html_hash}")
        assert os.path.exists(html_file_path), "HTML snapshot file was not created!"
        with open(html_file_path, 'r', encoding='utf-8') as f_check:
            assert f_check.read() == sample_html_content, "HTML content mismatch!"
        print(f"Successfully created and verified HTML snapshot: {html_file_path}")
    else:
        logger.error("Failed to save HTML snapshot.")

    logger.info("\nAttempting to save visual snapshot with Playwright...")
    # Configure these in your config.yaml for real runs, or rely on defaults
    # config['playwright_browser_type'] = 'chromium' 
    # config['playwright_headless_mode'] = True

    visual_snapshot_path = save_visual_snapshot(test_site_id, test_url)
    if visual_snapshot_path:
        logger.info(f"Visual snapshot saved to: {visual_snapshot_path}")
        assert os.path.exists(visual_snapshot_path), "Visual snapshot file was not created!"
        print(f"Successfully created visual snapshot: {visual_snapshot_path}")
    else:
        logger.error("Failed to create visual snapshot with Playwright. Check logs and Playwright setup.")
        
    logger.info("\n--- Testing Baseline Snapshot Save ---")
    baseline_site_id = "test-baseline-site-001"
    baseline_html_path, baseline_html_hash = save_html_snapshot(baseline_site_id, test_url, "<html><body>Baseline HTML</body></html>", is_baseline=True)
    if baseline_html_path:
        logger.info(f"Baseline HTML snapshot saved to: {baseline_html_path}, Hash: {baseline_html_hash}")
        assert "baseline/baseline.html" in baseline_html_path.replace("\\", "/"), "Baseline HTML path incorrect."
        assert os.path.exists(baseline_html_path)
    else:
        logger.error("Failed to save baseline HTML snapshot.")

    baseline_visual_path = save_visual_snapshot(baseline_site_id, test_url, is_baseline=True)
    if baseline_visual_path:
        logger.info(f"Baseline visual snapshot saved to: {baseline_visual_path}")
        assert "baseline/baseline.png" in baseline_visual_path.replace("\\", "/"), "Baseline visual path incorrect."
        assert os.path.exists(baseline_visual_path)
    else:
        logger.error("Failed to save baseline visual snapshot.")
        
    logger.info("----- Snapshot Tool Demo (Playwright) Finished -----") 