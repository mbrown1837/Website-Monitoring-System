# Coolify Deployment Guide

## Environment Variables for Coolify

Set these environment variables in your Coolify deployment:

### Required Environment Variables:
```bash
# Dashboard URL (replace with your actual domain)
DASHBOARD_URL=https://your-coolify-domain.com

# Email Configuration
SMTP_SERVER=mail.digitalclics.com
SMTP_PORT=465
SMTP_USERNAME=websitecheckapp@digitalclics.com
SMTP_PASSWORD=your_email_password
SMTP_USE_SSL=true
SMTP_USE_TLS=false

# Notification Emails
NOTIFICATION_EMAIL_FROM=websitecheckapp@digitalclics.com
NOTIFICATION_EMAIL_TO=websitecheckapp@digitalclics.com

# Flask Environment
FLASK_ENV=production
```

## Email Delivery Issues - Troubleshooting

### Common Causes of Email Undelivery:

1. **SMTP Authentication Issues**
   - Check username/password are correct
   - Verify SMTP server settings
   - Ensure SSL/TLS configuration is correct

2. **Invalid Recipient Addresses**
   - Verify email addresses in website configurations
   - Check for typos in email addresses
   - Ensure recipient domains exist

3. **Spam Filter Issues**
   - Email content may be flagged as spam
   - Check spam folders
   - Consider adding SPF/DKIM records

4. **Network Connectivity**
   - Check if SMTP server is accessible from Coolify
   - Verify firewall settings
   - Test SMTP connection manually

5. **Email Content Issues**
   - Large attachments may cause delivery failures
   - HTML content may be flagged
   - Check email size limits

### Testing Email Delivery:

1. **Check Logs:**
   ```bash
   # In Coolify logs, look for:
   - "Email report sent successfully"
   - "SSL connection successful"
   - "Email delivery failed"
   ```

2. **Test SMTP Connection:**
   ```python
   import smtplib
   server = smtplib.SMTP_SSL('mail.digitalclics.com', 465)
   server.login('websitecheckapp@digitalclics.com', 'password')
   server.quit()
   ```

## Dashboard URL Configuration

The application now automatically uses:
1. `DASHBOARD_URL` environment variable (for Coolify)
2. `dashboard_url` from config file (fallback)
3. `http://localhost:5001` (development fallback)

## Email Template Improvements

- ✅ Removed white hover effects (changed to light gray)
- ✅ Optimized for Coolify environment
- ✅ Better error handling for email delivery issues
- ✅ Environment variable support for dashboard URLs

## Deployment Checklist

- [ ] Set `DASHBOARD_URL` environment variable
- [ ] Configure SMTP settings
- [ ] Test email delivery
- [ ] Verify dashboard links work
- [ ] Check logs for any errors
- [ ] Test all email templates
