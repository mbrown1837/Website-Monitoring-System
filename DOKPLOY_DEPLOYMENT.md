# 🚀 Dokploy Deployment Guide

## Prerequisites
- ✅ Dokploy installed on your VPS
- ✅ Your Website Monitoring app code ready
- ✅ VPS with Docker support

## Step-by-Step Deployment

### 1. **Access Dokploy Dashboard**
```bash
# Open your browser and go to:
http://your-vps-ip:3000
```

### 2. **Create New Project**
1. Click **"New Project"** in Dokploy dashboard
2. Enter project name: `website-monitor`
3. Choose **"Docker Compose"** as deployment type

### 3. **Upload Your Code**
**Option A: Git Repository (Recommended)**
1. Push your code to GitHub/GitLab
2. In Dokploy, select **"Git Source"**
3. Enter your repository URL
4. Select branch: `main` or `master`

**Option B: Direct Upload**
1. Create a ZIP file of your project
2. Upload via Dokploy's file upload feature

### 4. **Configure Environment Variables**
In Dokploy dashboard, add these environment variables:

```bash
# Required Environment Variables
DASHBOARD_URL=http://your-domain.com
SECRET_KEY=your-secret-key-here
SCHEDULER_ENABLED=true
LOG_LEVEL=INFO
TZ=UTC

# Email Configuration (Optional)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=your-email@gmail.com
```

### 5. **Configure Docker Compose**
1. In Dokploy, select **"Docker Compose"** tab
2. Use the provided `dokploy.yml` configuration
3. Or copy the content from the file I created

### 6. **Set Up Domain (Optional)**
1. In Dokploy, go to **"Domains"** section
2. Add your domain: `monitor.yourdomain.com`
3. Dokploy will automatically configure SSL with Let's Encrypt

### 7. **Deploy**
1. Click **"Deploy"** button
2. Wait for the build process to complete
3. Check logs for any errors

## 🔧 **Post-Deployment Configuration**

### **Access Your App**
- **Dashboard**: `http://your-vps-ip:5001` or `https://your-domain.com`
- **Health Check**: `http://your-vps-ip:5001/health`

### **Verify Scheduler is Working**
1. Go to your app dashboard
2. Check the "Queue" page
3. You should see scheduled tasks for your websites

### **Monitor Logs**
1. In Dokploy dashboard, go to **"Logs"**
2. Check for any errors or warnings
3. Look for "SCHEDULER: Loaded X websites" message

## 🛠️ **Troubleshooting**

### **Common Issues**

**1. Scheduler Not Starting**
```bash
# Check if SCHEDULER_ENABLED=true in environment variables
# Verify database is accessible
```

**2. Database Connection Issues**
```bash
# Ensure data volume is properly mounted
# Check database file permissions
```

**3. Email Not Working**
```bash
# Verify SMTP credentials
# Check firewall settings for port 587
```

### **Useful Commands**
```bash
# Check container status
docker ps

# View logs
docker logs website-monitor

# Access container shell
docker exec -it website-monitor bash
```

## 📊 **Monitoring & Maintenance**

### **Health Checks**
- Dokploy automatically monitors your app health
- Set up notifications for downtime
- Monitor resource usage

### **Backups**
- Dokploy can backup your data volumes
- Set up automated backups in Dokploy dashboard
- Export database regularly

### **Updates**
- Push changes to your Git repository
- Dokploy will automatically redeploy
- Or manually trigger deployment from dashboard

## 🎯 **Expected Results**

After successful deployment:
- ✅ Website monitoring dashboard accessible
- ✅ Scheduler running and monitoring websites
- ✅ Email notifications working
- ✅ Data persistence across restarts
- ✅ Automatic SSL certificate (if domain configured)

## 📞 **Support**

If you encounter issues:
1. Check Dokploy logs first
2. Verify environment variables
3. Ensure all required ports are open
4. Check Docker container status

---

**Next Steps**: After deployment, test your app thoroughly and configure your domain for production use.