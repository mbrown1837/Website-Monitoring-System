# 🚀 Dokploy Deployment Guide for Website Monitoring System

## Prerequisites
- ✅ Dokploy installed on your Ubuntu VPS
- ✅ Domain name pointing to your VPS (optional but recommended)
- ✅ SMTP credentials for email notifications

## Step 1: Access Dokploy Dashboard

1. Open your browser and go to: `http://your-vps-ip:3000`
2. Login with your Dokploy credentials
3. You should see the Dokploy dashboard

## Step 2: Create New Project

1. Click **"New Project"** or **"+"** button
2. Choose **"Git Repository"** as source
3. Enter your repository details:
   - **Repository URL**: Your Git repository URL
   - **Branch**: `main` or `master`
   - **Project Name**: `website-monitor`
   - **Description**: `Website Monitoring System`

## Step 3: Configure Environment Variables

In the project settings, add these environment variables:

### Required Environment Variables:
```
DASHBOARD_URL=http://your-domain.com (or http://your-vps-ip:5001)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=your-email@gmail.com
SECRET_KEY=your-secret-key-here
```

### Optional Environment Variables:
```
LOG_LEVEL=INFO
TZ=UTC
SCHEDULER_ENABLED=true
```

## Step 4: Configure Docker Compose

1. In your project, go to **"Docker Compose"** tab
2. Replace the default content with the content from `dokploy.yml`
3. Or upload the `dokploy.yml` file directly

## Step 5: Deploy

1. Click **"Deploy"** button
2. Wait for the build process to complete (5-10 minutes)
3. Check the logs for any errors

## Step 6: Access Your Application

1. Once deployed, your app will be available at:
   - **Local**: `http://your-vps-ip:5001`
   - **Domain**: `http://your-domain.com` (if configured)

2. The health check endpoint is available at:
   - `http://your-vps-ip:5001/health`

## Step 7: Verify Deployment

1. **Check Health**: Visit `/health` endpoint
2. **Check Logs**: Monitor logs in Dokploy dashboard
3. **Test Scheduler**: Check if websites are being monitored
4. **Test Email**: Add a test website and verify email notifications

## Troubleshooting

### Common Issues:

1. **Port Already in Use**:
   - Change port in `dokploy.yml` from `5001` to another port
   - Update `DASHBOARD_URL` environment variable

2. **Database Issues**:
   - Check if volumes are properly mounted
   - Verify database permissions

3. **Scheduler Not Working**:
   - Check logs for scheduler errors
   - Verify `SCHEDULER_ENABLED=true` is set

4. **Email Not Working**:
   - Verify SMTP credentials
   - Check firewall settings for port 587

### Useful Commands:

```bash
# Check container status
docker ps

# View logs
docker logs website-monitor

# Access container shell
docker exec -it website-monitor bash

# Check database
docker exec -it website-monitor sqlite3 /app/data/website_monitor.db
```

## Monitoring & Maintenance

1. **Logs**: Monitor logs in Dokploy dashboard
2. **Updates**: Push changes to Git, Dokploy will auto-deploy
3. **Backups**: Database is stored in Docker volume
4. **Scaling**: Dokploy supports horizontal scaling

## Security Considerations

1. **Firewall**: Only expose necessary ports (80, 443, 3000)
2. **SSL**: Configure SSL certificate for production
3. **Secrets**: Use Dokploy's secret management for sensitive data
4. **Updates**: Keep Dokploy and Docker images updated

## Support

If you encounter issues:
1. Check Dokploy logs
2. Check application logs
3. Verify environment variables
4. Test locally first
