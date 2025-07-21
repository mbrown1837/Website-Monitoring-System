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
        self._init_blur_detection_table()
        
        self.logger.info(f"BlurDetector initialized with threshold: {self.threshold}, resize: {self.resize_dimensions}")
    
    def _get_db_connection(self):
        """Get database connection for storing blur detection results."""
        db_path = os.path.join('data', 'website_monitor.db')
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        conn = sqlite3.connect(db_path)
        return conn
    
    def _init_blur_detection_table(self):
        """Initialize the blur detection results table if it doesn't exist."""
        conn = self._get_db_connection()
        try:
            cursor = conn.cursor()
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
            conn.commit()
            self.logger.info("Blur detection database table initialized successfully.")
        except Exception as e:
            self.logger.error(f"Error initializing blur detection table: {e}", exc_info=True)
        finally:
            conn.close()
    
    def _create_blur_images_directory(self, website_id):
        """Create directory structure for storing blur analysis images."""
        # Get website URL to extract domain name (same pattern as snapshot_tool)
        from src.website_manager import WebsiteManager
        website_manager = WebsiteManager()
        website = website_manager.get_website(website_id)
        
        if website and website.get('url'):
            # Extract domain name from URL (same logic as snapshot_tool)
            from urllib.parse import urlparse
            parsed_url = urlparse(website['url'])
            domain_name = parsed_url.netloc.replace('.', '_').replace(':', '_')
            blur_dir = os.path.join('data', 'snapshots', domain_name, website_id, 'blur_images')
        else:
            # Fallback to old method if website not found
            blur_dir = os.path.join('data', 'snapshots', self._sanitize_site_id(website_id), 'blur_images')
        
        os.makedirs(blur_dir, exist_ok=True)
        return blur_dir
    
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

    def _download_image(self, image_url, page_url):
        """Download an image from a URL and return the image data."""
        try:
            # Skip data URLs (base64 encoded images, tracking pixels, etc.)
            if image_url.startswith('data:'):
                self.logger.debug(f"Skipping data URL: {image_url[:50]}...")
                return None
            
            # Skip obvious non-image URLs (tracking pixels, analytics, etc.)
            if any(domain in image_url.lower() for domain in [
                'facebook.com/tr', 'google-analytics.com', 'googletagmanager.com',
                'doubleclick.net', 'googlesyndication.com', 'googleadservices.com'
            ]):
                self.logger.debug(f"Skipping tracking/analytics URL: {image_url}")
                return None
            
            # Make absolute URL if relative
            if not image_url.startswith(('http://', 'https://')):
                image_url = urljoin(page_url, image_url)
            
            # Download the image
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(image_url, headers=headers, timeout=10, stream=True)
            response.raise_for_status()
            
            # Check if it's actually an image
            content_type = response.headers.get('content-type', '').lower()
            if not content_type.startswith('image/'):
                self.logger.warning(f"URL {image_url} does not appear to be an image (content-type: {content_type})")
                return None
            
            # Read the image data
            image_data = response.content
            
            # Validate minimum size
            if len(image_data) < 1024:  # Less than 1KB - probably not a real image
                self.logger.debug(f"Image too small ({len(image_data)} bytes), skipping: {image_url}")
                return None
            
            return image_data
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error downloading image {image_url}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error downloading image {image_url}: {e}")
            return None

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
            
            # Convert relative URLs to absolute
            if not image_url.startswith(('http://', 'https://')):
                image_url = urljoin(page_url, image_url)
            
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

    def analyze_website_images(self, website_id, all_images_data, crawl_id=None):
        """Analyze all images from all pages of a website in a single batch operation."""
        if not all_images_data:
            self.logger.debug(f"No images found for website {website_id}")
            return []
        
        # Single cleanup operation for the entire website
        self.cleanup_blur_data_for_website(website_id)
        
        # Create blur images directory
        blur_dir = self._create_blur_images_directory(website_id)
        
        results = []
        processed_count = 0
        max_workers = 5  # As requested by user
        
        # Group images by page for better logging
        pages_with_images = {}
        for img_data in all_images_data:
            page_url = img_data['page_url']
            if page_url not in pages_with_images:
                pages_with_images[page_url] = 0
            pages_with_images[page_url] += 1
        
        total_pages = len(pages_with_images)
        total_images = len(all_images_data)
        
        self.logger.info(f"Starting parallel blur analysis for {total_images} internal images from {total_pages} pages of website {website_id} using {max_workers} workers")
        
        # Step 1: Parallel downloading and saving of all images
        download_args = []
        for i, img_data in enumerate(all_images_data):
            # Create a unique filename that includes page info
            page_url = img_data['page_url']
            image_url = img_data['image_url']
            
            # Generate page-specific index for filename
            page_index = list(pages_with_images.keys()).index(page_url) + 1
            
            download_args.append((i, image_url, page_url, blur_dir, page_index))
        
        downloaded_images = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as download_executor:
            download_results = download_executor.map(self._download_and_save_image_batch, download_args)
            
            for result in download_results:
                if result and result[3]:  # If download was successful
                    downloaded_images.append((result[0], result[1], result[2]))  # (local_path, image_url, page_url)
                elif result and not result[3]:  # If download failed
                    self.logger.warning(f"Failed to download image: {result[1]}")
        
        self.logger.info(f"Downloaded {len(downloaded_images)} out of {total_images} images successfully")
        
        # Step 2: Parallel analysis of all downloaded images
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
        
        self.logger.info(f"Completed parallel blur analysis: {processed_count}/{total_images} images processed from {total_pages} pages")
        
        # Save all results to database if crawl_id is provided
        if crawl_id and results:
            self._save_results_to_db(crawl_id, results)
        
        return results
    
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