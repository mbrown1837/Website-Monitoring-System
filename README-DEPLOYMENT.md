# Website Monitoring System - Coolify Deployment Guide

## 🚀 Quick Deployment to Coolify

### Prerequisites
- Coolify installed on your VPS
- Domain name configured
- SMTP credentials for email notifications

### 1. Environment Variables to Set in Coolify

#### Required Variables:
```
DASHBOARD_URL=https://your-domain.com
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=your-email@gmail.com
SECRET_KEY=your-secure-secret-key-here
```

#### Optional Variables:
```
LOG_LEVEL=INFO
SCHEDULER_ENABLED=true
DEFAULT_CHECK_INTERVAL=1440
MAX_WORKERS=4
```

### 2. Deployment Steps

1. **Create New Project in Coolify**
   - Go to your Coolify dashboard
   - Click "New Project"
   - Choose "Docker Compose" or "Dockerfile"

2. **Configure Repository**
   - Connect your Git repository
   - Set build context to root directory
   - Use `Dockerfile` for build

3. **Set Environment Variables**
   - Add all required environment variables
   - Ensure `DASHBOARD_URL` points to your domain
   - Configure SMTP settings for email notifications

4. **Deploy**
   - Click "Deploy"
   - Wait for build to complete
   - Check health status at `https://your-domain.com/health`

### 3. Post-Deployment Configuration

1. **Access the Application**
   - Navigate to your domain
   - Default admin credentials (if any) should be set

2. **Configure Websites**
   - Add websites to monitor
   - Set check intervals
   - Configure email notifications

3. **Test Functionality**
   - Run manual checks
   - Verify email notifications
   - Check scheduler status

### 4. Health Check Endpoints

- **Basic Health**: `GET /health`
- **Detailed Health**: `GET /health/detailed`
- **Readiness**: `GET /health/ready`
- **Liveness**: `GET /health/live`

### 5. Monitoring and Logs

- **Application Logs**: Available in Coolify dashboard
- **Database**: SQLite file in `/app/data/`
- **Screenshots**: Stored in `/app/screenshots/`
- **Configuration**: Stored in `/app/config/`

### 6. Troubleshooting

#### Common Issues:
1. **Port Conflicts**: Ensure port 5001 is available
2. **Database Permissions**: Check volume mount permissions
3. **Email Issues**: Verify SMTP credentials
4. **Scheduler Not Working**: Check `SCHEDULER_ENABLED=true`

#### Debug Commands:
```bash
# Check application status
curl https://your-domain.com/health

# Check detailed health
curl https://your-domain.com/health/detailed

# Check logs
docker logs website-monitor
```

### 7. Security Considerations

- Change default `SECRET_KEY`
- Use strong SMTP passwords
- Enable HTTPS (handled by Coolify)
- Regular database backups
- Monitor resource usage

### 8. Backup Strategy

- **Database**: Regular backups of `/app/data/website_monitor.db`
- **Configuration**: Backup `/app/config/` directory
- **Screenshots**: Optional backup of `/app/screenshots/`

### 9. Updates

- Pull latest changes from Git
- Redeploy through Coolify
- Database migrations are automatic
- No data loss during updates

## 📊 Features Included

✅ **Website Monitoring**: Visual, crawl, blur, and performance checks
✅ **Scheduler**: Automated monitoring with configurable intervals
✅ **Email Notifications**: Real-time alerts and reports
✅ **Web Interface**: Modern, responsive dashboard
✅ **API Endpoints**: RESTful API for integration
✅ **Health Checks**: Production-ready health monitoring
✅ **Docker Support**: Containerized deployment
✅ **Database**: SQLite with automatic migrations
✅ **Logging**: Comprehensive logging system
✅ **WebSocket**: Real-time updates

## 🔧 Technical Details

- **Framework**: Flask (Python 3.11)
- **Database**: SQLite with WAL mode
- **Frontend**: Bootstrap 5 + JavaScript
- **Email**: SMTP with HTML templates
- **Scheduling**: APScheduler
- **WebSocket**: Flask-SocketIO
- **Container**: Docker with multi-stage build
- **Health Checks**: Built-in endpoints
- **Logging**: Structured logging with rotation

## 📞 Support

For issues or questions:
1. Check application logs in Coolify
2. Verify environment variables
3. Test health check endpoints
4. Review this documentation
