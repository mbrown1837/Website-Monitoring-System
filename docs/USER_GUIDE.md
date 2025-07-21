# Website Monitoring System - User Guide

## Overview
The Website Monitoring System is a comprehensive tool for monitoring website changes, performance, and content quality. It provides automated monitoring with visual change detection, blur detection, performance analysis, and content crawling.

## Features

### 1. Website Management
- **Add Websites**: Monitor multiple websites with customizable settings
- **Automated Monitoring**: Schedule periodic checks (hourly, daily, weekly)
- **Manual Checks**: Run immediate checks on demand
- **Website Settings**: Configure monitoring types per website

### 2. Monitoring Types

#### Content Crawling
- **Broken Links Detection**: Find and report broken internal/external links
- **Missing Meta Tags**: Identify pages without essential SEO meta tags
- **Site Structure Analysis**: Comprehensive crawl of website structure
- **Page Status Monitoring**: Track HTTP status codes and response times

#### Visual Change Detection
- **Screenshot Comparison**: Visual diff between current and baseline images
- **Percentage-based Changes**: Quantify visual changes with precision
- **Baseline Management**: Set and update visual baselines
- **Multi-page Monitoring**: Track changes across multiple pages

#### Blur Detection
- **Image Quality Analysis**: Detect blurry images using Laplacian analysis
- **Batch Processing**: Analyze multiple images simultaneously
- **Quality Scoring**: Numerical quality scores for each image
- **Local Storage**: Download and analyze images locally

#### Performance Monitoring
- **Google PageSpeed Integration**: Real-time performance metrics
- **Core Web Vitals**: LCP, FID, CLS measurements
- **Performance Scoring**: Overall performance ratings
- **Optimization Suggestions**: Actionable performance improvements

### 3. User Interface

#### Dashboard
- **Website Overview**: Quick status of all monitored websites
- **Recent Activity**: Latest monitoring results and changes
- **Quick Actions**: Manual check buttons for immediate testing
- **Statistics Cards**: Clickable summary cards with detailed results

#### Result Pages
- **Crawler Results**: Detailed crawl analysis with broken links and meta tags
- **Visual Changes**: Side-by-side comparison of visual changes
- **Blur Detection**: Grid/table view of image quality analysis
- **Performance Results**: Comprehensive performance metrics and recommendations

## Getting Started

### 1. Installation
```bash
# Install dependencies
pip install -r requirements.txt

# Configure settings
cp config/config.yaml.example config/config.yaml
```

### 2. Configuration
Edit `config/config.yaml`:
```yaml
# Google PageSpeed API key (optional)
google_pagespeed_api_key: "your_api_key_here"

# Email alerts (optional)
email:
  smtp_server: "smtp.gmail.com"
  smtp_port: 587
  username: "your_email@gmail.com"
  password: "your_password"

# Monitoring settings
monitoring:
  default_interval: 24  # hours
  max_crawl_depth: 3
  timeout: 30  # seconds
```

### 3. Adding Your First Website
```bash
# Using CLI
python main.py add-site "https://example.com" --name "My Website" --interval 24

# Using Web Interface
1. Open http://localhost:5001
2. Click "Add Website"
3. Fill in website details
4. Configure monitoring options
5. Click "Add Website"
```

### 4. Setting Baselines
```bash
# Set visual baseline for comparisons
python main.py set-baseline <website_id>
```

## Usage Guide

### Manual Monitoring
1. **Full Check**: Run all monitoring types
2. **Crawl Only**: Check for broken links and meta tags
3. **Visual Only**: Compare visual changes
4. **Blur Detection**: Analyze image quality
5. **Performance**: Check website performance

### Scheduled Monitoring
- Websites are automatically monitored based on their interval setting
- Results are stored in the database
- Email alerts are sent for significant changes (if configured)

### Viewing Results
1. **Dashboard**: Overview of all websites
2. **Website History**: Timeline of all checks for a website
3. **Detailed Results**: Click on any result card for detailed analysis
4. **Comparison Views**: Side-by-side comparisons for visual changes

## Advanced Features

### API Usage
```bash
# Manual check via API
curl -X POST "http://localhost:5001/website/<website_id>/manual_check" \
     -d "check_type=full"

# Get website status
curl "http://localhost:5001/api/website/<website_id>/status"
```

### Batch Operations
```bash
# Check all websites
python main.py check-all

# Export results
python main.py export-results --format csv --output results.csv
```

### Custom Monitoring
- **Custom Intervals**: Set specific monitoring frequencies
- **Selective Monitoring**: Enable/disable specific monitoring types
- **Custom Thresholds**: Set custom thresholds for alerts

## Troubleshooting

### Common Issues

#### 1. Database Errors
```bash
# Reset database
python main.py reset-database

# Backup database
cp data/website_monitor.db data/website_monitor.db.backup
```

#### 2. Screenshot Issues
- Ensure sufficient disk space in `data/snapshots/`
- Check write permissions on data directory
- Verify Chrome/Chromium is installed for screenshots

#### 3. Performance Check Failures
- Verify Google PageSpeed API key is valid
- Check internet connection
- Ensure website is publicly accessible

#### 4. Blur Detection Issues
- Verify images are accessible and not blocked
- Check image format support (JPEG, PNG, GIF, WebP)
- Ensure sufficient disk space for image downloads

### Error Messages

#### "No such table: performance_results"
- Database table missing, restart application to recreate

#### "Permission denied" on snapshots directory
- Fix permissions: `chmod 755 data/snapshots/`

#### "API key invalid" for performance checks
- Update Google PageSpeed API key in config.yaml

## Configuration Reference

### Website Settings
```yaml
# Per-website configuration
websites:
  - url: "https://example.com"
    name: "My Website"
    interval: 24  # hours
    enabled: true
    monitoring_types:
      crawl_enabled: true
      visual_enabled: true
      blur_enabled: false
      performance_enabled: true
```

### System Settings
```yaml
# Global system configuration
system:
  max_concurrent_checks: 3
  screenshot_timeout: 30
  crawl_timeout: 300
  image_quality_threshold: 100
  visual_change_threshold: 5.0
```

## Best Practices

### 1. Monitoring Strategy
- Start with daily monitoring for critical websites
- Use hourly monitoring only for high-priority sites
- Enable performance monitoring for user-facing sites
- Use blur detection for image-heavy websites

### 2. Baseline Management
- Set baselines after major website updates
- Review and update baselines monthly
- Use manual checks to verify baselines are current

### 3. Performance Optimization
- Monitor during off-peak hours to avoid server load
- Use selective monitoring to reduce resource usage
- Regular cleanup of old snapshots and results

### 4. Alert Configuration
- Set appropriate thresholds to avoid alert fatigue
- Configure email notifications for critical changes
- Use dashboard for routine monitoring

## Support

### Getting Help
1. Check the troubleshooting section above
2. Review log files in `data/monitoring.log`
3. Check database integrity with built-in tools
4. Review configuration files for syntax errors

### Log Files
- **Main Log**: `data/monitoring.log` - General application logs
- **Error Log**: `data/error.log` - Error-specific logs
- **Database Log**: Check SQLite integrity

### Reporting Issues
When reporting issues, include:
1. Error messages from logs
2. Configuration files (remove sensitive data)
3. Steps to reproduce the issue
4. System information and Python version

---

**Version**: 1.0
**Last Updated**: January 2025
**Documentation**: Complete user guide for website monitoring system 