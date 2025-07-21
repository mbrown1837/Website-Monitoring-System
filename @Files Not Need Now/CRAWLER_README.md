# Website Crawler Module

The Website Crawler Module is an advanced feature of the Website Monitoring System that automatically scans websites for broken links and missing meta tags. This helps website owners maintain high-quality websites with good SEO and user experience.

## Features

### Broken Links Detection

The crawler automatically scans your websites to detect:

- Internal broken links (404 errors)
- External broken links to other websites
- Network errors and unreachable pages
- Redirects that may impact SEO

### Missing Meta Tags Detection

The crawler identifies pages with missing or incomplete meta tags:

- Missing page titles
- Missing meta descriptions
- Images without alt text (important for accessibility and SEO)

### Comprehensive Reporting

- Visual dashboard with summary statistics
- Detailed reports for each website
- Filtering and sorting capabilities
- Historical tracking of issues

## How to Use

### Viewing Crawler Results

1. **Dashboard**: The main dashboard shows summary statistics for all websites, including total broken links and missing meta tags.

2. **Website History**: The history page for each website now includes a "Crawler Results" column with links to detailed reports.

3. **Detailed Reports**: Click on "Details" in the crawler info column to view the full crawler report, which includes:
   - Summary statistics
   - List of all broken links with status codes
   - List of all pages with missing meta tags
   - Recommendations for fixes

### Configuring the Crawler

Configure crawler settings in the Settings page:

1. **Max Crawl Depth**: Controls how deep the crawler will follow links (higher values check more pages but take longer).

2. **Respect robots.txt**: When enabled, the crawler will respect the website's robots.txt file directives.

3. **Check External Links**: When enabled, the crawler will also check links to external websites.

4. **Crawler User Agent**: The user agent string the crawler will use to identify itself to websites.

## Technical Details

The crawler is built on the YiraBot library and is integrated into the Website Monitoring System's regular checks. It runs automatically whenever a website check is performed, either manually or on schedule.

### Requirements

- YiraBot library (version 1.0.9 or higher)
- SQLite database for storing crawler results
- Python 3.7 or higher

### Data Storage

Crawler results are stored in the following database tables:

- `crawl_sessions`: Records of each crawl session
- `broken_links`: Details of each broken link found
- `missing_meta_tags`: Details of each missing meta tag

## Troubleshooting

If you encounter issues with the crawler:

1. Check that the YiraBot library is installed correctly (`pip install yirabot>=1.0.9`)
2. Ensure the website is accessible and not blocking crawlers
3. Try reducing the crawl depth for very large websites
4. Check the application logs for detailed error messages

## Future Enhancements

Planned enhancements for the crawler module include:

- JavaScript rendering support for single-page applications
- Custom crawler rules and exclusions
- Performance optimization for large websites
- Integration with popular SEO tools
- Automated fix suggestions 