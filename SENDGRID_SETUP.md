# SendGrid Email Alerts Setup Guide

## Overview

The Bloomberg Analytics Hub uses SendGrid API to send email notifications for security events, specifically failed login attempts.

## Email Notifications

### 1. Failed Login Alert (First Attempt)
Sent when a **registered user** enters the **wrong password for the first time**.

**Trigger:** First failed login attempt (LOGIN_ATTEMPTS = 0 → 1)

**Email includes:**
- Email address that attempted login
- Timestamp of attempt
- IP address
- Security recommendations

### 2. Unregistered User Alert
Sent when someone tries to login with an **email that doesn't exist** in the database.

**Trigger:** Login attempt with non-existent email

**Email includes:**
- Attempted email address
- Timestamp
- IP address
- Instructions to create the user account if legitimate

## SendGrid Configuration

### Step 1: Create SendGrid Account

1. Go to https://sendgrid.com
2. Sign up for a free account
   - **Free tier:** 100 emails/day (sufficient for security alerts)
   - No credit card required for free tier
3. Complete email verification

### Step 2: Create API Key

1. Log into SendGrid dashboard
2. Navigate to **Settings > API Keys**
3. Click **"Create API Key"**
4. Configure the API key:
   - **Name:** "Bloomberg Analytics Alerts" (or your preferred name)
   - **Permissions:** Select "Full Access" OR minimum "Mail Send"
5. Click **"Create & View"**
6. **IMPORTANT:** Copy the API key immediately!
   - Format: `SG.xxxxxxxxxxxxxxxxxxxxxxx`
   - You won't be able to see it again
   - Store it securely

### Step 3: Verify Sender Email

SendGrid requires you to verify the email address you'll send FROM:

1. Navigate to **Settings > Sender Authentication**
2. Click **"Verify a Single Sender"**
   - For production: Use domain authentication (better deliverability)
   - For testing: Single sender verification is fine
3. Fill in sender details:
   - **From Email:** The email that will appear in "From" field
     - Example: `alerts@yourcompany.com`
     - Example: `nikhilpr16+alerts@katbotz.com`
   - **From Name:** "Bloomberg Analytics Alerts"
   - **Reply To:** Your support/admin email
   - **Company Address:** Your company details
4. Click **"Create"**
5. **Check your email** for verification link
6. Click the verification link
7. Sender is now verified and can be used

### Step 4: Configure Environment Variables

#### For Local Development (.env file)

Create or update `.env` file in project root:

```env
# SendGrid Configuration
SENDGRID_API_KEY=SG.your_actual_api_key_here
SENDGRID_FROM_EMAIL=alerts@yourcompany.com
NOTIFICATION_EMAIL=admin@yourcompany.com
```

**Example:**
```env
SENDGRID_API_KEY=SG.K7xYz9AbCdEfGhIjKlMnOpQrStUvWxYz
SENDGRID_FROM_EMAIL=nikhilpr16+alerts@katbotz.com
NOTIFICATION_EMAIL=nikhilpr16@katbotz.com
```

#### For Cloud Foundry Production

**Option 1: Environment Variables (Recommended)**

```bash
cf set-env financial-dashboard SENDGRID_API_KEY "SG.your_key_here"
cf set-env financial-dashboard SENDGRID_FROM_EMAIL "alerts@yourcompany.com"
cf set-env financial-dashboard NOTIFICATION_EMAIL "admin@yourcompany.com"
cf restage financial-dashboard
```

**Option 2: manifest.yml (Not Recommended for Secrets)**

```yaml
env:
  SENDGRID_API_KEY: SG.your_key_here
  SENDGRID_FROM_EMAIL: alerts@yourcompany.com
  NOTIFICATION_EMAIL: admin@yourcompany.com
```

**IMPORTANT:** Never commit real API keys to Git!

### Step 5: Install SendGrid Library

The `sendgrid` library is already in `requirements.txt`:

```txt
sendgrid==6.11.0
```

**Local installation:**
```bash
pip install sendgrid
```

**Cloud Foundry:** Automatically installed during staging

## Testing Email Configuration

### Option 1: Using Admin Tool

```bash
python3 admin_user_manager.py
```

Add a test option to send a test email (future enhancement).

### Option 2: Manual Test

```python
from utils.email_service import EmailService

service = EmailService()

# Check if configured
if service.is_configured:
    print("✓ Email is configured")

    # Send test email
    if service.test_email_configuration():
        print("✓ Test email sent successfully!")
        print(f"Check {service.notification_email} for the test email")
    else:
        print("✗ Failed to send test email")
else:
    print("✗ Email not configured")
    print("Missing environment variables:")
    if not service.sendgrid_api_key:
        print("  - SENDGRID_API_KEY")
    if not service.sender_email:
        print("  - SENDGRID_FROM_EMAIL")
    if not service.notification_email:
        print("  - NOTIFICATION_EMAIL")
```

### Option 3: Trigger Real Alert

1. Start the application
2. Try to login with a registered user but wrong password
3. Check notification email inbox for security alert

## Email Templates

