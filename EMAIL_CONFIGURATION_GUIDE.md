# 📧 Email Configuration Guide

## 🚨 Current Issue
The SMTP server `mail.digitalclics.com:465` is not responding (connection timeout). This prevents email notifications from being sent.

## ✅ Solutions

### Option 1: Environment Variables (Recommended for Dokploy)

Set these environment variables in your Dokploy deployment:

#### Gmail Configuration:
```bash
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-gmail@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_USE_TLS=true
SMTP_USE_SSL=false
NOTIFICATION_EMAIL_FROM=your-gmail@gmail.com
```

#### Outlook Configuration:
```bash
SMTP_SERVER=smtp.outlook.com
SMTP_PORT=587
SMTP_USERNAME=your-outlook@outlook.com
SMTP_PASSWORD=your-password
SMTP_USE_TLS=true
SMTP_USE_SSL=false
NOTIFICATION_EMAIL_FROM=your-outlook@outlook.com
```

#### Other SMTP Providers:
```bash
SMTP_SERVER=your-smtp-server.com
SMTP_PORT=587
SMTP_USERNAME=your-email@domain.com
SMTP_PASSWORD=your-password
SMTP_USE_TLS=true
SMTP_USE_SSL=false
NOTIFICATION_EMAIL_FROM=your-email@domain.com
```

### Option 2: Update Config File

Edit `config/config.yaml`:

```yaml
smtp_server: smtp.gmail.com
smtp_port: 587
smtp_username: your-gmail@gmail.com
smtp_password: your-app-password
smtp_use_tls: true
smtp_use_ssl: false
notification_email_from: your-gmail@gmail.com
```

### Option 3: Fix Current Server

If you want to keep using `mail.digitalclics.com`:

1. **Check server status** with your email provider
2. **Try different ports**: 587, 25, 993, 995
3. **Verify credentials** are correct
4. **Check firewall/network** connectivity

## 🔧 Testing Email Configuration

Run the test script to verify your configuration:

```bash
python scripts/test_email.py
```

This will:
- Test SMTP connection
- Send a test email
- Show current configuration
- Display any errors

## 📋 Gmail Setup (if using Gmail)

1. **Enable 2-Factor Authentication** on your Google account
2. **Generate App Password**:
   - Go to Google Account settings
   - Security → 2-Step Verification → App passwords
   - Generate password for "Mail"
3. **Use the app password** (not your regular password) in `SMTP_PASSWORD`

## 🔍 Troubleshooting

### Connection Timeout
- Check if SMTP server is accessible from your network
- Try different ports (587, 465, 25)
- Verify firewall settings

### Authentication Failed
- Double-check username and password
- For Gmail: use app password, not regular password
- Ensure 2FA is enabled for Gmail

### SSL/TLS Issues
- Try `SMTP_USE_TLS=true` and `SMTP_USE_SSL=false` for port 587
- Try `SMTP_USE_TLS=false` and `SMTP_USE_SSL=true` for port 465

## 📊 Current Status

✅ **Email system architecture** - Working correctly  
✅ **Default email fallback** - Using `websitecheckapp@digitalclics.com`  
✅ **Individual check emails** - Triggered correctly  
✅ **Fallback SMTP servers** - Gmail/Outlook as backup  
❌ **Primary SMTP server** - `mail.digitalclics.com:465` not responding  

## 🎯 Next Steps

1. **Choose a working SMTP provider** (Gmail recommended)
2. **Set environment variables** in Dokploy
3. **Test email functionality** with the test script
4. **Redeploy** to Dokploy with new configuration
5. **Verify emails** are being sent for manual checks

The email system is working correctly - it just needs a working SMTP server! 🚀
