# 🔄 Website Deletion Synchronization Guide

## ✅ **Synchronization System Verified**

The website deletion synchronization system has been tested and verified to work correctly across all components:

- ✅ **Database cleanup** - All related records removed
- ✅ **Snapshot cleanup** - All files and directories removed  
- ✅ **Scheduler cleanup** - Scheduled tasks removed
- ✅ **Cache cleanup** - Memory cache cleared
- ✅ **JSON sync** - JSON file updated

## 🏗️ **How Synchronization Works**

### **When a Website is Deleted:**

1. **Website Manager** (`remove_website()` method) orchestrates the complete cleanup
2. **Database Cleanup** (`_cleanup_website_database_records()`) removes all related records
3. **Snapshot Cleanup** (`_cleanup_website_snapshots()`) removes all files and directories
4. **Scheduler Cleanup** (`_cleanup_website_scheduler_task()`) removes scheduled tasks
5. **Cache Cleanup** - Removes website from memory cache
6. **JSON Sync** (`_sync_json_file()`) updates the JSON file

### **Database Tables Cleaned:**

| Table | Column | Purpose |
|-------|--------|---------|
| `check_history` | `site_id` | Check history records |
| `crawl_history` | `site_id` | Crawl history records |
| `crawl_results` | `site_id` | Crawl result data |
| `broken_links` | `site_id` | Broken link reports |
| `missing_meta_tags` | `site_id` | Missing meta tag reports |
| `manual_check_queue` | `website_id` | Manual check queue items |
| `scheduler_log` | `website_id` | Scheduler log entries |
| `scheduler_metrics` | `website_id` | Scheduler performance metrics |
| `blur_detection_results` | `site_id` | Blur detection results |
| `performance_results` | `site_id` | Performance check results |

### **File System Cleanup:**

- **Snapshot directories** - All website-specific snapshot folders
- **Baseline images** - All baseline images for the website
- **Visual snapshots** - All visual comparison snapshots
- **Blur images** - All blur detection images
- **Empty directories** - Removes empty parent directories

### **Scheduler Integration:**

- **Task removal** - Removes scheduled monitoring tasks
- **Job cleanup** - Cancels pending scheduled jobs
- **Status update** - Updates scheduler status and metrics

## 🚀 **Usage Examples**

### **Web Interface:**
```python
# Via Flask route
@app.route('/website/remove/<site_id>', methods=['POST'])
def remove_website(site_id):
    website_manager.remove_website(site_id)
    # All synchronization happens automatically
```

### **Command Line:**
```bash
# Via CLI
python -m src.cli remove-site <site_id>

# Or directly
python -c "from src.website_manager_sqlite import WebsiteManager; WebsiteManager().remove_website('site_id')"
```

### **Programmatic:**
```python
from src.website_manager_sqlite import WebsiteManager

website_manager = WebsiteManager()
success = website_manager.remove_website(website_id)

if success:
    print("✅ Website and all associated data removed successfully")
else:
    print("❌ Website removal failed")
```

## 🔍 **Verification Methods**

### **Test Script:**
```bash
python scripts/test_website_deletion_sync.py
```

This script tests:
- Single website deletion
- Bulk deletion
- Database cleanup verification
- File system cleanup verification
- Scheduler cleanup verification

### **Manual Verification:**

1. **Check Database:**
   ```sql
   SELECT * FROM websites WHERE id = 'website_id';
   -- Should return no results
   ```

2. **Check Snapshot Directory:**
   ```bash
   ls data/snapshots/
   # Should not contain website-specific directories
   ```

3. **Check Scheduler:**
   ```python
   from src.scheduler_integration import get_scheduler_manager
   manager = get_scheduler_manager()
   # Check if website tasks are removed
   ```

## 📊 **Synchronization Status**

### **✅ Working Components:**

- **Database Records** - All related records removed
- **Snapshot Files** - All files and directories removed
- **Scheduler Tasks** - All scheduled tasks removed
- **Memory Cache** - Website removed from cache
- **JSON File** - Updated to reflect current state

### **⚠️ Notes:**

- **Scheduler Status Table** - Doesn't have website_id column (by design)
- **Empty Directories** - Automatically cleaned up
- **Concurrent Access** - Thread-safe operations
- **Error Handling** - Continues cleanup even if some steps fail

## 🛡️ **Safety Features**

### **Comprehensive Logging:**
```
Starting comprehensive cleanup for website: Example Site (https://example.com)
Database cleanup completed: 15 total records deleted
Snapshot cleanup completed: 3 directories, 45 files deleted
Removed scheduler task for website abc123
Synced JSON file with 4 websites
Website cleanup completed for Example Site:
  - Database records: ✅
  - Snapshot files: ✅
  - Scheduler task: ✅
  - JSON file sync: ✅
Successfully removed website Example Site and all associated data
```

### **Error Handling:**
- **Individual table failures** don't stop the entire process
- **File system errors** are logged but don't prevent database cleanup
- **Scheduler errors** are logged but don't prevent other cleanup
- **Partial failures** are reported in the final status

### **Rollback Safety:**
- **Database transactions** ensure atomicity
- **File operations** are logged for manual recovery if needed
- **Scheduler state** is updated to reflect current status

## 🎯 **Best Practices**

### **Before Deletion:**
1. **Backup important data** if needed
2. **Verify website ID** is correct
3. **Check for active monitoring** tasks
4. **Review snapshot data** if preservation needed

### **After Deletion:**
1. **Verify cleanup** using test script
2. **Check logs** for any errors
3. **Confirm scheduler** status is updated
4. **Test system** continues working normally

### **Bulk Deletions:**
1. **Use test script** for bulk cleanup
2. **Monitor logs** during bulk operations
3. **Verify disk space** is freed up
4. **Check scheduler** performance after bulk cleanup

## 🚨 **Troubleshooting**

### **Common Issues:**

1. **Database Lock Errors:**
   - Ensure no other processes are accessing the database
   - Check for long-running queries
   - Restart application if needed

2. **File Permission Errors:**
   - Check file system permissions
   - Ensure application has write access
   - Check for locked files

3. **Scheduler Errors:**
   - Verify scheduler is running
   - Check scheduler configuration
   - Review scheduler logs

### **Recovery:**

If deletion fails partially:
1. **Check logs** for specific error messages
2. **Manually clean** remaining data if needed
3. **Restart application** to clear any locks
4. **Re-run deletion** if safe to do so

## 🎉 **Summary**

The website deletion synchronization system is **production-ready** and provides:

- ✅ **Complete cleanup** of all website data
- ✅ **Thread-safe operations** for concurrent access
- ✅ **Comprehensive logging** for debugging
- ✅ **Error handling** with graceful degradation
- ✅ **Automatic synchronization** across all components

**The system ensures that when a website is deleted, it's completely removed from the entire application with no orphaned data remaining.** 🚀