### Failed Login Alert Email

**Subject:** 🚨 Security Alert: Failed Login Attempt

**Features:**
- Red alert banner
- Attempt details table (email, time, IP)
- "What This Means" section
- Recommended security actions
- Professional HTML formatting

### Unregistered User Alert Email

**Subject:** 🔔 Login Attempt with Unregistered Email: {email}

**Features:**
- Orange warning banner
- Attempt details table
- Possible scenarios explanation
- Instructions to create user account
- Admin tool command reference

## Behavior Without Configuration

If SendGrid is **not configured** in environment variables:

✅ System continues to work normally
✅ Alerts are logged to console/file
✅ No emails sent (graceful degradation)
✅ No errors or crashes

**Example log output:**
```
[WARNING] Email not configured. Would send: 🚨 Security Alert: Failed Login Attempt to admin@example.com
[INFO] Email content preview: <html><body>...
```

## Troubleshooting

### Issue 1: "SendGrid library not installed"

**Solution:**
```bash
pip install sendgrid==6.11.0
```

Or add to requirements.txt and install:
```bash
pip install -r requirements.txt
```

### Issue 2: "Email not configured"

**Check environment variables are set:**
```python
import os
print(f"API Key: {os.getenv('SENDGRID_API_KEY', 'NOT SET')}")
print(f"From Email: {os.getenv('SENDGRID_FROM_EMAIL', 'NOT SET')}")
print(f"Notification Email: {os.getenv('NOTIFICATION_EMAIL', 'NOT SET')}")
```

**For Cloud Foundry:**
```bash
cf env financial-dashboard | grep SENDGRID
cf env financial-dashboard | grep NOTIFICATION
```

### Issue 3: "Forbidden" or "Unauthorized" Error

**Cause:** Invalid API key or insufficient permissions

**Solution:**
1. Verify API key is correct (starts with `SG.`)
2. Check API key has "Mail Send" permission
3. Regenerate API key if needed

### Issue 4: "The from email does not match a verified Sender Identity"

**Cause:** Sender email not verified in SendGrid

**Solution:**
1. Go to SendGrid: Settings > Sender Authentication
2. Verify the email in SENDGRID_FROM_EMAIL
3. Check email and click verification link
4. Wait a few minutes for verification to propagate

### Issue 5: Emails Going to Spam

**Solutions:**
1. **Use Domain Authentication** instead of single sender (Settings > Sender Authentication)
2. **SPF and DKIM:** Add DNS records provided by SendGrid
3. **Avoid spam triggers:** Don't use ALL CAPS in subject, excessive exclamation marks
4. **Warm up sending:** Start with low volume, gradually increase

### Issue 6: Rate Limiting

**Free tier limits:**
- 100 emails/day
- 200 emails/day for verified domains

**Solution:**
- Implement alert aggregation (send summary instead of individual alerts)
- Upgrade to paid plan if needed
- Add rate limiting in code:

```python
# Track last email sent time
# Only send if > 5 minutes since last email
```

## Production Best Practices

### 1. API Key Security

✅ **DO:**
- Store API keys in environment variables
- Use Cloud Foundry services/user-provided-services
- Rotate API keys regularly
- Use different API keys for dev/staging/prod

❌ **DON'T:**
- Commit API keys to Git
- Share API keys in plain text
- Use same API key across environments
- Give API keys more permissions than needed

### 2. Sender Reputation

- Use domain authentication (not single sender)
- Set up SPF, DKIM, DMARC records
- Monitor bounce rates and spam complaints
- Use consistent "From" email address
- Keep sending volume consistent

### 3. Email Content

- Keep emails professional and clear
- Include unsubscribe link for non-critical alerts
- Use proper HTML structure
- Test on multiple email clients
- Keep under 102KB total size

### 4. Monitoring

Track these metrics in SendGrid dashboard:
- Delivery rate (should be >95%)
- Bounce rate (should be <5%)
- Spam report rate (should be <0.1%)
- Open rate (if tracking enabled)

### 5. Alert Aggregation

Instead of sending every single failed login attempt:

```python
# Send summary every hour
# "5 failed login attempts in the last hour"

# Or send only on threshold
# "Account locked after 5 failed attempts"
```

## SendGrid Alternatives

If SendGrid doesn't meet your needs:

1. **Amazon SES**
   - Cheaper at scale
   - Requires AWS account
   - Good deliverability

2. **Mailgun**
   - Similar to SendGrid
   - Good API documentation
   - Flexible pricing

3. **Postmark**
   - Focused on transactional emails
   - Excellent deliverability
   - More expensive

4. **SMTP (Gmail, Office 365)**
   - Free for low volume
   - More complex setup
   - May have rate limits

## Summary

✅ SendGrid API for reliable email delivery
✅ HTML email templates with security alerts
✅ IP address and timestamp tracking
✅ Graceful degradation without config
✅ Free tier (100 emails/day)
✅ Easy setup and verification
✅ Comprehensive logging
✅ Professional email formatting

The SendGrid implementation provides enterprise-grade email delivery for security notifications!
