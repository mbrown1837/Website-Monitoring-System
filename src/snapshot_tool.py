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

def handle_sticky_elements(page):
    """Advanced sticky element handling that addresses all common scenarios"""
    
    page.evaluate("""
        () => {
            // Find all sticky and fixed elements
            const allElements = document.querySelectorAll('*');
            const stickyElements = [];
            
            allElements.forEach(el => {
                const style = window.getComputedStyle(el);
                if (style.position === 'sticky' || style.position === 'fixed') {
                    stickyElements.push({
                        element: el,
                        originalPosition: style.position,
                        originalTop: style.top,
                        originalZIndex: style.zIndex
                    });
                }
            });
            
            // Store original values and convert to relative
            window.stickyElementsBackup = stickyElements;
            
            stickyElements.forEach(item => {
                const el = item.element;
                el.style.position = 'relative';
                el.style.top = 'auto';
                el.style.zIndex = 'auto';
            });
            
            // Handle common sticky classes
            const commonStickySelectors = [
                '.sticky', '.fixed', '.navbar-fixed-top', '.navbar-fixed',
                '.header-fixed', '.floating', '.affix', '.sticky-header',
                '.fixed-header', '.navbar-static-top', '.sticky-nav'
            ];
            
            commonStickySelectors.forEach(selector => {
                document.querySelectorAll(selector).forEach(el => {
                    const style = window.getComputedStyle(el);
                    if (style.position === 'sticky' || style.position === 'fixed') {
                        el.style.position = 'relative';
                        el.style.top = 'auto';
                    }
                });
            });
        }
    """)

def advanced_lazy_loading_handler(page):
    """Comprehensive lazy loading handler using latest Playwright techniques"""
    
    logger.info("Starting advanced lazy loading detection...")
    
    # Step 1: Force eager loading for native lazy images
    page.evaluate("""
        () => {
            // Force all lazy images to eager loading
            document.querySelectorAll('img[loading="lazy"]').forEach(img => {
                img.loading = 'eager';
            });
            
            // Handle data-src lazy images
            document.querySelectorAll('img[data-src]:not([src])').forEach(img => {
                if (img.dataset.src) {
                    img.src = img.dataset.src;
                    img.removeAttribute('data-src');
                }
            });
            
            // Handle srcset lazy images
            document.querySelectorAll('img[data-srcset]:not([srcset])').forEach(img => {
                if (img.dataset.srcset) {
                    img.srcset = img.dataset.srcset;
                    img.removeAttribute('data-srcset');
                }
            });
        }
    """)
    
    # Step 2: Smart scrolling to trigger intersection observers
    try:
        page_height = page.evaluate("document.documentElement.scrollHeight")
        viewport_height = page.evaluate("window.innerHeight")
        
        # Calculate scroll positions to ensure all content is triggered
        scroll_positions = []
        current_pos = 0
        step_size = viewport_height // 2  # Overlap scrolling
        
        while current_pos < page_height:
            scroll_positions.append(current_pos)
            current_pos += step_size
            
        # Add final position
        scroll_positions.append(page_height)
        
        # Scroll through all positions
        for pos in scroll_positions:
            page.evaluate(f"window.scrollTo(0, {pos})")
            time.sleep(0.2)  # Brief pause for intersection observers
            
            # Wait for any new network requests
            try:
                page.wait_for_load_state('networkidle', timeout=2000)
            except:
                pass  # Continue if timeout
                
    except Exception as e:
        logger.warning(f"Error during smart scrolling: {e}")
    
    # Step 3: Handle specific lazy loading libraries
    page.evaluate("""
        () => {
            // Trigger common lazy loading libraries
            const lazyElements = document.querySelectorAll(
                '[data-lazy], [data-src], [class*="lazy"], [class*="lazyload"]'
            );
            
            lazyElements.forEach(el => {
                // Trigger intersection observer manually
                const event = new Event('load');
                el.dispatchEvent(event);
                
                // Force visibility if hidden
                if (el.style.display === 'none' && !el.classList.contains('hidden-permanently')) {
                    el.style.display = 'block';
                }
            });
        }
    """)
    
    # Step 4: Wait for visible images to load (optimized)
    try:
        page.wait_for_function("""
            () => {
                const images = Array.from(document.images);
                const visibleImages = images.filter(img => {
                    const rect = img.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0 && 
                           window.getComputedStyle(img).display !== 'none';
                });
                
                // Check if at least 80% of visible images are loaded
                if (visibleImages.length === 0) return true;
                
                const loadedCount = visibleImages.filter(img => 
                    img.complete && (img.naturalWidth > 0 || img.src === '')
                ).length;
                
                return loadedCount >= Math.ceil(visibleImages.length * 0.8);
            }
        """, timeout=5000)  # Reduced from 10000 to 5000 for better performance
        logger.info("Visible images loading completed")
    except Exception as e:
        logger.info(f"Image loading completed with some timeouts: {e}")
    
    # Step 5: Return to top for screenshot
    page.evaluate("window.scrollTo(0, 0)")
    time.sleep(1)  # Allow scroll to complete

