import cv2
import numpy as np
import requests
import time
from io import BytesIO
from PIL import Image
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin

def normalize_image_url(image_url):
    """Normalize and validate image URL with proper handling of edge cases."""
    try:
        # Skip data URLs (base64 encoded images, tracking pixels, etc.)
        if image_url.startswith('data:'):
            print(f"Skipping data URL: {image_url[:50]}...")
            return None
        
        # Skip obvious non-image URLs (tracking pixels, analytics, etc.)
        if any(domain in image_url.lower() for domain in [
            'facebook.com/tr', 'google-analytics.com', 'googletagmanager.com',
            'doubleclick.net', 'googlesyndication.com', 'googleadservices.com',
            'pixel', 'tracking', 'analytics', 'beacon', 'collect'
        ]):
            print(f"Skipping tracking/analytics URL: {image_url}")
            return None
        
        # Handle protocol-relative URLs (//example.com/image.jpg)
        if image_url.startswith('//'):
            image_url = 'https:' + image_url
        
        # Normalize URL to HTTPS for better compatibility
        if image_url.startswith('http://'):
            image_url = image_url.replace('http://', 'https://', 1)
        
        # Validate URL structure
        try:
            from urllib.parse import urlparse
            parsed = urlparse(image_url)
            if not parsed.scheme or not parsed.netloc:
                print(f"Invalid URL structure: {image_url}")
                return None
        except Exception as e:
            print(f"Failed to parse URL {image_url}: {e}")
            return None
        
        return image_url
        
    except Exception as e:
        print(f"Error normalizing URL {image_url}: {e}")
        return None

def download_image_with_retry(image_url, max_retries=3, timeout=30):
    """Download image with retry mechanism."""
    # Normalize the image URL first
    normalized_url = normalize_image_url(image_url)
    if not normalized_url:
        return None
    
    image_url = normalized_url
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    
    for attempt in range(max_retries):
        try:
            with requests.Session() as session:
                session.headers.update(headers)
                session.mount('https://', requests.adapters.HTTPAdapter(
                    pool_connections=10,
                    pool_maxsize=20,
                    max_retries=0
                ))
                
                response = session.get(image_url, timeout=timeout, stream=True)
                response.raise_for_status()
                
                # Check if it's actually an image
                content_type = response.headers.get('content-type', '').lower()
                if not content_type.startswith('image/'):
                    print(f"Warning: URL {image_url} does not appear to be an image (content-type: {content_type})")
                    return None
                
                return response.content
                
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 1
                print(f"Timeout downloading {image_url}, attempt {attempt + 1}/{max_retries}, retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"Failed to download {image_url} after {max_retries} attempts due to timeout")
                return None
                
        except requests.exceptions.ConnectionError as e:
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 1
                print(f"Connection error downloading {image_url}, attempt {attempt + 1}/{max_retries}, retrying in {wait_time}s... Error: {e}")
                time.sleep(wait_time)
            else:
                print(f"Failed to download {image_url} after {max_retries} attempts due to connection error: {e}")
                return None
                
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 1
                print(f"Request error downloading {image_url}, attempt {attempt + 1}/{max_retries}, retrying in {wait_time}s... Error: {e}")
                time.sleep(wait_time)
            else:
                print(f"Failed to download {image_url} after {max_retries} attempts: {e}")
                return None
    
    return None

def analyze_single_image(image_source, threshold=100):
    if image_source.startswith(('http://', 'https://')):
        image_data = download_image_with_retry(image_source)
        if image_data is None:
            return {"error": "Image download failed", "source": image_source}
        
        img = np.array(Image.open(BytesIO(image_data)))
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    else:
        img = cv2.imread(image_source)
    
    if img is None:
        return {"error": "Image loading failed", "source": image_source}
    
    img = cv2.resize(img, (1280, 720))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    from blur_detector import detectBlur
    blur_map = detectBlur(gray, downsampling_factor=4)
    blur_percentage = np.mean(blur_map) * 100
    is_blurry = laplacian_var < threshold or blur_percentage > 15
    
    return {
        "source": image_source,
        "is_blurry": is_blurry,
        "laplacian_score": round(laplacian_var, 2),
        "blur_percentage": round(blur_percentage, 1),
        "threshold": threshold
    }

def analyze_webpage_images(page_url, threshold=100, max_workers=10):
    try:
        response = requests.get(page_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        img_urls = []
        for img in soup.find_all('img'):
            src = img.get('src')
            if src:
                if src.startswith(('http://', 'https://')):
                    img_urls.append(src)
                else:
                    img_urls.append(urljoin(page_url, src))
    except Exception as e:
        return {"error": f"Page processing failed: {str(e)}"}
    
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(analyze_single_image, url, threshold) for url in img_urls]
        for future in futures:
            try:
                results.append(future.result())
            except Exception as e:
                results.append({"error": str(e)})
    return results

if __name__ == "__main__":
    # Replace with your webpage URL
    page_url = "https://thewebturtles.com/"
    results = analyze_webpage_images(page_url)
    for res in results:
        print(res)
