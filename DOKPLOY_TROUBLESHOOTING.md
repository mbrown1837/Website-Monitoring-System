# Dokploy Troubleshooting Guide

## 🚨 **App URL Not Working - Quick Fixes**

### **1. Check Container Port Configuration**

In your Dokploy service settings, ensure:
- **Container Port**: `5001` (not 3000)
- **Host Port**: `5001` or leave empty for auto-assignment
- **Protocol**: `HTTP`

### **2. Verify Subdomain Configuration**

**DNS Settings (SiteGround):**
- **Type**: A Record
- **Name**: `websitemonitor` (or `websitemonitor.digitalclics.com`)
- **Value**: `167.86.123.94` (your Dokploy server IP)
- **TTL**: 300 (5 minutes)

**Dokploy Custom Domain:**
- **Domain**: `websitemonitor.digitalclics.com`
- **Container Port**: `5001`
- **SSL**: Enabled (Let's Encrypt)

### **3. Check Container Status**

Run these commands in Dokploy terminal or SSH:

```bash
# Check if container is running
docker ps | grep website-monitor

# Check container logs
docker logs digital-clics-website-monitoring-alhtqs-website-monitor-1

# Check if port 5001 is listening
netstat -tlnp | grep 5001
```

### **4. Test Direct Access**

Try accessing your app directly:
- **IP Access**: `http://167.86.123.94:5001`
- **Subdomain**: `https://websitemonitor.digitalclics.com`

### **5. Common Issues & Solutions**

**Issue**: Container not starting
**Solution**: Check logs for Python/Flask errors

**Issue**: Port 5001 not accessible
**Solution**: Verify Dokploy port mapping

**Issue**: Subdomain not resolving
**Solution**: Wait 5-10 minutes for DNS propagation

**Issue**: SSL certificate issues
**Solution**: Check Let's Encrypt logs in Dokploy

### **6. Environment Variables Check**

Ensure these are set in Dokploy:
```
DASHBOARD_URL=https://websitemonitor.digitalclics.com
SMTP_SERVER=mail.digitalclics.com
SMTP_PORT=465
SMTP_USERNAME=websitecheckapp@digitalclics.com
SMTP_PASSWORD=your_password
SECRET_KEY=website-monitor-secret-key-2024-3016d3d1d5f59d6a8b2121508dfdc174
SCHEDULER_ENABLED=true
LOG_LEVEL=INFO
TZ=UTC
```

### **7. Quick Health Check**

If the container is running, test:
```bash
curl http://localhost:5001/health
```

Should return: `{"status": "healthy"}`

## 🔧 **Next Steps**

1. **Check container logs** for any errors
2. **Verify port configuration** in Dokploy
3. **Test direct IP access** first
4. **Check DNS propagation** for subdomain
5. **Review SSL certificate** status

## 📞 **Need Help?**

If still not working, provide:
- Container logs output
- Dokploy service configuration screenshot
- DNS settings screenshot
- Any error messages
