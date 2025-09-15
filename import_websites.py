#!/usr/bin/env python3
import sys
import os
sys.path.append('/app')

from src.website_manager_sqlite import WebsiteManagerSQLite
from src.scheduler_integration import reschedule_tasks
import csv

def import_websites_from_csv(csv_file):
    """Import websites from CSV file into the database."""
    print(f'Importing websites from {csv_file}...')
    
    # Initialize website manager
    wm = WebsiteManagerSQLite()
    
    imported_count = 0
    failed_count = 0
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                name = row.get('name', '').strip()
                url = row.get('url', '').strip()
                
                if name and url:
                    try:
                        # Convert monitoring_interval from seconds to minutes
                        monitoring_interval_seconds = int(row.get('monitoring_interval', 900))
                        check_interval_minutes = monitoring_interval_seconds // 60
                        
                        # Parse exclude pages keywords
                        exclude_keywords_str = row.get('exclude_pages_keywords', '').strip()
                        exclude_keywords = [k.strip() for k in exclude_keywords_str.split(',') if k.strip()] if exclude_keywords_str else []
                        
                        website_data = {
                            'name': name,
                            'url': url,
                            'check_interval_minutes': check_interval_minutes,
                            'is_active': True,
                            'max_crawl_depth': int(row.get('max_depth', 2)),
                            'auto_crawl_enabled': row.get('enable_crawl', 'true').lower() == 'true',
                            'auto_visual_enabled': row.get('enable_visual', 'true').lower() == 'true',
                            'auto_blur_enabled': row.get('enable_blur_detection', 'true').lower() == 'true',
                            'auto_performance_enabled': row.get('enable_performance', 'true').lower() == 'true',
                            'auto_full_check_enabled': True,
                            'exclude_pages_keywords': exclude_keywords,
                            'tags': [],
                            'notification_emails': []
                        }
                        
                        result = wm.add_website(website_data)
                        if result:
                            print(f'SUCCESS: {name} ({check_interval_minutes} min interval)')
                            imported_count += 1
                        else:
                            print(f'FAILED: {name}')
                            failed_count += 1
                            
                    except Exception as e:
                        print(f'ERROR importing {name}: {e}')
                        failed_count += 1
        
        print(f'
Import complete: {imported_count} successful, {failed_count} failed')
        
        # Reschedule tasks
        print('Rescheduling tasks...')
        reschedule_tasks()
        print('Scheduler updated with new websites')
        
    except Exception as e:
        print(f'Error: {e}')

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: python import_websites.py <csv_file>')
        sys.exit(1)
    
    csv_file = sys.argv[1]
    if not os.path.exists(csv_file):
        print(f'Error: File {csv_file} not found')
        sys.exit(1)
    
    import_websites_from_csv(csv_file)
