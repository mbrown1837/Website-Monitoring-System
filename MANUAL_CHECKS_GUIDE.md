# 🔧 Manual Checks System Guide

## ✅ **System Verified & Production Ready**

The manual checks system has been thoroughly tested and verified to work correctly:

- ✅ **Individual check buttons** - Each performs only its respective check
- ✅ **Baseline creation** - Respects global exclude keywords
- ✅ **Queue system integration** - Properly manages check requests
- ✅ **JavaScript functionality** - All buttons work correctly

## 🎯 **Manual Check Buttons**

### **Available Check Types:**

| Button | Check Type | What It Does | Configuration |
|--------|------------|--------------|---------------|
| **Full Check** | `full` | All checks enabled | `crawl: ✅, visual: ✅, blur: ✅, performance: ✅` |
| **Visual Check** | `visual` | Visual comparison only | `crawl: ❌, visual: ✅, blur: ❌, performance: ❌` |
| **Crawl Check** | `crawl` | Website crawling only | `crawl: ✅, visual: ❌, blur: ❌, performance: ❌` |
| **Blur Check** | `blur` | Blur detection only | `crawl: ❌, visual: ❌, blur: ✅, performance: ❌` |
| **Performance Check** | `performance` | PageSpeed analysis only | `crawl: ❌, visual: ❌, blur: ❌, performance: ✅` |
| **Create Baseline** | `baseline` | Baseline creation only | `crawl: ❌, visual: ✅, blur: ❌, performance: ❌` |

### **How Each Check Works:**

#### **1. Visual Check Only (`visual`)**
- **Skips crawling** - Only processes the main URL
- **Creates snapshots** - Takes visual screenshots
- **Compares with baseline** - If baseline exists
- **Sends email notification** - Reports visual differences

#### **2. Crawl Check Only (`crawl`)**
- **Crawls website** - Discovers all internal pages
- **Checks links** - Identifies broken links
- **Analyzes meta tags** - Finds missing meta information
- **Sends email notification** - Reports crawl results

#### **3. Blur Check Only (`blur`)**
- **Uses existing crawl data** - If available
- **Analyzes images** - Detects blurry images
- **Processes main page** - If no crawl data exists
- **Sends email notification** - Reports blur detection results

#### **4. Performance Check Only (`performance`)**
- **Validates URL** - Ensures URL is suitable for PageSpeed API
- **Calls PageSpeed API** - Gets performance metrics
- **Analyzes results** - Identifies performance issues
- **Sends email notification** - Reports performance data

#### **5. Baseline Creation (`baseline`)**
- **Crawls website** - Discovers internal pages
- **Respects exclude keywords** - Skips excluded pages
- **Creates visual snapshots** - Captures baseline images
- **Saves to database** - Stores baseline information
- **Sends email notification** - Confirms baseline creation

## 🚫 **Global Exclude Keywords**

### **Default Excluded Keywords:**
```yaml
exclude_pages_keywords:
  - products
  - blogs
  - blog
  - product
  - shop
  - store
  - cart
  - checkout
  - account
  - login
  - register
  - search
  - category
  - tag
  - archive
```

### **How Exclusion Works:**

#### **For Baseline Creation:**
- **URLs containing exclude keywords** are skipped
- **Case-insensitive matching** - `Products`, `PRODUCTS`, `products` all excluded
- **Partial matching** - `/products/item1` is excluded
- **Per-site overrides** - Website-specific exclude keywords take precedence

#### **Example URL Filtering:**
```
✅ INCLUDED:
- https://example.com/
- https://example.com/about
- https://example.com/contact
- https://example.com/admin

❌ EXCLUDED:
- https://example.com/products
- https://example.com/blogs
- https://example.com/blog
- https://example.com/product
- https://example.com/products/item1
- https://example.com/blogs/post1
- https://example.com/login
```

## 🔄 **Queue System Integration**

### **How Manual Checks Are Processed:**

1. **Button Click** - User clicks a manual check button
2. **AJAX Request** - JavaScript sends request to backend
3. **Queue Addition** - Check is added to manual check queue
4. **Status Response** - Queue ID and status returned
5. **Background Processing** - Queue processor handles the check
6. **Email Notification** - Results sent via email

### **Queue Management:**

- **Duplicate Prevention** - Same check type for same website prevented
- **Sequential Processing** - One check at a time per website
- **Status Tracking** - Real-time status updates
- **Error Handling** - Graceful failure handling

## 🎨 **Frontend Implementation**

### **JavaScript Button Handlers:**

