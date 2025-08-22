#!/usr/bin/env python3
"""
Performance Checker Module
Handles website performance monitoring using Google PageSpeed Insights API
"""

import os
import json
import sqlite3
import requests
import time
from datetime import datetime, timezone
from urllib.parse import urlparse
from src.config_loader import get_config
from src.logger_setup import setup_logging
from src.path_utils import get_database_path, ensure_directory_exists
from src.website_manager_sqlite import WebsiteManager

logger = setup_logging()

class PerformanceChecker:
    def __init__(self, config_path=None):
        self.logger = logger
        self.config = get_config(config_path=config_path)
        
        # Google PageSpeed Insights API settings
        self.api_key = self.config.get('google_pagespeed_api_key', '')
        self.api_url = 'https://www.googleapis.com/pagespeedonline/v5/runPagespeed'
        
        # Initialize database tables during initialization
        self._init_performance_tables()
        
        self.logger.info("PerformanceChecker initialized")
    
    def _get_db_connection(self):
        """Get database connection for storing performance results."""
        import os
        db_path = get_database_path()
        ensure_directory_exists(os.path.dirname(db_path))
        conn = sqlite3.connect(str(db_path))
        return conn
    
    def _init_performance_tables(self):
        """Initialize database tables for performance monitoring."""
        conn = self._get_db_connection()
        try:
            cursor = conn.cursor()
            
            # Create performance_results table with display values
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS performance_results (
                    id INTEGER PRIMARY KEY,
                    website_id TEXT,
                    crawl_id INTEGER,
                    url TEXT,
                    page_title TEXT,
                    device_type TEXT,
                    performance_score INTEGER,
                    fcp_score REAL,
                    fcp_display TEXT,
                    lcp_score REAL,
                    lcp_display TEXT,
                    cls_score REAL,
                    cls_display TEXT,
                    fid_score REAL,
                    fid_display TEXT,
                    speed_index REAL,
                    speed_index_display TEXT,
                    total_blocking_time REAL,
                    tbt_display TEXT,
                    timestamp TEXT,
                    raw_data TEXT,
                    FOREIGN KEY (crawl_id) REFERENCES crawl_results (id)
                )
            ''')
            
            # Add new columns to existing table if they don't exist
            try:
                cursor.execute('ALTER TABLE performance_results ADD COLUMN page_title TEXT')
                cursor.execute('ALTER TABLE performance_results ADD COLUMN fcp_display TEXT')
                cursor.execute('ALTER TABLE performance_results ADD COLUMN lcp_display TEXT')
                cursor.execute('ALTER TABLE performance_results ADD COLUMN cls_display TEXT')
                cursor.execute('ALTER TABLE performance_results ADD COLUMN fid_display TEXT')
                cursor.execute('ALTER TABLE performance_results ADD COLUMN speed_index_display TEXT')
                cursor.execute('ALTER TABLE performance_results ADD COLUMN tbt_display TEXT')
            except sqlite3.OperationalError:
                # Columns already exist
                pass
            
            conn.commit()
            self.logger.debug("Performance database tables initialized")
        except Exception as e:
            self.logger.error(f"Error initializing performance tables: {e}", exc_info=True)
        finally:
            conn.close()
    
    def check_website_performance(self, website_id, crawl_id=None, pages_to_check=None):
        """
        Check website performance using Google PageSpeed Insights API.
        
        Args:
            website_id (str): Website ID to check
            crawl_id (int, optional): Associated crawl ID
            pages_to_check (list, optional): List of page dictionaries to check
                                           Format: [{'url': 'url', 'title': 'title'}, ...]
                                           If None, checks main website URL only
            
        Returns:
            dict: Performance results for all pages
        """
        
        # Get website details
        website_manager = WebsiteManager()
        website = website_manager.get_website(website_id)
        
        if not website:
            self.logger.error(f"Website {website_id} not found")
            return {"error": "Website not found"}
        
        main_url = website.get('url')
        if not main_url:
            self.logger.error(f"No URL found for website {website_id}")
            return {"error": "No URL found"}
        
        # If no pages specified, check main URL only
        if not pages_to_check:
            pages_to_check = [{'url': main_url, 'title': website.get('name', 'Homepage')}]
        
        results = {
            'performance_check_summary': {
                'enabled': True,
                'main_url': main_url,
                'timestamp': datetime.now().isoformat(),
                'pages_analyzed': len(pages_to_check),
                'results': {}
            }
        }
        
        # Check if API key is configured
        if not self.api_key:
            self.logger.warning("Google PageSpeed API key not configured. Performance check disabled.")
            results['performance_check_summary']['enabled'] = False
            results['performance_check_summary']['error'] = 'API key not configured'
            return results
        
        # Check both mobile and desktop for each page
        devices = ['mobile', 'desktop']
        
        for page_info in pages_to_check:
            page_url = page_info['url']
            page_title = page_info.get('title', 'Unknown Page')
            
            # Skip external URLs - only check internal pages
            if not self._is_internal_url(page_url, main_url):
                self.logger.debug(f"Skipping external URL: {page_url}")
                continue
            
            self.logger.info(f"Checking performance for page: {page_title} ({page_url})")
            
            page_results = {}
            
            for device in devices:
                try:
                    self.logger.info(f"Checking {page_url} on {device}")
                    
                    # Call Google PageSpeed Insights API
                    performance_data = self._call_pagespeed_api(page_url, device)
                    
                    if performance_data:
                        # Process and store results
                        processed_data = self._process_performance_data(performance_data, device)
                        processed_data['page_title'] = page_title
                        
                        # Store in database
                        self._store_performance_result(
                            website_id, crawl_id, page_url, device, 
                            processed_data, performance_data
                        )
                        
                        # Add to results
                        page_results[device] = processed_data
                        
                        self.logger.info(f"Performance check completed for {page_url} on {device}")
                    else:
                        self.logger.warning(f"No performance data received for {page_url} on {device}")
                        page_results[device] = {
                            'error': 'No data received from API'
                        }
                    
                    # Add delay between requests to respect API limits
                    time.sleep(2)  # Increased delay for multiple pages
                    
                except Exception as e:
                    self.logger.error(f"Error checking performance for {page_url} on {device}: {e}", exc_info=True)
                    page_results[device] = {
                        'error': str(e)
                    }
            
            # Store page results
            results['performance_check_summary']['results'][page_url] = {
                'page_title': page_title,
                'url': page_url,
                'results': page_results
            }
        
        return results
    
    def _is_internal_url(self, url, main_url):
        """Check if a URL is internal to the main website."""
        try:
            from urllib.parse import urlparse
            
            main_parsed = urlparse(main_url)
            url_parsed = urlparse(url)
            
            # Compare domains (case-insensitive)
            return url_parsed.netloc.lower() == main_parsed.netloc.lower()
        except Exception:
            return False
    
    def _call_pagespeed_api(self, url, strategy='mobile'):
        """
        Call Google PageSpeed Insights API.
        
        Args:
            url (str): URL to analyze
            strategy (str): 'mobile' or 'desktop'
            
        Returns:
            dict: API response data
        """
        params = {
            'url': url,
            'key': self.api_key,
            'strategy': strategy,
            'category': ['PERFORMANCE'],
            'locale': 'en'
        }
        
        try:
            response = requests.get(self.api_url, params=params, timeout=30)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"PageSpeed API request failed: {e}")
            return None
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse PageSpeed API response: {e}")
            return None
    
    def _process_performance_data(self, api_data, device_type):
        """
        Process raw PageSpeed API data into useful metrics.
        
        Args:
            api_data (dict): Raw API response
            device_type (str): 'mobile' or 'desktop'
            
        Returns:
            dict: Processed performance metrics
        """
        try:
            lighthouse_result = api_data.get('lighthouseResult', {})
            audits = lighthouse_result.get('audits', {})
            categories = lighthouse_result.get('categories', {})
            
            # Overall performance score
            performance_category = categories.get('performance', {})
            performance_score = int(performance_category.get('score', 0) * 100)
            
            # Core Web Vitals
            fcp = audits.get('first-contentful-paint', {})
            lcp = audits.get('largest-contentful-paint', {})
            cls = audits.get('cumulative-layout-shift', {})
            fid = audits.get('max-potential-fid', {})  # FID approximation
            
            # Other metrics
            speed_index = audits.get('speed-index', {})
            tbt = audits.get('total-blocking-time', {})
            
            processed = {
                'device_type': device_type,
                'performance_score': performance_score,
                'performance_grade': self._get_performance_grade(performance_score),
                'metrics': {
                    'first_contentful_paint': {
                        'value': fcp.get('numericValue', 0),
                        'displayValue': fcp.get('displayValue', 'N/A'),
                        'score': fcp.get('score', 0)
                    },
                    'largest_contentful_paint': {
                        'value': lcp.get('numericValue', 0),
                        'displayValue': lcp.get('displayValue', 'N/A'),
                        'score': lcp.get('score', 0)
                    },
                    'cumulative_layout_shift': {
                        'value': cls.get('numericValue', 0),
                        'displayValue': cls.get('displayValue', 'N/A'),
                        'score': cls.get('score', 0)
                    },
                    'max_potential_fid': {
                        'value': fid.get('numericValue', 0),
                        'displayValue': fid.get('displayValue', 'N/A'),
                        'score': fid.get('score', 0)
                    },
                    'speed_index': {
                        'value': speed_index.get('numericValue', 0),
                        'displayValue': speed_index.get('displayValue', 'N/A'),
                        'score': speed_index.get('score', 0)
                    },
                    'total_blocking_time': {
                        'value': tbt.get('numericValue', 0),
                        'displayValue': tbt.get('displayValue', 'N/A'),
                        'score': tbt.get('score', 0)
                    }
                }
            }
            
            return processed
            
        except Exception as e:
            self.logger.error(f"Error processing performance data: {e}", exc_info=True)
            return {
                'device_type': device_type,
                'error': str(e)
            }
    
    def _get_performance_grade(self, score):
        """Convert numeric score to letter grade."""
        if score >= 90:
            return 'A'
        elif score >= 50:
            return 'B'
        else:
            return 'C'
    
    def _store_performance_result(self, website_id, crawl_id, url, device_type, processed_data, raw_data):
        """Store performance result in database."""
        conn = self._get_db_connection()
        try:
            cursor = conn.cursor()
            
            metrics = processed_data.get('metrics', {})
            
            cursor.execute('''
                INSERT INTO performance_results 
                (website_id, crawl_id, url, page_title, device_type, performance_score, 
                 fcp_score, fcp_display, lcp_score, lcp_display, cls_score, cls_display, 
                 fid_score, fid_display, speed_index, speed_index_display, total_blocking_time, 
                 tbt_display, timestamp, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                website_id,
                crawl_id,
                url,
                processed_data.get('page_title', 'N/A'), # Add page_title
                device_type,
                processed_data.get('performance_score', 0),
                metrics.get('first_contentful_paint', {}).get('score', 0),
                metrics.get('first_contentful_paint', {}).get('displayValue', 'N/A'), # Add fcp_display
                metrics.get('largest_contentful_paint', {}).get('score', 0),
                metrics.get('largest_contentful_paint', {}).get('displayValue', 'N/A'), # Add lcp_display
                metrics.get('cumulative_layout_shift', {}).get('score', 0),
                metrics.get('cumulative_layout_shift', {}).get('displayValue', 'N/A'), # Add cls_display
                metrics.get('max_potential_fid', {}).get('score', 0),
                metrics.get('max_potential_fid', {}).get('displayValue', 'N/A'), # Add fid_display
                metrics.get('speed_index', {}).get('value', 0),
                metrics.get('speed_index', {}).get('displayValue', 'N/A'), # Add speed_index_display
                metrics.get('total_blocking_time', {}).get('value', 0),
                metrics.get('total_blocking_time', {}).get('displayValue', 'N/A'), # Add tbt_display
                datetime.now().isoformat(),
                json.dumps(raw_data)
            ))
            
            conn.commit()
            self.logger.debug(f"Stored performance result for {url} ({device_type})")
            
        except Exception as e:
            self.logger.error(f"Error storing performance result: {e}", exc_info=True)
        finally:
            conn.close()
    
    def get_latest_performance_results(self, website_id, limit=20):
        """Get latest performance results for a website."""
        conn = self._get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM performance_results 
                WHERE website_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (website_id, limit))
            
            results = []
            for row in cursor.fetchall():
                # Handle both old and new schema
                if len(row) >= 21:  # New schema with display values (21 columns)
                    results.append({
                        'id': row[0],
                        'website_id': row[1],
                        'crawl_id': row[2],
                        'url': row[3],
                        'device_type': row[4],
                        'performance_score': row[5],
                        'fcp_score': row[6],
                        'lcp_score': row[7],
                        'cls_score': row[8],
                        'fid_score': row[9],
                        'speed_index': row[10],
                        'total_blocking_time': row[11],
                        'timestamp': row[12],
                        'raw_data': row[13],
                        'page_title': row[14],
                        'fcp_display': row[15],
                        'lcp_display': row[16],
                        'cls_display': row[17],
                        'fid_display': row[18],
                        'speed_index_display': row[19],
                        'tbt_display': row[20]
                    })
                else:  # Old schema fallback
                    results.append({
                        'id': row[0],
                        'website_id': row[1],
                        'crawl_id': row[2],
                        'url': row[3],
                        'page_title': 'N/A',
                        'device_type': row[4],
                        'performance_score': row[5],
                        'fcp_score': row[6],
                        'fcp_display': self._format_metric_display(row[6], 'fcp'),
                        'lcp_score': row[7],
                        'lcp_display': self._format_metric_display(row[7], 'lcp'),
                        'cls_score': row[8],
                        'cls_display': self._format_metric_display(row[8], 'cls'),
                        'fid_score': row[9],
                        'fid_display': self._format_metric_display(row[9], 'fid'),
                        'speed_index': row[10],
                        'speed_index_display': self._format_metric_display(row[10], 'speed_index'),
                        'total_blocking_time': row[11],
                        'tbt_display': self._format_metric_display(row[11], 'tbt'),
                        'timestamp': row[12]
                    })
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error getting performance results: {e}", exc_info=True)
            return []
        finally:
            conn.close()
    
    def _format_metric_display(self, value, metric_type):
        """Format metric values for display when no display value is available."""
        if value is None or value == 0:
            return 'N/A'
        
        if metric_type in ['fcp', 'lcp', 'fid']:
            return f"{value:.2f}"
        elif metric_type == 'cls':
            return f"{value:.3f}"
        elif metric_type == 'speed_index':
            return f"{value / 1000:.1f}s" if value > 0 else 'N/A'
        elif metric_type == 'tbt':
            return f"{value:.0f}ms" if value > 0 else 'N/A'
        else:
            return str(value)

# Example usage
if __name__ == "__main__":
    checker = PerformanceChecker()
    results = checker.check_website_performance("test-website-id")
    print(json.dumps(results, indent=2)) 