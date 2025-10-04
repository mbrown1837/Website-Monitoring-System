import cv2
import numpy as np
import requests
import os
import sqlite3
import json
import shutil
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from PIL import Image
from io import BytesIO
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import multiprocessing

from src.logger_setup import setup_logging
from src.config_loader import get_config
from src.path_utils import get_database_path, get_snapshots_directory, ensure_directory_exists

logger = setup_logging()

class BlurDetector:
    def __init__(self, config_path=None):
        self.logger = logger
        self.config = get_config(config_path=config_path)
        
        # Load blur detection settings from config
        self.threshold = self.config.get('blur_detection_threshold', 100)
        self.blur_percentage_threshold = self.config.get('blur_detection_percentage_threshold', 15)
        self.min_image_size = self.config.get('blur_detection_min_image_size', 100)
        self.resize_dimensions = tuple(self.config.get('blur_detection_resize_dimensions', [1280, 720]))
        self.cleanup_days = self.config.get('blur_detection_cleanup_days', 30)
        
        # Initialize the database table
        self._init_blur_detection_tables()
        
        self.logger.info(f"BlurDetector initialized with threshold: {self.threshold}, resize: {self.resize_dimensions}")
    
    def _get_db_connection(self):
        """Get database connection for storing blur detection results."""
        db_path = get_database_path()
        # Ensure the directory exists (db_path is a string)
        db_dir = os.path.dirname(db_path)
        ensure_directory_exists(db_dir)
        conn = sqlite3.connect(str(db_path), timeout=30)
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.execute("PRAGMA busy_timeout=5000;")
        except Exception:
            pass
        return conn
    
    def _init_blur_detection_tables(self):
        """Initialize database tables for blur detection."""
        conn = self._get_db_connection()
        try:
            cursor = conn.cursor()
            
            # Create blur_detection_results table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS blur_detection_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    crawl_id INTEGER NOT NULL,
                    website_id TEXT NOT NULL,
                    page_url TEXT NOT NULL,
                    image_url TEXT NOT NULL,
                    image_local_path TEXT,
                    laplacian_score REAL,
                    blur_percentage REAL,
                    is_blurry BOOLEAN,
                    image_width INTEGER,
                    image_height INTEGER,
                    file_size INTEGER,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (crawl_id) REFERENCES crawl_results (id)
                )
            ''')
            
            # Create image_registry table for duplicate detection
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS image_registry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    website_id TEXT NOT NULL,
                    image_url TEXT NOT NULL,
                    image_hash TEXT,
                    image_local_path TEXT,
                    first_seen_page TEXT NOT NULL,
                    first_seen_timestamp TEXT NOT NULL,
                    last_seen_timestamp TEXT NOT NULL,
                    usage_count INTEGER DEFAULT 1,
                    file_size INTEGER,
                    image_width INTEGER,
                    image_height INTEGER,
                    UNIQUE(website_id, image_url)
                )
            ''')
            
            # Create indexes for better performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_image_registry_website_url ON image_registry(website_id, image_url)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_image_registry_hash ON image_registry(image_hash)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_image_registry_timestamp ON image_registry(last_seen_timestamp)')
            
            conn.commit()
            self.logger.info("Blur detection database tables initialized successfully.")
        except Exception as e:
            self.logger.error(f"Error initializing blur detection table: {e}", exc_info=True)
        finally:
            conn.close()
    
    def _create_blur_images_directory(self, website_id):
        """Create blur images directory for a specific website."""
        from pathlib import Path
        
        # Get website info to extract domain name
        website = self.website_manager.get_website(website_id) if hasattr(self, 'website_manager') else None
        
        if website and website.get('url'):
            # Extract domain name from URL (same logic as snapshot_tool)
            from urllib.parse import urlparse
            parsed_url = urlparse(website['url'])
            domain_name = parsed_url.netloc.replace('.', '_').replace(':', '_')
            # Convert string path to Path object
            snapshots_dir = Path(get_snapshots_directory())
            blur_dir = snapshots_dir / domain_name / website_id / 'blur_images'
        else:
            # Fallback to old method if website not found
            snapshots_dir = Path(get_snapshots_directory())
            blur_dir = snapshots_dir / self._sanitize_site_id(website_id) / 'blur_images'
        
        ensure_directory_exists(str(blur_dir))
        return str(blur_dir)
    
    def _sanitize_site_id(self, site_id):
        """Sanitize site ID for use in file paths."""
        # Convert URL to safe directory name if needed
        if site_id.startswith(('http://', 'https://')):
            parsed = urlparse(site_id)
            return f"{parsed.netloc.replace('.', '_').replace(':', '_')}"
        return str(site_id).replace('/', '_').replace('\\', '_').replace(':', '_')
    
    def cleanup_blur_data_for_website(self, website_id):
        """Clean up old blur detection data for a specific website."""
        try:
            # Clean up database records
            conn = self._get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM blur_detection_results WHERE website_id = ?', (website_id,))
                deleted_count = cursor.rowcount
                conn.commit()
                self.logger.info(f"Deleted {deleted_count} old blur detection records for website {website_id}")
            except Exception as e:
                self.logger.error(f"Error cleaning up blur detection database records for website {website_id}: {e}")
                conn.rollback()
            finally:
                conn.close()
            
            # Clean up image files
            blur_dir = self._create_blur_images_directory(website_id)
            if os.path.exists(blur_dir):
                try:
                    shutil.rmtree(blur_dir)
                    self.logger.info(f"Removed blur images directory: {blur_dir}")
                    # Recreate the directory for new images
                    os.makedirs(blur_dir, exist_ok=True)
                except Exception as e:
                    self.logger.error(f"Error removing blur images directory {blur_dir}: {e}")
            
        except Exception as e:
            self.logger.error(f"Error during blur data cleanup for website {website_id}: {e}", exc_info=True)

    def _normalize_image_url(self, image_url, page_url):
        """Normalize and validate image URL with proper handling of edge cases."""
        try:
            # Skip data URLs (base64 encoded images, tracking pixels, etc.)
            if image_url.startswith('data:'):
                self.logger.debug(f"Skipping data URL: {image_url[:50]}...")
                return None
            
            # Skip obvious non-image URLs (tracking pixels, analytics, etc.)
            if any(domain in image_url.lower() for domain in [
                'facebook.com/tr', 'google-analytics.com', 'googletagmanager.com',
                'doubleclick.net', 'googlesyndication.com', 'googleadservices.com',
                'pixel', 'tracking', 'analytics', 'beacon', 'collect'
            ]):
                self.logger.debug(f"Skipping tracking/analytics URL: {image_url}")
                return None
            
            # Skip SVG images (vector graphics don't need blur detection)
            if image_url.lower().endswith('.svg') or 'image/svg' in image_url.lower():
                self.logger.debug(f"Skipping SVG image: {image_url}")
                return None
            
            # Note: WebP images are now supported for blur detection
            # OpenCV and PIL both handle WebP images perfectly
            
            # Handle protocol-relative URLs (//example.com/image.jpg)
            if image_url.startswith('//'):
                image_url = 'https:' + image_url
            
            # Make absolute URL if relative
            if not image_url.startswith(('http://', 'https://')):
                image_url = urljoin(page_url, image_url)
            
            # Normalize URL to HTTPS for better compatibility
            if image_url.startswith('http://'):
                image_url = image_url.replace('http://', 'https://', 1)
            
            # Validate URL structure
            try:
                parsed = urlparse(image_url)
                if not parsed.scheme or not parsed.netloc:
                    self.logger.warning(f"Invalid URL structure: {image_url}")
                    return None
            except Exception as e:
                self.logger.warning(f"Failed to parse URL {image_url}: {e}")
                return None
            
            return image_url
            
        except Exception as e:
            self.logger.error(f"Error normalizing URL {image_url}: {e}")
            return None

    def _download_image(self, image_url, page_url, max_retries=3):
        """Download an image from a URL with retry mechanism and return the image data."""
        try:
            # Normalize the image URL first
            normalized_url = self._normalize_image_url(image_url, page_url)
            if not normalized_url:
                return None
            
            image_url = normalized_url
            
            # WebP images are now supported for blur detection
            
            # Download the image with retry mechanism and enhanced headers to avoid 403 errors
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'Accept': 'image/webp,image/png,image/jpeg,image/gif,image/*,*/*;q=0.8',  # Include WebP support
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache',
                'Referer': page_url,  # Add referer to appear as if coming from the page
                'Sec-Fetch-Dest': 'image',
                'Sec-Fetch-Mode': 'no-cors',
                'Sec-Fetch-Site': 'same-origin',
                'DNT': '1',
                'Sec-GPC': '1'
            }
            
            # Get timeout from config or use default (increased for slow connections)
            timeout = self.config.get('blur_detection_timeout', 60)  # Increased from 30 to 60
            
            for attempt in range(max_retries):
                try:
                    # Create session for connection pooling
                    with requests.Session() as session:
                        session.headers.update(headers)
                        
                        # Configure session for better performance and reliability
                        adapter = requests.adapters.HTTPAdapter(
                            pool_connections=5,  # Reduced from 10
                            pool_maxsize=10,     # Reduced from 20
                            max_retries=0        # We handle retries manually
                        )
                        session.mount('https://', adapter)
                        session.mount('http://', adapter)
                        
                        # Add delay between retries to avoid overwhelming servers
                        if attempt > 0:
                            time.sleep(2)  # 2 second delay between retries
                        
                        response = session.get(
                            image_url, 
                            timeout=(timeout, timeout),  # Connect and read timeout
                            stream=True,
                            allow_redirects=True
                        )
                        response.raise_for_status()
                        
                        # Get final URL after redirects
                        final_url = response.url
                        if final_url != image_url:
                            self.logger.debug(f"Image URL redirected from {image_url} to {final_url}")
                        
                        # Check if it's actually an image
                        content_type = response.headers.get('content-type', '').lower()
                        if not content_type.startswith('image/'):
                            self.logger.warning(f"URL {final_url} does not appear to be an image (content-type: {content_type})")
                            return None
                        
                        # Read the image data
                        image_data = response.content
                        
                        # Validate minimum size
                        if len(image_data) < 1024:  # Less than 1KB - probably not a real image
                            self.logger.debug(f"Image too small ({len(image_data)} bytes), skipping: {final_url}")
                            return None
                        
                        # Validate maximum size (prevent memory issues)
                        max_size = 10 * 1024 * 1024  # 10MB limit
                        if len(image_data) > max_size:
                            self.logger.warning(f"Image too large ({len(image_data)} bytes), skipping: {final_url}")
                            return None
                        
                        # Validate image format by checking file signature
                        if not self._is_valid_image_data(image_data):
                            self.logger.warning(f"Invalid image format detected for {final_url}")
                            return None
                        
                        self.logger.debug(f"Successfully downloaded image from {image_url} ({len(image_data)} bytes)")
                        return image_data
                        
                except requests.exceptions.Timeout:
                    if attempt < max_retries - 1:
                        wait_time = (2 ** attempt) * 2  # Exponential backoff: 2s, 4s, 8s
                        self.logger.warning(f"Timeout downloading {image_url}, attempt {attempt + 1}/{max_retries}, retrying in {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        self.logger.error(f"Failed to download {image_url} after {max_retries} attempts due to timeout")
                        return None
                        
                except requests.exceptions.ConnectionError as e:
                    if attempt < max_retries - 1:
                        wait_time = (2 ** attempt) * 2  # Exponential backoff: 2s, 4s, 8s
                        self.logger.warning(f"Connection error downloading {image_url}, attempt {attempt + 1}/{max_retries}, retrying in {wait_time}s... Error: {e}")
                        time.sleep(wait_time)
                    else:
                        self.logger.error(f"Failed to download {image_url} after {max_retries} attempts due to connection error: {e}")
                        return None
                        
                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 403:
                        # Try different strategies for 403 errors
                        if attempt == 0:
                            # First attempt: try with different headers
                            self.logger.warning(f"Access forbidden (403) for image {image_url} - trying alternative headers...")
                            # Try with minimal headers
                            minimal_headers = {
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                                'Accept': 'image/*,*/*;q=0.8',
                                'Referer': page_url
                            }
                            try:
                                response = session.get(
                                    image_url, 
                                    timeout=(timeout, timeout),
                                    stream=True,
                                    allow_redirects=True,
                                    headers=minimal_headers
                                )
                                response.raise_for_status()
                                # If successful, process the response
                                content_type = response.headers.get('content-type', '').lower()
                                if not content_type.startswith('image/'):
                                    self.logger.warning(f"URL {image_url} does not appear to be an image (content-type: {content_type})")
                                    return None
                                
                                image_data = response.content
                                if len(image_data) < 1024:
                                    self.logger.debug(f"Image too small ({len(image_data)} bytes), skipping: {image_url}")
                                    return None
                                
                                if len(image_data) > 10 * 1024 * 1024:
                                    self.logger.warning(f"Image too large ({len(image_data)} bytes), skipping: {image_url}")
                                    return None
                                
                                if not self._is_valid_image_data(image_data):
                                    self.logger.warning(f"Invalid image format detected for {image_url}")
                                    return None
                                
                                self.logger.debug(f"Successfully downloaded image from {image_url} with alternative headers ({len(image_data)} bytes)")
                                return image_data
                            except Exception:
                                # If alternative headers also fail, skip this image
                                self.logger.warning(f"Access forbidden (403) for image {image_url} even with alternative headers - skipping")
                                return None
                        else:
                            self.logger.warning(f"Access forbidden (403) for image {image_url} - skipping (no retry)")
                            return None
                    elif e.response.status_code == 404:
                        self.logger.warning(f"Image not found (404) for {image_url} - skipping (no retry)")
                        return None
                    elif e.response.status_code in [429, 503, 504]:
                        # Server overloaded, retry with backoff
                        if attempt < max_retries - 1:
                            wait_time = (2 ** attempt) * 2
                            self.logger.warning(f"Server overloaded ({e.response.status_code}) for {image_url}, attempt {attempt + 1}/{max_retries}, retrying in {wait_time}s...")
                            time.sleep(wait_time)
                        else:
                            self.logger.error(f"Failed to download {image_url} after {max_retries} attempts due to server overload ({e.response.status_code})")
                            return None
                    else:
                        self.logger.warning(f"HTTP error {e.response.status_code} for {image_url} - skipping")
                        return None
                        
                except requests.exceptions.RequestException as e:
                    if attempt < max_retries - 1:
                        wait_time = (2 ** attempt) * 2
                        self.logger.warning(f"Request error downloading {image_url}, attempt {attempt + 1}/{max_retries}, retrying in {wait_time}s... Error: {e}")
                        time.sleep(wait_time)
                    else:
                        self.logger.error(f"Failed to download {image_url} after {max_retries} attempts due to request error: {e}")
                        return None
                        
                except Exception as e:
                    self.logger.error(f"Unexpected error downloading image {image_url}: {e}")
                    return None
                    
            # If we get here, all retries failed
            self.logger.error(f"Failed to download {image_url} after {max_retries} attempts")
            return None
            
        except Exception as e:
            self.logger.error(f"Error in _download_image for {image_url}: {e}")
            return None

    def _is_valid_image_data(self, image_data):
        """Validate image data by checking file signatures."""
        if not image_data or len(image_data) < 4:
            return False
        
        # Check for common image file signatures
        signatures = {
            b'\xff\xd8\xff': 'JPEG',
            b'\x89PNG\r\n\x1a\n': 'PNG',
            b'GIF87a': 'GIF',
            b'GIF89a': 'GIF',
            b'RIFF': 'WEBP',  # WebP starts with RIFF
            b'BM': 'BMP',
            b'II*\x00': 'TIFF (little-endian)',
            b'MM\x00*': 'TIFF (big-endian)'
        }
        
        for signature, format_name in signatures.items():
            if image_data.startswith(signature):
                return True
        
        # If no signature matches, it might still be valid (some servers don't send proper headers)
        # Check if the data can be decoded as an image
        try:
            from PIL import Image
            from io import BytesIO
            img = Image.open(BytesIO(image_data))
            img.verify()  # This will raise an exception if the image is corrupted
            return True
        except Exception:
            return False

    def _download_and_save_image(self, args):
        """Helper function for parallel image downloading and saving."""
        i, image_data, page_url, blur_dir = args
        
        try:
            # Handle both string URLs and dict objects from crawler
            if isinstance(image_data, dict):
                image_url = image_data.get('src') or image_data.get('url')
            else:
                image_url = str(image_data)
            
            if not image_url:
                return None
            
            # Normalize the image URL
            normalized_url = self._normalize_image_url(image_url, page_url)
            if not normalized_url:
                return None
            
            image_url = normalized_url
            
            # Generate local filename
            parsed_url = urlparse(image_url)
            filename = f"page_{i+1}_{os.path.basename(parsed_url.path) or 'image'}"
            if not filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')):
                filename += '.jpg'  # Default extension
            
            local_path = os.path.join(blur_dir, filename)
            
            # Download image
            image_data = self._download_image(image_url, page_url)
            if image_data:
                # Save image data to file
                try:
                    with open(local_path, 'wb') as f:
                        f.write(image_data)
                    return (local_path, image_url, True)
                except Exception as e:
                    self.logger.error(f"Error saving image data to {local_path}: {e}")
                    return (local_path, image_url, False)
            else:
                return (local_path, image_url, False)
                
        except Exception as e:
            self.logger.error(f"Error downloading image {i+1} from {page_url}: {e}", exc_info=True)
            return None

    def _analyze_single_image(self, image_path, image_url):
        """Analyze a single image for blur using Variance of Laplacian method."""
        try:
            # Load image
            img = cv2.imread(image_path)
            if img is None:
                self.logger.warning(f"Could not load image: {image_path}")
                return None
            
            # Get original dimensions
            original_height, original_width = img.shape[:2]
            file_size = os.path.getsize(image_path)
            
            # Skip very small images to avoid false positives
            if original_width < self.min_image_size or original_height < self.min_image_size:
                self.logger.debug(f"Skipping small image {image_url}: {original_width}x{original_height}")
                return {
                    "image_url": image_url,
                    "image_local_path": image_path,
                    "is_blurry": False,
                    "laplacian_score": None,
                    "blur_percentage": None,
                    "image_width": original_width,
                    "image_height": original_height,
                    "file_size": file_size,
                    "skipped": True,
                    "skip_reason": "Image too small"
                }
            
            # Resize image preserving aspect ratio
            img_resized = self._resize_image_preserve_aspect(img, self.resize_dimensions)
            
            # Convert to grayscale
            gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)
            
            # Method 1: Laplacian Variance
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            # Method 2: Spatial Blur Detection (simplified version)
            blur_percentage = self._calculate_blur_percentage(gray)
            
            # Combined decision logic
            is_blurry = laplacian_var < self.threshold or blur_percentage > self.blur_percentage_threshold
            
            result = {
                "image_url": image_url,
                "image_local_path": image_path,
                "is_blurry": is_blurry,
                "laplacian_score": round(laplacian_var, 2),
                "blur_percentage": round(blur_percentage, 1),
                "image_width": original_width,
                "image_height": original_height,
                "file_size": file_size,
                "threshold": self.threshold,
                "skipped": False
            }
            
            self.logger.debug(f"Analyzed {image_url}: Laplacian={laplacian_var:.2f}, Blur%={blur_percentage:.1f}, Blurry={is_blurry}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error analyzing image {image_path}: {e}", exc_info=True)
            return None

    def _analyze_image_parallel(self, args):
        """Helper function for parallel image analysis."""
        local_path, image_url = args
        
        try:
            if os.path.exists(local_path):
                return self._analyze_single_image(local_path, image_url)
            else:
                return None
        except Exception as e:
            self.logger.error(f"Error analyzing image {local_path}: {e}", exc_info=True)
            return None
    
    def _resize_image_preserve_aspect(self, img, target_dimensions):
        """Resize image to target dimensions while preserving aspect ratio."""
        height, width = img.shape[:2]
        target_width, target_height = target_dimensions
        
        # Calculate scaling factor
        scale = min(target_width / width, target_height / height)
        
        # Calculate new dimensions
        new_width = int(width * scale)
        new_height = int(height * scale)
        
        # Resize image
        resized = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)
        
        return resized
    
    def _calculate_blur_percentage(self, gray_image):
        """Calculate blur percentage using edge detection method."""
        try:
            # Apply Canny edge detection
            edges = cv2.Canny(gray_image, 50, 150)
            
            # Calculate the percentage of edge pixels
            total_pixels = gray_image.shape[0] * gray_image.shape[1]
            edge_pixels = cv2.countNonZero(edges)
            edge_percentage = (edge_pixels / total_pixels) * 100
            
            # Higher edge percentage means less blur
            # Convert to blur percentage (inverse relationship)
            blur_percentage = max(0, 100 - (edge_percentage * 10))  # Rough conversion
            
            return blur_percentage
            
        except Exception as e:
            self.logger.error(f"Error calculating blur percentage: {e}")
            return 0

    def _check_image_registry(self, website_id, image_url):
        """Check if an image already exists in the registry."""
        conn = self._get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT image_local_path, file_size, image_width, image_height, usage_count 
                FROM image_registry 
                WHERE website_id = ? AND image_url = ?
            ''', (website_id, image_url))
            
            result = cursor.fetchone()
            if result:
                return {
                    'exists': True,
                    'image_local_path': result[0],
                    'file_size': result[1],
                    'image_width': result[2],
                    'image_height': result[3],
                    'usage_count': result[4]
                }
            return {'exists': False}
            
        except Exception as e:
            self.logger.error(f"Error checking image registry: {e}")
            return {'exists': False}
        finally:
            conn.close()

    def _add_image_to_registry(self, website_id, image_url, image_local_path, page_url, file_size, image_width, image_height):
        """Add a new image to the registry or update existing entry."""
        conn = self._get_db_connection()
        try:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            
            # Check if image already exists
            cursor.execute('''
                SELECT id, usage_count FROM image_registry 
                WHERE website_id = ? AND image_url = ?
            ''', (website_id, image_url))
            
            existing = cursor.fetchone()
            
            if existing:
                # Update existing entry
                cursor.execute('''
                    UPDATE image_registry 
                    SET last_seen_timestamp = ?, usage_count = usage_count + 1
                    WHERE id = ?
                ''', (now, existing[0]))
                self.logger.debug(f"Updated image registry entry for {image_url} (usage count: {existing[1] + 1})")
            else:
                # Add new entry
                cursor.execute('''
                    INSERT INTO image_registry 
                    (website_id, image_url, image_local_path, first_seen_page, first_seen_timestamp, 
                     last_seen_timestamp, file_size, image_width, image_height)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (website_id, image_url, image_local_path, page_url, now, now, file_size, image_width, image_height))
                self.logger.debug(f"Added new image to registry: {image_url}")
            
            conn.commit()
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating image registry: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def _deduplicate_images(self, website_id, all_images_data):
        """Remove duplicate images from the dataset based on URL."""
        if not all_images_data:
            return []
        
        # Track unique images by URL
        unique_images = {}
        duplicates_removed = 0
        
        for img_data in all_images_data:
            image_url = img_data['image_url']
            
            if image_url not in unique_images:
                # First time seeing this image
                unique_images[image_url] = img_data
            else:
                # Duplicate image found
                duplicates_removed += 1
                # Update the existing entry to include all page references
                existing = unique_images[image_url]
                if 'page_url' in existing and 'page_url' in img_data:
                    if 'additional_pages' not in existing:
                        existing['additional_pages'] = []
                    existing['additional_pages'].append(img_data['page_url'])
        
        deduplicated_data = list(unique_images.values())
        
        self.logger.info(f"Image deduplication: {len(all_images_data)} total images, {len(deduplicated_data)} unique images, {duplicates_removed} duplicates removed")
        
        return deduplicated_data

    def analyze_website_images(self, website_id, all_images_data, crawl_id=None):
        """Analyze all images from all pages of a website in a single batch operation with deduplication."""
        if not all_images_data:
            self.logger.debug(f"No images found for website {website_id}")
            return []
        
        # Initialize results at the beginning to avoid UnboundLocalError
        results = []
        
        # Step 0: Deduplicate images to avoid processing the same image multiple times
        try:
            original_count = len(all_images_data)
            all_images_data = self._deduplicate_images(website_id, all_images_data)
            deduplicated_count = len(all_images_data)
            
            if original_count != deduplicated_count:
                self.logger.info(f"Image deduplication: {original_count} -> {deduplicated_count} images ({original_count - deduplicated_count} duplicates removed)")
        except Exception as e:
            self.logger.warning(f"Error during image deduplication: {e}")
        
        try:
            # Single cleanup operation for the entire website
            self.cleanup_blur_data_for_website(website_id)
            
            # Create blur images directory
            blur_dir = self._create_blur_images_directory(website_id)
            
            processed_count = 0
            max_workers = 2  # Reduced from 5 to avoid overwhelming servers
            
            # Group images by page for better logging
            pages_with_images = {}
            for img_data in all_images_data:
                page_url = img_data['page_url']
                if page_url not in pages_with_images:
                    pages_with_images[page_url] = 0
                pages_with_images[page_url] += 1
            
            total_pages = len(pages_with_images)
            total_images = len(all_images_data)
            
            self.logger.info(f"Starting parallel blur analysis for {total_images} unique images from {total_pages} pages of website {website_id} using {max_workers} workers")
            
            # Process all images (cache system removed for always getting latest data)
            images_to_process = all_images_data
            self.logger.info(f"Processing all {len(images_to_process)} images (cache system disabled for latest data)")
            
            # Step 2: Process all images
            if images_to_process:
                # Parallel downloading and saving of new images
                download_args = []
                for i, img_data in enumerate(images_to_process):
                    page_url = img_data['page_url']
                    image_url = img_data['image_url']
                    
                    # Generate page-specific index for filename
                    page_index = list(pages_with_images.keys()).index(page_url) + 1
                    
                    download_args.append((i, image_url, page_url, blur_dir, page_index))
            
            downloaded_images = []
            
            with ThreadPoolExecutor(max_workers=max_workers) as download_executor:
                download_results = download_executor.map(self._download_and_save_image_batch, download_args)
                
                for i, result in enumerate(download_results):
                    if result and result[3]:  # If download was successful
                        downloaded_images.append((result[0], result[1], result[2]))  # (local_path, image_url, page_url)
                    elif result and not result[3]:  # If download failed
                        self.logger.warning(f"Failed to download image: {result[1]}")
            
                    # Add small delay every few downloads to be respectful to servers
                    if (i + 1) % 3 == 0:
                        time.sleep(0.5)  # 0.5 second delay every 3 downloads
                
                self.logger.info(f"Downloaded {len(downloaded_images)} out of {len(images_to_process)} new images successfully")
                
                # Step 3: Parallel analysis of downloaded images
            if downloaded_images:
                with ProcessPoolExecutor(max_workers=min(max_workers, multiprocessing.cpu_count())) as analysis_executor:
                    analysis_results = analysis_executor.map(self._analyze_image_parallel_batch, downloaded_images)
                    
                    for (local_path, image_url, page_url), analysis_result in zip(downloaded_images, analysis_results):
                        if analysis_result:
                            # Convert absolute path to relative path for web serving
                            relative_path = os.path.relpath(local_path, 'data')
                            analysis_result['image_local_path'] = relative_path
                            analysis_result['page_url'] = page_url
                            analysis_result['website_id'] = website_id
                            analysis_result['crawl_id'] = crawl_id
                            analysis_result['timestamp'] = datetime.now(timezone.utc).isoformat()
                            
                            # Add to image registry
                            if 'file_size' in analysis_result and 'image_width' in analysis_result and 'image_height' in analysis_result:
                                self._add_image_to_registry(
                                    website_id, image_url, relative_path, page_url,
                                    analysis_result['file_size'], analysis_result['image_width'], analysis_result['image_height']
                                )
                            
                            results.append(analysis_result)
                            processed_count += 1
                        else:
                            # Clean up failed analysis
                            if os.path.exists(local_path):
                                os.remove(local_path)
            
            # Log detailed results by page
            for page_url, expected_count in pages_with_images.items():
                actual_count = len([r for r in results if r.get('page_url') == page_url])
                self.logger.debug(f"Processed {actual_count}/{expected_count} images from {page_url}")
            
            self.logger.info(f"Completed parallel blur analysis: {processed_count} images processed, total results: {len(results)}")
        
            # Save all results to database if crawl_id is provided
            if crawl_id and results:
                self._save_results_to_db(crawl_id, results)
            
            return results
                
        except Exception as e:
            self.logger.error(f"Error in parallel blur analysis for website {website_id}: {e}")
            # Return partial results if any were processed
            if results:
                self.logger.info(f"Returning {len(results)} partial results despite error")
                return results
            return []
    
    def _download_and_save_image_batch(self, args):
        """Helper function for parallel batch image downloading and saving."""
        i, image_url, page_url, blur_dir, page_index = args
        
        try:
            # Generate local filename with page information
            parsed_url = urlparse(image_url)
            filename = f"page_{page_index}_{os.path.basename(parsed_url.path) or 'image'}"
            if not filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')):
                filename += '.jpg'  # Default extension
            
            local_path = os.path.join(blur_dir, filename)
            
            # Download image
            image_data = self._download_image(image_url, page_url)
            if image_data:
                # Save image data to file
                try:
                    with open(local_path, 'wb') as f:
                        f.write(image_data)
                    return (local_path, image_url, page_url, True)
                except Exception as e:
                    self.logger.error(f"Error saving image data to {local_path}: {e}")
                    return (local_path, image_url, page_url, False)
            else:
                return (local_path, image_url, page_url, False)
                
        except Exception as e:
            self.logger.error(f"Error downloading image {i+1} from {page_url}: {e}", exc_info=True)
            return None
    
    def _analyze_image_parallel_batch(self, args):
        """Helper function for parallel batch image analysis."""
        local_path, image_url, page_url = args
        
        try:
            if os.path.exists(local_path):
                return self._analyze_single_image(local_path, image_url)
            else:
                return None
        except Exception as e:
            self.logger.error(f"Error analyzing image {local_path}: {e}", exc_info=True)
            return None

    def analyze_page_images(self, website_id, page_url, images_list, crawl_id=None):
        """Analyze all images from a page for blur detection using multiprocessing."""
        if not images_list:
            self.logger.debug(f"No images found for page: {page_url}")
            return []
        
        try:
            # Clean up old blur data first
            self.cleanup_blur_data_for_website(website_id)
            
            # Create blur images directory
            blur_dir = self._create_blur_images_directory(website_id)
            
            results = []
            processed_count = 0
            max_workers = 5  # As requested by user
            
            self.logger.info(f"Starting parallel blur analysis for {len(images_list)} internal images from {page_url} using {max_workers} workers")
            
            # Step 1: Parallel downloading and saving
            download_args = [(i, img_data, page_url, blur_dir) for i, img_data in enumerate(images_list)]
            downloaded_images = []
            
            with ThreadPoolExecutor(max_workers=max_workers) as download_executor:
                download_results = download_executor.map(self._download_and_save_image, download_args)
                
                for result in download_results:
                    if result and result[2]:  # If download was successful
                        downloaded_images.append((result[0], result[1]))  # (local_path, image_url)
                    elif result and not result[2]:  # If download failed
                        self.logger.warning(f"Failed to download image: {result[1]}")
            
            self.logger.info(f"Downloaded {len(downloaded_images)} out of {len(images_list)} images successfully")
            
            # Step 2: Parallel analysis of downloaded images
            if downloaded_images:
                with ProcessPoolExecutor(max_workers=min(max_workers, multiprocessing.cpu_count())) as analysis_executor:
                    analysis_results = analysis_executor.map(self._analyze_image_parallel, downloaded_images)
                    
                    for (local_path, image_url), analysis_result in zip(downloaded_images, analysis_results):
                        if analysis_result:
                            # Convert absolute path to relative path for web serving
                            # Store path relative to data/ directory for web access
                            relative_path = os.path.relpath(local_path, 'data')
                            analysis_result['image_local_path'] = relative_path
                            analysis_result['page_url'] = page_url
                            analysis_result['website_id'] = website_id
                            analysis_result['crawl_id'] = crawl_id
                            analysis_result['timestamp'] = datetime.now(timezone.utc).isoformat()
                            
                            results.append(analysis_result)
                            processed_count += 1
                        else:
                            # Clean up failed analysis
                            if os.path.exists(local_path):
                                os.remove(local_path)
            
            self.logger.info(f"Completed parallel blur analysis: {processed_count}/{len(images_list)} images processed from {page_url}")
            
            # Save results to database if crawl_id is provided
            if crawl_id and results:
                self._save_results_to_db(crawl_id, results)
            
            return results
                
        except Exception as e:
            self.logger.error(f"Error during blur detection for page {page_url}: {e}", exc_info=True)
            # Return partial results if any were processed
            if results:
                self.logger.info(f"Returning {len(results)} partial results despite error")
                return results
            else:
                self.logger.error(f"No blur detection results available for page {page_url} due to error")
                return []
    
    def _save_results_to_db(self, crawl_id, results):
        """Save blur detection results to database."""
        conn = self._get_db_connection()
        try:
            cursor = conn.cursor()
            
            for result in results:
                cursor.execute('''
                    INSERT INTO blur_detection_results 
                    (crawl_id, website_id, page_url, image_url, image_local_path, 
                     laplacian_score, blur_percentage, is_blurry, image_width, 
                     image_height, file_size, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    crawl_id,
                    result['website_id'],
                    result['page_url'],
                    result['image_url'],
                    result['image_local_path'],
                    result.get('laplacian_score'),
                    result.get('blur_percentage'),
                    result['is_blurry'],
                    result['image_width'],
                    result['image_height'],
                    result['file_size'],
                    result['timestamp']
                ))
            
            conn.commit()
            self.logger.info(f"Saved {len(results)} blur detection results to database for crawl_id: {crawl_id}")
            
        except Exception as e:
            self.logger.error(f"Error saving blur detection results to database: {e}", exc_info=True)
            conn.rollback()
        finally:
            conn.close()
    
    def get_blur_results_for_crawl(self, crawl_id):
        """Get blur detection results for a specific crawl."""
        conn = self._get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM blur_detection_results 
                WHERE crawl_id = ? 
                ORDER BY page_url, image_url
            ''', (crawl_id,))
            
            columns = [description[0] for description in cursor.description]
            results = []
            
            for row in cursor.fetchall():
                result = dict(zip(columns, row))
                results.append(result)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error getting blur results for crawl {crawl_id}: {e}", exc_info=True)
            return []
        finally:
            conn.close()
    
    def get_blur_stats_for_website(self, website_id):
        """Get blur detection statistics for a website."""
        conn = self._get_db_connection()
        try:
            cursor = conn.cursor()
            
            # Get latest crawl results
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_images,
                    SUM(CASE WHEN is_blurry = 1 THEN 1 ELSE 0 END) as blurry_images,
                    AVG(laplacian_score) as avg_laplacian_score,
                    AVG(blur_percentage) as avg_blur_percentage
                FROM blur_detection_results 
                WHERE website_id = ? 
                AND crawl_id = (
                    SELECT MAX(crawl_id) FROM blur_detection_results WHERE website_id = ?
                )
            ''', (website_id, website_id))
            
            row = cursor.fetchone()
            if row:
                return {
                    'total_images': row[0] or 0,
                    'blurry_images': row[1] or 0,
                    'avg_laplacian_score': round(row[2] or 0, 2),
                    'avg_blur_percentage': round(row[3] or 0, 1)
                }
            
            return {
                'total_images': 0,
                'blurry_images': 0,
                'avg_laplacian_score': 0,
                'avg_blur_percentage': 0
            }
            
        except sqlite3.OperationalError as e:
            if "no such table" in str(e).lower():
                self.logger.warning(f"Blur detection table not found for website {website_id}. Initializing table...")
                self._init_blur_detection_table()
                # Return empty stats for now
                return {
                    'total_images': 0,
                    'blurry_images': 0,
                    'avg_laplacian_score': 0,
                    'avg_blur_percentage': 0
                }
            else:
                raise
        except Exception as e:
            self.logger.error(f"Error getting blur stats for website {website_id}: {e}", exc_info=True)
            return {
                'total_images': 0,
                'blurry_images': 0,
                'avg_laplacian_score': 0,
                'avg_blur_percentage': 0
            }
        finally:
            conn.close()

    def cleanup_old_images(self, days=None):
        """Clean up old blur detection images based on age."""
        cleanup_days = days or self.cleanup_days
        
        # This would implement age-based cleanup logic
        # For now, just log the intention
        self.logger.info(f"Blur image cleanup scheduled for images older than {cleanup_days} days")
        # TODO: Implement actual age-based cleanup logic if needed 