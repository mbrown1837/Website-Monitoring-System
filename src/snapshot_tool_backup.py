import os
import hashlib
from datetime import datetime, timezone
import time
from urllib.parse import urlparse
from src.config_loader import get_config
from src.logger_setup import setup_logging
import re

# Playwright imports
from playwright.sync_api import sync_playwright

logger = setup_logging()
config = get_config()

DEFAULT_SNAPSHOT_DIR = "data/snapshots"

def scroll_and_load_lazy_content(page):
    """Advanced scrolling to trigger all lazy-loaded content"""
    
    # First, scroll to trigger lazy images specifically
    lazy_images = page.locator('img[loading="lazy"]:visible, img[data-src]:visible').all()
    logger.info(f"Found {len(lazy_images)} lazy images to load")
    
    for img in lazy_images:
        try:
            img.scroll_into_view_if_needed()
            # Wait for image to actually load
            img.wait_for(state='visible', timeout=3000)
            # Check if image has natural width (loaded)
            page.wait_for_function(
                'img => img.naturalWidth > 0',
                arg=img,
                timeout=5000
            )
        except Exception as e:
            logger.debug(f"Error loading lazy image: {e}")
            continue
    
    # Advanced scrolling strategy
    logger.info("Performing advanced scrolling...")
    last_height = page.evaluate("document.body.scrollHeight")
    attempts = 0
    max_attempts = 20
    
    while attempts < max_attempts:
        # Scroll down in multiple steps
        for i in range(0, 10):
            page.evaluate(f"window.scrollTo(0, {last_height * (i + 1) / 10})")
            time.sleep(0.3)
        
        # Wait for any new content to load
        time.sleep(2)
        
        # Check if page height increased (new content loaded)
        new_height = page.evaluate("document.body.scrollHeight")
        if new_height > last_height:
            logger.info(f"New content detected! Height: {last_height} -> {new_height}")
            last_height = new_height
            attempts = 0  # Reset attempts when new content is found
        else:
            attempts += 1
        
        # Additional triggers for lazy content
        page.keyboard.press('End')
        time.sleep(0.5)
    
    # Final scroll to ensure everything is triggered
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(3)

def wait_for_all_content(page):
    """Wait for all content to be fully loaded"""
    
    # Wait for network to be idle
    try:
        page.wait_for_load_state('networkidle', timeout=30000)
    except Exception as e:
        logger.info(f"Network idle timeout, continuing: {e}")
    
    # Wait for all images to load
    try:
        page.wait_for_function("""
            () => {
                const images = Array.from(document.images);
                return images.every(img => img.complete && img.naturalWidth > 0);
            }
        """, timeout=30000)
        logger.info("All images loaded successfully")
    except Exception as e:
        logger.info(f"Some images may not have loaded, continuing: {e}")
    
    # Wait for any animations or transitions to complete
    time.sleep(2)

def force_load_lazy_content(page):
    """Force load any remaining lazy content"""
    page.evaluate("""
        // Force load data-src images
        document.querySelectorAll('img[data-src]').forEach(img => {
            if (img.dataset.src) {
                img.src = img.dataset.src;
                img.removeAttribute('data-src');
            }
        });
        
        // Remove lazy loading attributes
        document.querySelectorAll('img[loading="lazy"]').forEach(img => {
            img.loading = 'eager';
        });
        
        // Trigger any intersection observers
        const lazyElements = document.querySelectorAll('[class*="lazy"], [data-lazy]');
        lazyElements.forEach(el => {
            // Create a temporary intersection observer event
            const event = new Event('load');
            el.dispatchEvent(event);
        });
        
        // Force visibility of hidden content sections
        document.querySelectorAll('[style*="display: none"], [style*="visibility: hidden"]').forEach(el => {
            const computedStyle = window.getComputedStyle(el);
            if (computedStyle.display === 'none' && !el.classList.contains('popup')) {
                el.style.display = 'block';
            }
        });
    """)

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

