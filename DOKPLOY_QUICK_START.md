# 🚀 Dokploy Quick Start Guide

## ⚡ **Quick Deployment Steps**

### **1. Access Dokploy**
```
http://your-vps-ip:3000
```

### **2. Create Project**
- Click **"New Project"**
- Name: `website-monitor`
- Type: **Docker Compose**

### **3. Connect Repository**
- **Git Source**: `https://github.com/yourusername/website-monitoring`
- **Branch**: `main`

### **4. Environment Variables**
```bash
DASHBOARD_URL=http://your-domain.com
SECRET_KEY=your-secret-key-here
SCHEDULER_ENABLED=true
LOG_LEVEL=INFO
TZ=UTC
```

### **5. Deploy**
- Click **"Deploy"**
- Wait for build completion
- Access: `http://your-vps-ip:5001`

## 🔧 **Required Environment Variables**

| Variable | Description | Example |
|----------|-------------|---------|
| `DASHBOARD_URL` | Your app's public URL | `https://monitor.yourdomain.com` |
| `SECRET_KEY` | Flask secret key | `your-secret-key-here` |
| `SCHEDULER_ENABLED` | Enable scheduler | `true` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `TZ` | Timezone | `UTC` |

## 📧 **Optional Email Variables**
```bash
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=your-email@gmail.com
```

## 🎯 **Expected Results**
- ✅ Dashboard accessible at your URL
- ✅ Scheduler monitoring websites
- ✅ Health check: `/health` endpoint
- ✅ Data persistence across restarts

## 🆘 **Troubleshooting**
- **App not starting**: Check environment variables
- **Scheduler not working**: Verify `SCHEDULER_ENABLED=true`
- **Database issues**: Check volume mounts
- **Email not working**: Verify SMTP credentials

## 📞 **Need Help?**
1. Check Dokploy logs
2. Verify all environment variables
3. Ensure ports 5001 and 8765 are open
4. Check Docker container status

---
**Ready to deploy? Follow the steps above!** 🚀