```javascript
// Button element selection
const visualCheckBtn = document.getElementById('visualCheckBtn');
const crawlCheckBtn = document.getElementById('crawlCheckBtn');
const blurCheckBtn = document.getElementById('blurCheckBtn');
const performanceCheckBtn = document.getElementById('performanceCheckBtn');
const createBaselineBtn = document.getElementById('createBaselineBtn');

// Event listeners for each button
visualCheckBtn.addEventListener('click', function() {
    // Send AJAX request with check_type=visual
    fetch('/manual-check-website', {
        method: 'POST',
        body: 'check_type=visual'
    });
});
```

### **Button States:**

- **Loading State** - Shows spinner and disables button
- **Success State** - Shows success message
- **Error State** - Shows error message and re-enables button
- **Auto Reset** - Button resets after 3 seconds

## 🔧 **Backend Configuration**

### **Manual Check Configuration:**

```python
def get_manual_check_config(self, website_id, check_type):
    base_configs = {
        'full': {'crawl_enabled': True, 'visual_enabled': True, 'blur_enabled': True, 'performance_enabled': True},
        'visual': {'crawl_enabled': False, 'visual_enabled': True, 'blur_enabled': False, 'performance_enabled': False},
        'crawl': {'crawl_enabled': True, 'visual_enabled': False, 'blur_enabled': False, 'performance_enabled': False},
        'blur': {'crawl_enabled': False, 'visual_enabled': False, 'blur_enabled': True, 'performance_enabled': False},
        'performance': {'crawl_enabled': False, 'visual_enabled': False, 'blur_enabled': False, 'performance_enabled': True},
        'baseline': {'crawl_enabled': False, 'visual_enabled': True, 'blur_enabled': False, 'performance_enabled': False}
    }
    return base_configs.get(check_type, base_configs['full'])
```

### **URL Exclusion Logic:**

```python
def _should_exclude_url_for_checks(self, url: str, check_type: str = "all", website_id: str = None) -> bool:
    # Get exclude keywords (per-site or global)
    exclude_keywords = self.config.get('exclude_pages_keywords', ['products', 'blogs', 'blog', 'product'])
    
    # Check if URL contains any exclude keywords
    url_lower = url.lower()
    for keyword in exclude_keywords:
        if keyword.lower() in url_lower:
            return True
    return False
```

## 📧 **Email Notifications**

### **Individual Check Emails:**

Each manual check type sends its own specific email:

- **Visual Check** - Visual comparison results
- **Crawl Check** - Broken links and meta tag analysis
- **Blur Check** - Blur detection results
- **Performance Check** - PageSpeed metrics
- **Baseline Creation** - Baseline creation confirmation

### **Email Content:**

- **Check-specific results** - Only relevant data for that check type
- **Website information** - Name, URL, timestamp
- **Action buttons** - Links to dashboard and history
- **Error handling** - Clear error messages if checks fail

## 🧪 **Testing**

### **Test Script:**

```bash
python scripts/test_manual_checks.py
```

This script tests:
- ✅ Manual check configurations
- ✅ Global exclude keywords functionality
- ✅ Queue processor integration
- ✅ Individual check type isolation

### **Manual Testing:**

1. **Navigate to history page** - `/website/history/<site_id>`
2. **Click individual buttons** - Test each check type
3. **Verify queue status** - Check queue processing
4. **Check email notifications** - Verify emails are sent
5. **Test baseline creation** - Verify exclude keywords work

## 🚀 **Production Deployment**

### **Dokploy Configuration:**

The manual checks system is ready for Dokploy deployment:

- ✅ **JavaScript functionality** - All buttons work correctly
- ✅ **Backend processing** - Queue system handles requests
- ✅ **Email notifications** - SMTP configuration supported
- ✅ **Database integration** - All data properly stored
- ✅ **Error handling** - Graceful failure management

### **Environment Variables:**

```bash
# Email configuration for notifications
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
NOTIFICATION_EMAIL_FROM=your-email@gmail.com

# Dashboard URL for email links
DASHBOARD_URL=http://167.86.123.94:5001
```

## 📊 **Monitoring & Logs**

### **Log Messages:**

```
✅ Visual check initiated for website: Example Site
✅ Crawl check queued successfully (ID: abc123)
✅ Blur detection completed: 3 blurry images found
✅ Performance check completed: Score 85/100
✅ Baseline created for 5 pages (excluded 3 pages)
```

### **Queue Status:**

- **Pending** - Check waiting in queue
- **Processing** - Check currently running
- **Completed** - Check finished successfully
- **Failed** - Check encountered error

## 🎉 **Summary**

The manual checks system provides:

- ✅ **Individual check isolation** - Each button does only its specific check
- ✅ **Global exclude keywords** - Baseline creation respects exclusions
- ✅ **Queue system integration** - Proper request management
- ✅ **Email notifications** - Check-specific email reports
- ✅ **Production readiness** - Fully tested and verified

**The system ensures that manual checks are precise, efficient, and respect global configuration settings while providing clear feedback to users through email notifications.** 🚀
