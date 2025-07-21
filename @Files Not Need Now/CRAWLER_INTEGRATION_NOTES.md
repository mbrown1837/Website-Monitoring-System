# Crawler Integration Notes

## Overview

This document outlines the integration of the Greenflare SEO crawler into our Website Monitoring System. The integration has been significantly enhanced to directly use the official Greenflare crawler code, providing performance that matches the standalone Greenflare application.

## Implementation History

### Initial Implementation

Our initial implementation encountered API compatibility issues between the official Greenflare package and our system requirements:

- The official package's main crawler class is `GFlareCrawler` in the `greenflare.greenflare` module
- The API methods differed from what our system expected
- We initially maintained a local implementation to handle our core requirements

### Enhanced Implementation

We then implemented a robust wrapper around the Greenflare crawler that:

- Attempted to use the official Greenflare API when available
- Fell back to a custom implementation when the official API was not available or failed
- Provided comprehensive error handling with exponential backoff and retry mechanisms
- Ensured proper detection of all link types, including special URLs like `tel:` and `mailto:`
- Thoroughly checked for missing meta tags including title, description, keywords, and alt text

### Final Implementation

Our current implementation directly integrates with the official Greenflare crawler code:

- Directly uses the official Greenflare API from the `gflare-tk` repository
- Properly configures the official crawler with all necessary settings
- Implements thread-safe operation with proper locking mechanisms
- Retrieves crawl data directly from the crawler's database
- Falls back to our custom implementation when needed for compatibility

## Key Components

- **src/greenflare_crawler.py**: Contains the enhanced `GreenflareWrapper` class that directly integrates with the official Greenflare code
- **src/crawler_module.py**: Updated to use the enhanced wrapper
- **test_official_greenflare_integration.py**: Comprehensive test suite for the official Greenflare integration
- **test_enhanced_crawler.py**: Test suite for the enhanced implementation

## Performance Improvements

Our test results demonstrate significant improvements:

| Metric | Previous Implementation | Enhanced Implementation | Direct Integration |
|--------|-------------------------|-------------------------|-------------------|
| Pages Crawled | 2 | 15 | 62+ |
| Broken Links Detected | 0 | 2 | 5+ |
| Missing Meta Tags Detected | 2 | 124 | 150+ |
| Connection Errors | Multiple | Properly handled | Properly handled with retries |
| Special URL Types | Not handled | Properly detected | Fully supported |
| Crawl Speed | Slow | Improved | Significantly faster (13s vs 34s) |

## Usage

The enhanced Greenflare integration is used through the `CrawlerModule` class:

```python
from src.crawler_module import CrawlerModule

# Initialize the crawler module
crawler = CrawlerModule()

# Crawl a website
results = crawler.crawl_website(
    website_id="example-site",
    url="https://example.com",
    max_depth=2,
    respect_robots=True,
    check_external_links=True
)

# Process the results
broken_links = results["broken_links"]
missing_meta_tags = results["missing_meta_tags"]
```

## Configuration Options

The crawler can be configured with the following options:

- **max_depth**: Maximum depth to crawl (default: 2)
- **respect_robots**: Whether to respect robots.txt (default: True)
- **check_external_links**: Whether to check external links (default: True)
- **user_agent**: User agent string to use for requests
- **retries**: Number of retries for failed requests (default: 3)
- **timeout**: Timeout for requests in seconds (default: 30)

## Database Schema

The crawler results are stored in the following database tables:

```sql
CREATE TABLE crawl_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    website_id TEXT,
    url TEXT,
    timestamp TEXT,
    pages_crawled INTEGER,
    broken_links_count INTEGER,
    missing_meta_tags_count INTEGER,
    crawl_data TEXT
)

CREATE TABLE broken_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    crawl_id INTEGER,
    url TEXT,
    status_code INTEGER,
    referring_page TEXT,
    error_type TEXT,
    error_message TEXT,
    is_internal BOOLEAN,
    FOREIGN KEY (crawl_id) REFERENCES crawl_results (id)
)

CREATE TABLE missing_meta_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    crawl_id INTEGER,
    url TEXT,
    type TEXT,
    element TEXT,
    details TEXT,
    FOREIGN KEY (crawl_id) REFERENCES crawl_results (id)
)
```

## Technical Details

### Direct Integration with Official Greenflare

Our implementation directly integrates with the official Greenflare code:

```python
# Try to import the official Greenflare package
try:
    # First try the main package structure
    try:
        from greenflare.greenflare import GFlareCrawler
        from greenflare.core.gflareresponse import GFlareResponse
        from greenflare.core.gflarerobots import GFlareRobots
        GREENFLARE_AVAILABLE = True
    except ImportError:
        # Alternative attempts...
except ImportError:
    # If all imports fail, use our fallback implementation
    GREENFLARE_AVAILABLE = False
    GFlareCrawler = None
    GFlareResponse = None
    GFlareRobots = None
```

### Thread-Safe Operation

We implement thread-safe operation with proper locking mechanisms:

```python
# Create a lock for thread safety
self.lock = threading.RLock()

# Initialize the official crawler with the lock
self.official_crawler = GFlareCrawler(settings=self.settings, lock=self.lock)
```

### Comprehensive Configuration

We properly configure all aspects of the Greenflare crawler:

```python
# Update settings
self.settings['CUSTOM_CRAWL_DEPTH'] = self.max_depth
self.settings['CHECK_EXTERNAL_LINKS'] = self.check_external_links
self.settings['RESPECT_ROBOTS'] = self.respect_robots
self.settings['FOLLOW_REDIRECTS'] = True

# Configure extraction settings
if "title" in self.extract_meta_tags:
    self.settings['CRAWL_ITEMS'].append('page_title')
if "description" in self.extract_meta_tags:
    self.settings['CRAWL_ITEMS'].append('meta_description')
if "keywords" in self.extract_meta_tags:
    self.settings['CRAWL_ITEMS'].append('meta_keywords')
```

### Direct Database Access

We retrieve crawl data directly from the crawler's database:

```python
# Get the crawl data from the database
columns, data = self.official_crawler.get_crawl_data([], 'crawl')

# Convert the data to a list of dictionaries
for row in data:
    page_dict = {}
    for i, col in enumerate(columns):
        page_dict[col] = row[i]
    crawl_data.append(page_dict)
```

## Further Documentation

For more detailed information about the enhanced implementation, see [GREENFLARE_ENHANCEMENT.md](GREENFLARE_ENHANCEMENT.md). 