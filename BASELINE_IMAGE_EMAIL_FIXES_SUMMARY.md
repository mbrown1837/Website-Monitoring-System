# 🔧 Baseline Image & Email Template Fixes Summary

## 🎯 **Issues Fixed**

### **1. ❌ Baseline Images Not Showing (404 Errors)**
**Problem:** Baseline images were returning 404 errors because the route structure didn't match the file paths.

**Root Cause:**
- Route: `/snapshots/<site_id>/<type>/<filename>`
- Actual paths: `data/snapshots/westlanddre_com/d2c7b4e9-7073-4ea9-b363-fdac449c1a70/baseline/baseline_home.png`

**Solution:**
- Changed route to `/snapshots/<path:file_path>` to handle full file paths
- Updated route logic to properly serve files from the snapshot directory
- Maintained security checks for path traversal prevention

**Files Modified:**
- `src/app.py` - Updated `serve_snapshot()` function

### **2. ❌ Dashboard URL Hardcoded**
**Problem:** Dashboard URL was hardcoded to `http://167.86.123.94:5001` in production config.

**Solution:**
- Updated `config/config.production.yaml` to use environment variable
- Changed: `dashboard_url: http://167.86.123.94:5001`
- To: `dashboard_url: ${DASHBOARD_URL:-http://localhost:5001}`

**Files Modified:**
- `config/config.production.yaml`

### **3. ❌ Website ID in Email Templates**
**Problem:** Email templates were using `check_results.get('website_id')` which might not be the correct field.

**Solution:**
- Updated all email templates to use `check_results.get('site_id', check_results.get('website_id'))`
- This ensures compatibility with both field names
- Maintains backward compatibility

**Files Modified:**
- `src/alerter.py` - Updated all email template functions

## 🧪 **Testing**

Created comprehensive test script: `scripts/test_baseline_image_fix.py`

**Test Coverage:**
1. **Baseline Image Routes** - Tests the new `/snapshots/<path:file_path>` route
2. **Dashboard URL Configuration** - Verifies environment variable usage
3. **Email Template Website ID** - Confirms correct field usage

## 🚀 **Deployment Status**

✅ **All fixes committed and pushed to GitHub**
- Commit: `9d2387f`
- Message: "Fix baseline image serving and email template issues"

## 📋 **Expected Results After Deployment**

### **✅ Baseline Images**
- All baseline images should now display correctly on the history page
- No more 404 errors for baseline screenshots
- Proper file serving from `/snapshots/` route

### **✅ Dashboard URLs**
- Dashboard URLs in emails will use the `DASHBOARD_URL` environment variable
- Fallback to `http://localhost:5001` if not set
- Dynamic configuration for different environments

### **✅ Email Templates**
- Website IDs in email links will work correctly
- Uses `site_id` as primary field with `website_id` fallback
- All email notifications will have proper dashboard links

## 🔧 **Environment Variables Required**

Make sure these are set in your Dokploy deployment:

```bash
DASHBOARD_URL=http://167.86.123.94:5001
```

## 🎯 **Verification Steps**

1. **Check Baseline Images:**
   - Go to any website history page
   - Verify baseline images are displaying (not 404 errors)
   - Check browser network tab for successful image loads

2. **Check Email Links:**
   - Trigger a manual check
   - Check email notification
   - Verify dashboard links work correctly

3. **Check Dashboard URL:**
   - Verify emails show correct dashboard URL
   - Confirm links point to your Dokploy instance

## 📊 **Files Changed Summary**

| File | Changes | Impact |
|------|---------|--------|
| `src/app.py` | Updated snapshot serving route | Fixes 404 errors for baseline images |
| `config/config.production.yaml` | Made dashboard_url dynamic | Enables environment-based configuration |
| `src/alerter.py` | Fixed website ID field usage | Ensures proper email links |
| `scripts/test_baseline_image_fix.py` | New test script | Verifies all fixes work correctly |

## ✅ **Status: READY FOR DEPLOYMENT**

All fixes have been implemented, tested, and pushed to GitHub. The application should now properly display baseline images and send correctly formatted email notifications with proper dashboard links.

**Next Steps:**
1. Redeploy your Dokploy application
2. Verify baseline images are showing
3. Test email notifications
4. Import your 63 websites using the CSV file
