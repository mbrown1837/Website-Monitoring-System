# Website Monitoring System - Troubleshooting Guide

## Common Issues and Solutions

### Database Errors

#### Issue: "No such table: performance_results"
**Cause**: Database table not initialized properly
**Solution**:
```bash
# Stop the application
# Delete and recreate the database
rm data/website_monitor.db
python main.py  # This will recreate the database
```

#### Issue: "Database is locked"
**Cause**: Multiple processes accessing the database
**Solution**:
```bash
# Kill all Python processes
pkill -f "python.*app.py"
# Restart the application
python src/app.py
```

### Template Errors

#### Issue: "TypeError: '<' not supported between instances of 'NoneType' and 'int'"
**Cause**: Template trying to compare None values
**Solution**: This has been fixed in the latest version. Update your templates.

#### Issue: "TemplateNotFound: blur_detection_results.html"
**Cause**: Missing template file
**Solution**: Ensure all template files exist in the templates directory.

### Performance Issues

#### Issue: Google PageSpeed API not working
**Cause**: Missing or invalid API key
**Solution**:
1. Get API key from Google Cloud Console
2. Update config.yaml with valid key
3. Restart application

#### Issue: "API quota exceeded"
**Cause**: Too many API calls
**Solution**: 
- Reduce monitoring frequency
- Use performance checks sparingly
- Consider API quota limits

### Visual Change Detection Issues

#### Issue: Screenshots not being captured
**Cause**: Missing Chrome/Chromium or permissions
**Solution**:
```bash
# Install Chrome (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install google-chrome-stable

# Or install Chromium
sudo apt-get install chromium-browser
```

#### Issue: "Permission denied" on snapshots directory
**Cause**: Insufficient permissions
**Solution**:
```bash
chmod 755 data/snapshots/
chown -R $USER:$USER data/
```

### Blur Detection Issues

#### Issue: Images not being downloaded
**Cause**: Network issues or blocked images
**Solution**:
- Check internet connection
- Verify images are publicly accessible
- Check for content blocking (robots.txt, etc.)

#### Issue: "Out of memory" during image processing
**Cause**: Large images or insufficient RAM
**Solution**:
- Reduce image processing batch size
- Increase system memory
- Use image resizing options

### Crawling Issues

#### Issue: Crawler not finding pages
**Cause**: Website blocking crawlers or JavaScript-heavy site
**Solution**:
- Check robots.txt file
- Ensure website allows crawling
- For JavaScript sites, consider using JavaScript-enabled crawler

#### Issue: "Timeout during crawl"
**Cause**: Slow website or network issues
**Solution**:
- Increase timeout in config
- Check website performance
- Verify network connectivity

### Scheduler Issues

#### Issue: Scheduled checks not running
**Cause**: Scheduler not properly initialized
**Solution**:
```bash
# Check if scheduler is running
ps aux | grep python
# Restart with scheduler
python main.py --enable-scheduler
```

### Configuration Issues

#### Issue: Config file not found
**Cause**: Missing config.yaml
**Solution**:
```bash
# Create default config
cp config/config.yaml.example config/config.yaml
# Edit with your settings
nano config/config.yaml
```

#### Issue: Invalid YAML syntax
**Cause**: Syntax errors in config file
**Solution**:
- Use YAML validator
- Check indentation (use spaces, not tabs)
- Ensure proper quoting of strings

### Memory and Performance Issues

#### Issue: High memory usage
**Cause**: Large images or too many concurrent operations
**Solution**:
- Reduce concurrent checks
- Implement image compression
- Regular cleanup of old files

#### Issue: Application running slowly
**Cause**: Database queries or large datasets
**Solution**:
- Optimize database queries
- Implement pagination
- Clean up old data regularly

### Network Issues

#### Issue: Connection timeouts
**Cause**: Slow or unreliable network
**Solution**:
- Increase timeout values
- Implement retry logic
- Check network stability

#### Issue: SSL certificate errors
**Cause**: Invalid or expired certificates
**Solution**:
- Update certificate store
- Add SSL verification options
- Use proper SSL context

## Debugging Steps

### 1. Check Logs
```bash
# View recent logs
tail -f data/monitoring.log

# Check for errors
grep -i error data/monitoring.log
```

### 2. Test Database
```bash
# Check database integrity
python -c "
import sqlite3
conn = sqlite3.connect('data/website_monitor.db')
cursor = conn.cursor()
cursor.execute('PRAGMA integrity_check')
print(cursor.fetchone())
conn.close()
"
```

### 3. Test Configuration
```bash
# Validate config
python -c "
import yaml
with open('config/config.yaml') as f:
    config = yaml.safe_load(f)
print('Config valid:', config is not None)
"
```

### 4. Test API Endpoints
```bash
# Test website status
curl -X GET "http://localhost:5001/api/websites"

# Test manual check
curl -X POST "http://localhost:5001/website/<id>/manual_check" \
     -d "check_type=crawl"
```

## Performance Optimization

### Database Optimization
```sql
-- Clean up old data
DELETE FROM crawl_results WHERE timestamp < datetime('now', '-30 days');
DELETE FROM visual_changes WHERE timestamp < datetime('now', '-30 days');
DELETE FROM blur_detection_results WHERE timestamp < datetime('now', '-30 days');

-- Reindex database
REINDEX;
VACUUM;
```

### File System Cleanup
```bash
# Remove old snapshots (older than 30 days)
find data/snapshots -name "*.png" -mtime +30 -delete
find data/snapshots -name "*.jpg" -mtime +30 -delete

# Clean up temporary files
rm -rf data/tmp/*
```

### Memory Management
```bash
# Monitor memory usage
top -p $(pgrep -f "python.*app.py")

# If memory is high, restart periodically
# Add to crontab for daily restart
0 2 * * * /path/to/restart_script.sh
```

## Recovery Procedures

### Complete Reset
```bash
# Backup current data
cp -r data/ data_backup_$(date +%Y%m%d)/

# Reset database
rm data/website_monitor.db

# Clear snapshots
rm -rf data/snapshots/*

# Restart application
python src/app.py
```

### Partial Reset
```bash
# Reset specific website data
python main.py reset-website <website_id>

# Reset specific monitoring type
python main.py reset-monitoring-type blur_detection
```

## Monitoring Health

### System Health Checks
```bash
# Check disk space
df -h data/

# Check database size
ls -lh data/website_monitor.db

# Check active processes
ps aux | grep python
```

### Application Health
```bash
# Test all endpoints
curl -s http://localhost:5001/health

# Check recent activity
python main.py status --verbose
```

## Getting Help

### Log Analysis
When reporting issues, include:
1. Relevant log entries from `data/monitoring.log`
2. Configuration file (remove sensitive data)
3. Steps to reproduce the issue
4. System information

### Common Log Patterns
```bash
# Find errors
grep -i "error\|exception\|traceback" data/monitoring.log

# Find warnings
grep -i "warning\|warn" data/monitoring.log

# Find database issues
grep -i "database\|sqlite\|sql" data/monitoring.log
```

---

**Last Updated**: January 2025
**Version**: 1.0
**Status**: Complete troubleshooting guide 