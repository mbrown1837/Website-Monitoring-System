# Website Monitoring System - Deployment Guide

## 🚀 **Recommended Deployment Options**

### **Option 1: Dokploy (RECOMMENDED) ⭐**

**Why Dokploy is best for this app:**
- ✅ Multi-container support (Flask app + Scheduler + Database)
- ✅ Built-in Traefik reverse proxy
- ✅ Better background task handling
- ✅ Native Docker Compose support
- ✅ Free and open-source
- ✅ Multi-server scaling support

**Installation:**
```bash
# On your Ubuntu VPS
curl -sSL https://dokploy.com/install.sh | sh
```

**Deployment Steps:**
1. Install Dokploy on your VPS
2. Access Dokploy dashboard
3. Create new project
4. Upload your code repository
5. Use `dokploy.yml` configuration
6. Set environment variables
7. Deploy

### **Option 2: Docker Compose + Nginx (Most Reliable)**

**For production-grade deployment:**
- ✅ Full control over configuration
- ✅ Better resource management
- ✅ Nginx reverse proxy with SSL
- ✅ Automatic database backups
- ✅ Separate scheduler process

**Deployment Steps:**
```bash
# Clone repository
git clone <your-repo>
cd website-monitoring

# Set environment variables
cp .env.example .env
nano .env

# Start services
docker-compose -f docker-compose.production.yml up -d

# Run migration script
docker-compose exec website-monitor python scripts/migrate_json_to_sqlite.py
```

### **Option 3: Coolify (Current - Limited)**

**Current setup issues:**
- ❌ Limited multi-container support
- ❌ Background task handling problems
- ❌ Scheduler synchronization issues

## 🔧 **Fixing the Scheduler Issue**

### **Root Cause**
The scheduler can't find websites because:
1. Websites are added via web interface (JSON file)
2. Scheduler reads from SQLite database
3. Data synchronization between JSON and SQLite is incomplete

### **Solution**
Run the migration script to sync data:

```bash
# On your VPS
python scripts/migrate_json_to_sqlite.py
```

### **Verification**
Check logs for:
```
SCHEDULER: Database path: /app/data/website_monitor.db
SCHEDULER: Cache loaded: True
SCHEDULER: Cache size: 7
SCHEDULER: Loaded 7 total websites from database
```

## 📋 **Environment Variables**

Create `.env` file with:
```env
DASHBOARD_URL=https://your-domain.com
SMTP_SERVER=mail.digitalclics.com
SMTP_PORT=465
SMTP_USERNAME=websitecheckapp@digitalclics.com
SMTP_PASSWORD=your-password
EMAIL_FROM=websitecheckapp@digitalclics.com
SECRET_KEY=your-secret-key
```

## 🐳 **Docker Configuration**

### **Current Issues with Coolify:**
1. Single container trying to run both Flask app and scheduler
2. Database synchronization problems
3. Limited process isolation

### **Recommended Fix:**
Use separate containers:
- `website-monitor`: Flask web application
- `website-scheduler`: Background scheduler process
- `nginx`: Reverse proxy (optional)

## 🔍 **Troubleshooting**

### **Scheduler Not Finding Websites:**
```bash
# Check database content
docker-compose exec website-monitor sqlite3 /app/data/website_monitor.db "SELECT COUNT(*) FROM websites;"

# Run migration
docker-compose exec website-monitor python scripts/migrate_json_to_sqlite.py

# Check logs
docker-compose logs website-scheduler
```

### **Email Notifications Not Working:**
1. Check SMTP credentials
2. Verify firewall settings (port 465/587)
3. Check email logs in dashboard

### **Performance Issues:**
1. Increase `max_concurrent_site_checks` in config
2. Adjust `single_site_processing` settings
3. Monitor resource usage

## 📊 **Monitoring & Maintenance**

### **Health Checks:**
- Web app: `https://your-domain.com/health`
- Scheduler: Check logs for "SCHEDULER: Found X active websites"

### **Backups:**
- Database: Automatic daily backups (if using production setup)
- Screenshots: Stored in Docker volumes
- Logs: Rotated automatically

### **Scaling:**
- Horizontal: Add more VPS instances with Dokploy
- Vertical: Increase VPS resources
- Database: Consider PostgreSQL for high-volume deployments

## 🚨 **Migration from Coolify to Dokploy**

1. **Backup current data:**
   ```bash
   docker cp coolify-container:/app/data ./backup-data
   ```

2. **Install Dokploy:**
   ```bash
   curl -sSL https://dokploy.com/install.sh | sh
   ```

3. **Deploy with Dokploy:**
   - Upload code repository
   - Use `dokploy.yml` configuration
   - Restore data volumes
   - Set environment variables

4. **Verify deployment:**
   - Check scheduler logs
   - Test website monitoring
   - Verify email notifications

## 📈 **Performance Optimization**

### **For High-Volume Monitoring:**
1. Use PostgreSQL instead of SQLite
2. Implement Redis for caching
3. Use Celery for background tasks
4. Add load balancing

### **For Resource Efficiency:**
1. Optimize Docker images
2. Use multi-stage builds
3. Implement proper logging rotation
4. Monitor memory usage

## 🔐 **Security Considerations**

1. **SSL/TLS**: Use Let's Encrypt certificates
2. **Firewall**: Restrict access to necessary ports
3. **Updates**: Keep Docker images updated
4. **Secrets**: Use environment variables for sensitive data
5. **Backups**: Encrypt backup data

## 📞 **Support**

If you encounter issues:
1. Check application logs
2. Verify environment variables
3. Test database connectivity
4. Check network connectivity
5. Review Docker container status
