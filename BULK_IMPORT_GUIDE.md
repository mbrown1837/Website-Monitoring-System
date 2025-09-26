# 📥 Bulk Import Guide for Dokploy Deployment

## ✅ **Bulk Import Verification Complete**

The bulk import functionality has been tested and verified to work correctly with:
- ✅ **24-hour check intervals** (1440 minutes)
- ✅ **Baseline creation** (via auto_full_check_enabled)
- ✅ **Full check types** (crawl, visual, blur, performance)
- ✅ **Queue system** for proper sequential processing
- ✅ **Concurrency control** (0.5 second delays)

## 🚀 **How to Use Bulk Import**

### **Option 1: Web Interface (Recommended)**
1. **Deploy to Dokploy** with the latest code
2. **Navigate to** `http://your-dokploy-ip:5001/bulk-import`
3. **Upload CSV file** using the web form
4. **Sites will be imported** with automatic baseline creation

### **Option 2: Command Line Script**
```bash
python scripts/bulk_website_import_improved.py --csv your-sites.csv
```

## 📋 **CSV Format**

Create a CSV file with these columns:

```csv
name,url,monitoring_interval,max_depth,enable_crawl,enable_visual,enable_blur_detection,enable_performance,exclude_pages_keywords
My Website 1,https://example1.com,86400,2,true,true,true,true,
My Website 2,https://example2.com,86400,2,true,true,true,true,
My Website 3,https://example3.com,86400,2,true,true,true,true,
```

### **Column Descriptions:**
- **`name`** - Website name (required)
- **`url`** - Website URL (required)
- **`monitoring_interval`** - Check interval in seconds (86400 = 24 hours)
- **`max_depth`** - Crawl depth (2 recommended)
- **`enable_crawl`** - Enable crawl checks (true/false)
- **`enable_visual`** - Enable visual checks (true/false)
- **`enable_blur_detection`** - Enable blur detection (true/false)
- **`enable_performance`** - Enable performance checks (true/false)
- **`exclude_pages_keywords`** - Keywords to exclude (comma-separated, optional)

## 🎯 **What Happens During Import**

### **For Each Website:**
1. ✅ **Website added** to database with 24-hour interval
2. ✅ **All check types enabled** (crawl, visual, blur, performance)
3. ✅ **Baseline creation queued** automatically
4. ✅ **Full check scheduled** for immediate execution
5. ✅ **Email notifications** configured (if SMTP working)

### **Timeline:**
- **Immediate**: Baseline creation starts via queue system
- **24 hours later**: First scheduled check runs
- **Every 24 hours**: Regular monitoring continues

## 📊 **Sample CSV Files**

### **Basic Import (All Defaults)**
```csv
name,url
Site 1,https://example1.com
Site 2,https://example2.com
Site 3,https://example3.com
```

### **Advanced Import (Custom Settings)**
```csv
name,url,monitoring_interval,max_depth,enable_crawl,enable_visual,enable_blur_detection,enable_performance,exclude_pages_keywords
E-commerce Site,https://shop.example.com,86400,3,true,true,true,true,cart,checkout,login
Blog Site,https://blog.example.com,43200,2,true,true,false,true,admin,wp-admin
Portfolio Site,https://portfolio.example.com,86400,1,false,true,true,false,
```

## 🔧 **Configuration Details**

### **Default Settings Applied:**
- **Check Interval**: 24 hours (1440 minutes)
- **Crawl Depth**: 2 levels
- **Visual Threshold**: 5% difference
- **Render Delay**: 6 seconds
- **All Check Types**: Enabled
- **Baseline Creation**: Automatic
- **Queue Processing**: Sequential (respects concurrency limits)

### **Concurrency Control:**
- **0.5 second delay** between website imports
- **Queue system** handles baseline creation
- **One site at a time** processing
- **No conflicts** with existing monitoring

## 🚨 **Important Notes**

### **Before Import:**
1. **Ensure SMTP is configured** for email notifications
2. **Check Dokploy environment variables** are set
3. **Verify disk space** for snapshots
4. **Test with small CSV** first

### **After Import:**
1. **Check queue status** in the dashboard
2. **Monitor baseline creation** progress
3. **Verify 24-hour scheduling** is working
4. **Test email notifications** are being sent

## 🎉 **Expected Results**

After bulk import:
- ✅ **All websites** added to monitoring
- ✅ **Baselines created** automatically
- ✅ **24-hour schedule** established
- ✅ **Email notifications** working (if SMTP configured)
- ✅ **Dashboard shows** all imported sites
- ✅ **Next day**: First scheduled checks run

## 🔍 **Troubleshooting**

### **Import Fails:**
- Check CSV format and required columns
- Verify URLs are valid and accessible
- Check disk space for snapshots
- Review logs for specific errors

### **Baselines Not Created:**
- Check queue processor is running
- Verify website manager permissions
- Check snapshot directory exists
- Review crawler module logs

### **Scheduling Issues:**
- Verify scheduler is enabled
- Check website is_active status
- Review scheduler logs
- Confirm 24-hour interval is set

## 📝 **Quick Start for Dokploy**

1. **Create CSV file** with your websites
2. **Deploy to Dokploy** with latest code
3. **Set SMTP environment variables** (Gmail recommended)
4. **Navigate to** `/bulk-import` page
5. **Upload CSV** and wait for import
6. **Check dashboard** for imported sites
7. **Wait 24 hours** for first scheduled checks

The bulk import system is ready for production use! 🚀