def save_visual_snapshot(site_id: str, url: str, timestamp: datetime = None, is_baseline: bool = False, url_path: str = None) -> str | None:
    """
    Saves a visual snapshot (screenshot) of a web page using Playwright.
    Returns a web-friendly, relative path to the saved image file, including the 'data' directory.
    """
    logger.info(f"Attempting to capture visual snapshot for site ID {site_id} ({url})")

    # Get snapshot format from config, default to 'png' for best quality
    snapshot_format = config.get('snapshot_format', 'png').lower()
    if snapshot_format not in ['png', 'jpeg', 'webp']:
        logger.warning(f"Invalid snapshot_format '{snapshot_format}' in config. Defaulting to 'png'.")
        snapshot_format = 'png'
        
    parsed_url = urlparse(url)
    domain_name = parsed_url.netloc.replace('.', '_').replace(':', '_')
    
    if url_path is None:
        url_path = (parsed_url.path.strip('/') or 'home').replace('/', '_')
        url_path = re.sub(r'\.(html|htm|php|aspx|jsp)$', '', url_path, flags=re.IGNORECASE).lower()

    # This function returns the absolute path to the data/snapshots directory
    # e.g., C:/.../Project/data/snapshots
    snapshots_base_dir_abs = get_snapshot_directory()
    site_base_dir = os.path.join(snapshots_base_dir_abs, domain_name, site_id)
    
    sub_folder = "baseline" if is_baseline else "visual"
    site_visual_dir = os.path.join(site_base_dir, sub_folder)

    if is_baseline:
        filename = f"baseline_{url_path}.{snapshot_format}"
    else:
        ts = timestamp or datetime.now(timezone.utc)
        filename = f"{ts.strftime('%Y%m%d_%H%M%S_%f')}_utc.{snapshot_format}"

    os.makedirs(site_visual_dir, exist_ok=True)
    image_path_abs = os.path.join(site_visual_dir, filename)

    max_retries = config.get('playwright_retries', 3)
    for attempt in range(1, max_retries + 1):
        try:
            with sync_playwright() as p:
                browser_type = config.get('playwright_browser_type', 'chromium')
                
                # Add additional launch arguments for stability
                launch_args = []
                if browser_type == 'chromium':
                    launch_args.append('--use-angle=gl')

                browser = getattr(p, browser_type).launch(
                    headless=config.get('playwright_headless_mode', True),
                    args=launch_args
                )
                
                context = browser.new_context(
                    user_agent=config.get('playwright_user_agent'),
                    viewport={'width': 1920, 'height': 1080}
                )
                page = context.new_page()
                page.goto(url, wait_until='domcontentloaded', timeout=config.get('playwright_navigation_timeout_ms', 30000))
                
                time.sleep(config.get('playwright_render_delay_ms', 2000) / 1000)
                
                scroll_and_load_lazy_content(page)
                wait_for_all_content(page)
                
                page.screenshot(path=image_path_abs, full_page=True)
                browser.close()

                logger.info(f"Successfully saved visual snapshot for site ID {site_id} to: {image_path_abs}")

                # --- THIS IS THE DEFINITIVE FIX ---
                # Construct a relative path that is valid from the project root.
                # It will look like: 'data/snapshots/domain/site_id/folder/file.png'
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                correct_relative_path = os.path.relpath(image_path_abs, project_root)
                
                # Normalize for web (use forward slashes)
                final_path = correct_relative_path.replace("\\", "/")
                
                logger.info(f"Returning final relative snapshot path: {final_path}")
                return final_path

        except Exception as e:
            logger.error(f"Attempt {attempt}/{max_retries} failed for snapshot {url}: {e}", exc_info=True)
            if attempt < max_retries:
                time.sleep(5) 
            else:
                logger.error(f"All {max_retries} attempts failed for visual snapshot of {url}.")
                return None
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
        assert "baseline/baseline" in baseline_visual_path.replace("\\", "/"), "Baseline visual path incorrect."
        assert os.path.exists(baseline_visual_path)
    else:
        logger.error("Failed to save baseline visual snapshot.")
        
    logger.info("----- Snapshot Tool Demo (Playwright) Finished -----") 