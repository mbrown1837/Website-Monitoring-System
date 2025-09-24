"""
Queue Processor for Manual Checks

This module handles the processing of manual check requests in a queue system
with priority handling and real-time status updates.
"""

import time
import threading
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from src.website_manager_sqlite import WebsiteManagerSQLite
from src.history_manager_sqlite import HistoryManager
from src.crawler_module import CrawlerModule
from src.logger_setup import setup_logging
from src.config_loader import get_config

class QueueProcessor:
    def __init__(self, config_path=None):
        self.config = get_config(config_path=config_path) if config_path else get_config()
        self.logger = setup_logging(config_path=config_path) if config_path else setup_logging()
        
        # Initialize managers
        self.website_manager = WebsiteManagerSQLite(config_path=config_path)
        self.history_manager = HistoryManager(config_path=config_path)
        self.crawler_module = CrawlerModule(config_path=config_path)
        
        # Force load websites to ensure cache is populated
        self.website_manager._load_websites(force_reload=True)
        self.logger.info(f"Queue processor loaded {len(self.website_manager._websites_cache)} websites")
        if self.website_manager._websites_cache:
            website_ids = list(self.website_manager._websites_cache.keys())
            self.logger.info(f"Website IDs in cache: {website_ids}")
        else:
            self.logger.warning("No websites found in cache after loading!")
        
        # Queue processing control
        self._running = False
        self._processing_thread = None
        self._stop_event = threading.Event()
        
        # Concurrency control - ensure only one item processes at a time
        self._processing_lock = threading.Lock()
        self._currently_processing = None
        
        # WebSocket connections for real-time updates
        self._websocket_connections = set()
        
        self.logger.info("Queue Processor initialized")
    
    def start(self):
        """Start the queue processor in a background thread."""
        if self._running:
            self.logger.warning("Queue processor is already running")
            return
        
        self._running = True
        self._stop_event.clear()
        self._processing_thread = threading.Thread(target=self._process_queue_loop, daemon=True)
        self._processing_thread.start()
        self.logger.info("🚀 Queue processor started")
    
    def stop(self):
        """Stop the queue processor."""
        if not self._running:
            return
        
        self._running = False
        self._stop_event.set()
        
        if self._processing_thread and self._processing_thread.is_alive():
            self._processing_thread.join(timeout=10)
        
        self.logger.info("🛑 Queue processor stopped")
    
    def _process_queue_loop(self):
        """Main queue processing loop with strict sequential processing."""
        self.logger.info("🔄 Starting queue processing loop")
        
        while self._running and not self._stop_event.is_set():
            try:
                # Check if we're already processing something
                with self._processing_lock:
                    if self._currently_processing is not None:
                        self.logger.info(f"⏳ Waiting for {self._currently_processing} to finish before processing next item")
                        time.sleep(2)
                        continue
                
                # Get next item from queue
                queue_item = self.website_manager.get_next_queue_item()
                
                if queue_item:
                    # Set processing lock
                    with self._processing_lock:
                        self._currently_processing = queue_item['id']
                    
                    self.logger.info(f"🔄 Processing queue item {queue_item['id']}: {queue_item['check_type']} check for {queue_item['website_name']}")
                    self._process_queue_item(queue_item)
                    
                    # Clear processing lock
                    with self._processing_lock:
                        self._currently_processing = None
                    
                    # Add delay between items to prevent overwhelming the system
                    time.sleep(1)
                else:
                    # No items in queue, wait a bit
                    time.sleep(2)
                    
            except Exception as e:
                self.logger.error(f"Error in queue processing loop: {e}", exc_info=True)
                # Clear processing lock on error
                with self._processing_lock:
                    self._currently_processing = None
                time.sleep(5)  # Wait before retrying
        
        self.logger.info("🔄 Queue processing loop ended")
    
    def _process_queue_item(self, queue_item):
        """Process a single queue item."""
        queue_id = queue_item['id']
        website_id = queue_item['website_id']
        check_type = queue_item['check_type']
        website_name = queue_item['website_name']
        
        self.logger.info(f"🔄 Processing queue item {queue_id}: {check_type} check for {website_name}")
        
        try:
            # Update status to processing
            self.website_manager.update_queue_status(queue_id, 'processing')
            self._broadcast_status_update(queue_id, 'processing', f"Processing {check_type} check for {website_name}")
            
            # Get website configuration - use direct database query for reliability
            self.logger.info(f"Loading website {website_id} for manual check... (UPDATED CODE)")
            
            # Query database directly to avoid cache issues
            import sqlite3
            import json
            try:
                with sqlite3.connect(self.website_manager.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM websites WHERE id = ?", (website_id,))
                    row = cursor.fetchone()
                    if row:
                        columns = [description[0] for description in cursor.description]
                        website = dict(zip(columns, row))
                        
                        # Parse JSON fields like the normal load method
                        if website.get('tags'):
                            try:
                                website['tags'] = json.loads(website['tags'])
                            except:
                                website['tags'] = []
                        if website.get('notification_emails'):
                            try:
                                website['notification_emails'] = json.loads(website['notification_emails'])
                            except:
                                website['notification_emails'] = []
                        if website.get('all_baselines'):
                            try:
                                website['all_baselines'] = json.loads(website['all_baselines'])
                            except:
                                website['all_baselines'] = {}
                        if website.get('exclude_pages_keywords'):
                            try:
                                website['exclude_pages_keywords'] = json.loads(website['exclude_pages_keywords'])
                            except:
                                website['exclude_pages_keywords'] = []
                        
                        # Convert boolean fields
                        website['is_active'] = bool(website['is_active'])
                        website['capture_subpages'] = bool(website['capture_subpages'])
                        website['has_subpage_baselines'] = bool(website['has_subpage_baselines'])
                        website['enable_blur_detection'] = bool(website['enable_blur_detection'])
                        website['blur_detection_scheduled'] = bool(website['blur_detection_scheduled'])
                        website['blur_detection_manual'] = bool(website['blur_detection_manual'])
                        website['auto_crawl_enabled'] = bool(website['auto_crawl_enabled'])
                        website['auto_visual_enabled'] = bool(website['auto_visual_enabled'])
                        website['auto_blur_enabled'] = bool(website['auto_blur_enabled'])
                        website['auto_performance_enabled'] = bool(website['auto_performance_enabled'])
                        website['auto_full_check_enabled'] = bool(website['auto_full_check_enabled'])
                        
                        self.logger.info(f"Successfully loaded website {website_id} from database: {website.get('name', 'Unknown')}")
                    else:
                        raise Exception(f"Website {website_id} not found in database")
            except Exception as e:
                self.logger.error(f"Failed to load website {website_id} from database: {e}")
                raise Exception(f"Website {website_id} not found")
            
            # Get check configuration based on check type
            check_config = self.website_manager.get_manual_check_config(website_id, check_type)
            
            # Perform the check using crawler module
            # Handle baseline checks specially
            # For 'full' checks, create baseline if website doesn't have any baselines yet
            has_baselines = bool(website.get('all_baselines'))
            create_baseline = (check_type == 'baseline') or (check_type == 'full' and not has_baselines)
            
            self.logger.info(f"Baseline creation decision for {website_name}: check_type={check_type}, has_baselines={has_baselines}, create_baseline={create_baseline}")
            
            results = self.crawler_module.crawl_website(
                website_id=website_id,
                url=website['url'],
                check_config=check_config,
                is_scheduled=False,
                create_baseline=create_baseline
            )
            
            # Update status to completed
            # Convert results to JSON-serializable format
            serializable_results = self._make_json_serializable(results)
            self.website_manager.update_queue_status(
                queue_id, 
                'completed', 
                result_data=serializable_results
            )
            
            self.logger.info(f"✅ Completed queue item {queue_id}: {check_type} check for {website_name}")
            self._broadcast_status_update(queue_id, 'completed', f"Completed {check_type} check for {website_name}")
            
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"❌ Failed queue item {queue_id}: {error_msg}")
            
            # Convert technical error to user-friendly message
            user_friendly_error = self._convert_error_to_user_friendly(e, check_type)
            
            # Update status to failed
            self.website_manager.update_queue_status(
                queue_id, 
                'failed', 
                error_message=user_friendly_error
            )
            
            self._broadcast_status_update(queue_id, 'failed', f"Failed {check_type} check for {website_name}: {user_friendly_error}")
        
        finally:
            # Ensure processing lock is always released
            with self._processing_lock:
                if self._currently_processing == queue_id:
                    self._currently_processing = None
                    self.logger.info(f"🔓 Released processing lock for {queue_id}")
    
    def add_manual_check(self, website_id, check_type, user_id=None):
        """Add a manual check to the queue."""
        try:
            queue_id = self.website_manager.add_to_queue(website_id, check_type, user_id)
            
            # Get website info for status
            website = self.website_manager.get_website(website_id)
            website_name = website.get('name', 'Unknown') if website else 'Unknown'
            
            self.logger.info(f"➕ Added {check_type} check for {website_name} to queue (ID: {queue_id})")
            self._broadcast_status_update(queue_id, 'pending', f"Added {check_type} check for {website_name} to queue")
            
            return queue_id
            
        except Exception as e:
            self.logger.error(f"Error adding manual check to queue: {e}")
            raise
    
    def get_queue_status(self, queue_id=None, website_id=None):
        """Get queue status."""
        return self.website_manager.get_queue_status(queue_id, website_id)
    
    def _make_json_serializable(self, obj):
        """Convert objects to JSON-serializable format."""
        if isinstance(obj, dict):
            return {key: self._make_json_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._make_json_serializable(item) for item in obj]
        elif isinstance(obj, set):
            return list(obj)  # Convert sets to lists
        elif isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        else:
            # For other types, convert to string
            return str(obj)
    
    def _convert_error_to_user_friendly(self, error, check_type):
        """Convert technical errors to user-friendly messages."""
        error_str = str(error).lower()
        
        # Network-related errors
        if 'connection' in error_str or 'timeout' in error_str:
            return f"Unable to connect to the website. Please check if the website is accessible and try again."
        elif 'dns' in error_str or 'name resolution' in error_str:
            return f"Website domain could not be found. Please verify the website URL is correct."
        elif 'ssl' in error_str or 'certificate' in error_str:
            return f"SSL certificate issue detected. The website may have security certificate problems."
        elif 'permission' in error_str or 'forbidden' in error_str:
            return f"Access denied to the website. The website may be blocking automated requests."
        elif 'not found' in error_str or '404' in error_str:
            return f"Website page not found. The requested page may have been moved or deleted."
        elif 'server error' in error_str or '500' in error_str:
            return f"Website server error. The website may be experiencing technical difficulties."
        elif 'rate limit' in error_str or 'too many requests' in error_str:
            return f"Too many requests to the website. Please wait a moment before trying again."
        elif 'timeout' in error_str:
            return f"Request timed out. The website is taking too long to respond."
        
        # Check-specific errors
        if check_type == 'visual':
            return f"Visual check failed. Unable to capture website screenshots. This may be due to website restrictions or technical issues."
        elif check_type == 'crawl':
            return f"Crawl check failed. Unable to analyze website content. The website may be blocking automated crawlers."
        elif check_type == 'performance':
            return f"Performance check failed. Unable to analyze website performance. The performance analysis service may be unavailable."
        elif check_type == 'blur':
            return f"Blur detection failed. Unable to analyze images for blur. This may be due to image access restrictions."
        elif check_type == 'baseline':
            return f"Baseline creation failed. Unable to create baseline images. This may be due to website access restrictions."
        
        # Generic fallback
        return f"Check failed due to an unexpected error. Please try again or contact support if the issue persists."
    
    def _broadcast_status_update(self, queue_id, status, message):
        """Broadcast status update to all WebSocket connections."""
        try:
            update_data = {
                'type': 'status_update',
                'queue_id': queue_id,
                'status': status,
                'message': message,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            # TODO: Implement WebSocket broadcasting
            # For now, just log the update
            self.logger.info(f"📡 Status update: {json.dumps(update_data)}")
            
        except Exception as e:
            self.logger.error(f"Error broadcasting status update: {e}")
    
    def add_websocket_connection(self, websocket):
        """Add a WebSocket connection for real-time updates."""
        self._websocket_connections.add(websocket)
        self.logger.info(f"📡 Added WebSocket connection (total: {len(self._websocket_connections)})")
    
    def remove_websocket_connection(self, websocket):
        """Remove a WebSocket connection."""
        self._websocket_connections.discard(websocket)
        self.logger.info(f"📡 Removed WebSocket connection (total: {len(self._websocket_connections)})")
    
    def clear_all_pending_items(self):
        """Clear all pending and processing items from the queue."""
        try:
            cleared_count = self.website_manager.clear_pending_queue_items()
            self.logger.info(f"🧹 Cleared {cleared_count} pending/processing items from queue")
            return cleared_count
        except Exception as e:
            self.logger.error(f"Error clearing pending items: {e}")
            raise

# Global queue processor instance
_queue_processor = None

def get_queue_processor(config_path=None):
    """Get the global queue processor instance."""
    global _queue_processor
    if _queue_processor is None:
        _queue_processor = QueueProcessor(config_path)
    return _queue_processor

def start_queue_processor(config_path=None):
    """Start the global queue processor."""
    processor = get_queue_processor(config_path)
    processor.start()
    return processor

def stop_queue_processor():
    """Stop the global queue processor."""
    global _queue_processor
    if _queue_processor:
        _queue_processor.stop()
        _queue_processor = None