def scroll_and_load_lazy_content(page):
    """Legacy function - now calls advanced lazy loading handler"""
    advanced_lazy_loading_handler(page)

def ensure_complete_loading(page):
    """Ensure absolutely everything is loaded before screenshot"""
    
    logger.info("Ensuring complete page loading...")
    
    # Wait for network to be completely idle
    try:
        page.wait_for_load_state('networkidle', timeout=30000)
    except Exception as e:
        logger.info(f"Network idle timeout: {e}")
    
    # Wait for all fonts to load
    try:
        page.wait_for_function("""
            () => document.fonts.ready.then(() => true)
        """, timeout=10000)
        logger.info("All fonts loaded")
    except Exception as e:
        logger.info(f"Font loading timeout: {e}")
    
    # Wait for CSS animations to complete
    try:
        page.wait_for_function("""
            () => {
                const animations = document.getAnimations();
                return animations.every(anim => 
                    anim.playState === 'finished' || 
                    anim.playState === 'idle'
                );
            }
        """, timeout=5000)
        logger.info("All animations completed")
    except Exception as e:
        logger.info(f"Animation completion timeout: {e}")
    
    # Final verification of image loading (optimized for performance)
    try:
        page.wait_for_function("""
            () => {
                const images = Array.from(document.images);
                const videos = Array.from(document.querySelectorAll('video'));
                
                // Only check visible images to reduce processing time
                const visibleImages = images.filter(img => {
                    const rect = img.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0 && 
                           window.getComputedStyle(img).display !== 'none';
                });
                
                // Check if at least 80% of visible images are loaded (more lenient)
                const imagesLoaded = visibleImages.length === 0 || 
                    visibleImages.filter(img => 
                        img.complete && (img.naturalWidth > 0 || img.src === '')
                    ).length >= Math.ceil(visibleImages.length * 0.8);
                
                // Check videos (more lenient - only check if they have src)
                const videosLoaded = videos.length === 0 || 
                    videos.every(video => 
                        video.readyState >= 3 || video.src === '' || !video.src
                    );
                
                return imagesLoaded && videosLoaded;
            }
        """, timeout=5000)  # Reduced from 10000 to 5000 for better performance
        logger.info("Media content verification completed")
    except Exception as e:
        logger.info(f"Media loading verification completed with some timeouts: {e}")
    
    # Give everything a moment to stabilize
    time.sleep(2)

def wait_for_all_content(page):
    """Legacy function - now calls enhanced loading verification"""
    ensure_complete_loading(page)

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
                
                # Enhanced launch arguments for stability
                launch_args = [
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-extensions'
                ]
                
                if browser_type == 'chromium':
                    launch_args.extend([
                        '--use-angle=gl',
                        '--disable-background-timer-throttling',
                        '--disable-renderer-backgrounding'
                    ])

                browser = getattr(p, browser_type).launch(
                    headless=config.get('playwright_headless_mode', True),
                    args=launch_args
                )
                
                context = browser.new_context(
                    user_agent=config.get('playwright_user_agent'),
                    viewport={'width': 1920, 'height': 1080}
                )
                page = context.new_page()
                
                # Navigate with comprehensive waiting
                page.goto(url, 
                    wait_until='domcontentloaded', 
                    timeout=config.get('playwright_navigation_timeout_ms', 30000)
                )
                
                # Initial render delay
                time.sleep(config.get('playwright_render_delay_ms', 2000) / 1000)
                
                # Handle sticky elements FIRST
                handle_sticky_elements(page)
                
                # Advanced lazy loading handling
                advanced_lazy_loading_handler(page)
                
                # Ensure everything is completely loaded
                ensure_complete_loading(page)
                
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