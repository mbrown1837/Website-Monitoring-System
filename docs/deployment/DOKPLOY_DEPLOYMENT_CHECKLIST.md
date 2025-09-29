# 🚀 Dokploy Deployment Checklist

## ✅ **Pre-Deployment Setup**

### **1. Environment Variables in Dokploy**
Make sure these are set in your Dokploy dashboard:

```bash
DASHBOARD_URL=http://167.86.123.94:5001
SECRET_KEY=website-monitor-secret-key-2024-3016d3d1d5f59d6a8b2121508dfdc174
SCHEDULER_ENABLED=true
LOG_LEVEL=INFO
TZ=UTC
```

### **2. Repository Connection**
- ✅ Repository: `https://github.com/mbrown1837/Website-Monitoring-System.git`
- ✅ Branch: `main`
- ✅ Dockerfile: `Dockerfile` (in root directory)

## 🔄 **Deployment Steps**

### **Step 1: Deploy/Redeploy in Dokploy**
1. Go to your Dokploy dashboard: `http://167.86.123.94:3000`
2. Find your `website-monitor` project
3. Click **"Deploy"** or **"Redeploy"** to pull the latest changes
4. Wait for deployment to complete (usually 2-3 minutes)

### **Step 2: Verify Deployment**
1. Check if the app is running: `http://167.86.123.94:5001`
2. Look for the health dashboard
3. Check logs for any errors

## 🧪 **Testing Checklist**

### **1. Basic Functionality**
- [ ] **Dashboard loads**: `http://167.86.123.94:5001`
- [ ] **Health dashboard works**: `http://167.86.123.94:5001/health`
- [ ] **Website list loads**: `http://167.86.123.94:5001/`
- [ ] **No critical errors** in logs

### **2. Baseline Images**
- [ ] **Baseline images display** in history page
- [ ] **Visual comparisons work** (before/after images)
- [ ] **No "No baseline found" warnings** in logs

### **3. Email Notifications**
- [ ] **Email URLs are correct**: Should show `http://167.86.123.94:5001/website/history/...`
- [ ] **No old Coolify domain** in email links
- [ ] **Email links work** when clicked

### **4. Scheduler**
- [ ] **Scheduler is running** (check logs for "SCHEDULER: Starting website monitoring scheduler")
- [ ] **Websites are being monitored** automatically
- [ ] **No "No websites found" errors**

### **5. Database**
- [ ] **SQLite database is working** (no connection errors)
- [ ] **Website data is loaded** from database
- [ ] **Check history is being recorded**

## 🔍 **Diagnostic Commands**

### **Test Environment Variables**
Run this in your Dokploy container to verify environment variables:

```bash
python scripts/test_env_in_dokploy.py
```

### **Check Email URLs**
Run this to test email URL generation:

```bash
python scripts/test_email_urls.py
```

### **Verify Environment**
Run this to check all environment settings:

```bash
python scripts/verify_env.py
```

## 🐛 **Common Issues & Solutions**

### **Issue: Email URLs still show old domain**
**Solution**: 
1. Restart the application in Dokploy
2. Verify `DASHBOARD_URL` environment variable is set correctly
3. Run `python scripts/test_env_in_dokploy.py` to verify

### **Issue: Baseline images not showing**
**Solution**:
1. Check if baseline images exist in `/app/data/snapshots/`
2. Look for "No baseline found" warnings in logs
3. Trigger a manual website check to create baselines

### **Issue: Scheduler not finding websites**
**Solution**:
1. Check database connection in logs
2. Verify websites are loaded: `SCHEDULER: Loaded X websites from database`
3. Check if websites are marked as active

### **Issue: PageSpeed API errors**
**Solution**:
1. Check logs for "PageSpeed API request failed"
2. Verify URLs are valid (not localhost/test domains)
3. Check Google PageSpeed API quota

## 📊 **Monitoring**

### **Key Log Messages to Watch For**
- ✅ `SCHEDULER: Starting website monitoring scheduler`
- ✅ `SCHEDULER: Loaded X websites from database`
- ✅ `Using dashboard URL: http://167.86.123.94:5001`
- ❌ `No baseline found for URL`
- ❌ `UNIQUE constraint failed`
- ❌ `PageSpeed API request failed`

### **Health Check Endpoints**
- **Main Dashboard**: `http://167.86.123.94:5001`
- **Health Status**: `http://167.86.123.94:5001/health`
- **Queue Status**: `http://167.86.123.94:5001/queue`

## 🎯 **Success Criteria**

Your deployment is successful when:
1. ✅ Dashboard loads without errors
2. ✅ Baseline images display correctly
3. ✅ Email notifications show correct URLs
4. ✅ Scheduler is monitoring websites automatically
5. ✅ No critical errors in logs
6. ✅ All health checks pass

## 📞 **Need Help?**

If you encounter any issues:
1. Check the logs in Dokploy dashboard
2. Run the diagnostic scripts
3. Verify environment variables
4. Check this checklist for common solutions

---

**Last Updated**: $(date)
**Version**: Latest (commit 19aed04)
**Environment**: Dokploy on Ubuntu VPS
