# 🚀 Dokploy Quick Start Guide

## Prerequisites ✅
- Dokploy installed on Ubuntu VPS
- Git repository with your code
- SMTP credentials for email notifications

## Step-by-Step Deployment

### 1. Access Dokploy
- Open browser: `http://your-vps-ip:3000`
- Login with your credentials

### 2. Create Project
- Click **"New Project"**
- Choose **"Git Repository"**
- Enter repository URL and branch
- Project name: `website-monitor`

### 3. Configure Environment Variables
Add these in project settings:

```
DASHBOARD_URL=http://your-vps-ip:5001
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=your-email@gmail.com
SECRET_KEY=your-secret-key-here
SCHEDULER_ENABLED=true
LOG_LEVEL=INFO
TZ=UTC
```

### 4. Deploy
- Use `dokploy.yml` configuration
- Click **"Deploy"**
- Wait for build to complete

### 5. Access Application
- **URL**: `http://your-vps-ip:5001`
- **Health Check**: `http://your-vps-ip:5001/health`

## Quick Commands

```bash
# Check status
docker ps

# View logs
docker logs website-monitor

# Access container
docker exec -it website-monitor bash
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Port in use | Change port in dokploy.yml |
| Database error | Check volume mounts |
| Scheduler not working | Verify SCHEDULER_ENABLED=true |
| Email not working | Check SMTP credentials |

## Files Created
- `dokploy.yml` - Dokploy configuration
- `Dockerfile.production` - Production Dockerfile
- `DOKPLOY_DEPLOYMENT.md` - Detailed guide
- `.env.example` - Environment template

## Support
- Check logs in Dokploy dashboard
- Verify environment variables
- Test locally first
