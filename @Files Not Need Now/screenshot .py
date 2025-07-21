from playwright.sync_api import sync_playwright
import time

def scroll_and_load_lazy_content(page):
    """Advanced scrolling to trigger all lazy-loaded content"""
    
    # First, scroll to trigger lazy images specifically
    lazy_images = page.locator('img[loading="lazy"]:visible, img[data-src]:visible').all()
    print(f"Found {len(lazy_images)} lazy images to load")
    
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
        except:
            continue
    
    # Advanced scrolling strategy
    print("Performing advanced scrolling...")
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
            print(f"New content detected! Height: {last_height} -> {new_height}")
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
    except:
        print("Network idle timeout, continuing...")
    
    # Wait for all images to load
    try:
        page.wait_for_function("""
            () => {
                const images = Array.from(document.images);
                return images.every(img => img.complete && img.naturalWidth > 0);
            }
        """, timeout=30000)
        print("All images loaded successfully")
    except:
        print("Some images may not have loaded, continuing...")
    
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

def take_complete_screenshot(url, output_path='complete_screenshot.png'):
    """Take a complete screenshot with all content loaded"""
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})
        
        try:
            print(f"Loading {url}...")
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
            
            # Initial wait for page to stabilize
            time.sleep(3)
            
            # Advanced scrolling to trigger lazy content
            scroll_and_load_lazy_content(page)
            
            # Force load any remaining lazy content
            force_load_lazy_content(page)
            
            # Wait for all content to be fully loaded
            wait_for_all_content(page)
            
            # Scroll back to top for final screenshot
            page.evaluate("window.scrollTo(0, 0)")
            time.sleep(2)
            
            # Take the screenshot
            print("Taking final screenshot...")
            page.screenshot(path=output_path, full_page=True)
            print(f"Screenshot saved as '{output_path}'")
            
        except Exception as e:
            print(f"Error: {e}")
            try:
                page.screenshot(path=f"fallback_{output_path}", full_page=True)
                print(f"Fallback screenshot saved")
            except:
                pass
        finally:
            browser.close()

# Usage
if __name__ == "__main__":
    take_complete_screenshot('https://staging2.alexanderlawnservicebr.com/', 'alexander.png')
