# Email Alert System Documentation

## Overview

The system now automatically sends email notifications to administrators when security events occur, specifically for failed login attempts.

## Email Notifications

### 1. Failed Login Alert (First Attempt)
Sent when a **registered user** enters the **wrong password for the first time**.

**Trigger:** First failed login attempt (LOGIN_ATTEMPTS = 0 → 1)

**Email includes:**
- Email address that attempted login
- Timestamp of attempt
- IP address
- Security recommendations

**Example Scenario:**
```
User: admin@g.com
Attempt: Wrong password
Result: Email sent to administrator
```

### 2. Unregistered User Alert
Sent when someone tries to login with an **email that doesn't exist** in the database.

**Trigger:** Login attempt with non-existent email

**Email includes:**
- Attempted email address
- Timestamp
- IP address
- Instructions to create the user account if legitimate
- Command to run admin tool

**Example Scenario:**
```
User: newuser@company.com (doesn't exist in system)
Attempt: Any password
Result: Email sent to administrator with instructions
```

## Configuration

### Setup Email Alerts

Add these variables to your `.env` file:

```env
# Email Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your-email@gmail.com
SENDER_PASSWORD=your-app-password
ADMIN_EMAIL=admin@example.com
```

### For Gmail Users

1. **Enable 2-Factor Authentication**
   - Go to Google Account Settings
   - Security > 2-Step Verification
   - Enable it

2. **Generate App Password**
   - In 2-Step Verification settings
   - Click "App passwords"
   - Select "Mail" and your device
   - Copy the 16-character password

3. **Configure .env**
   ```env
   SENDER_EMAIL=your-email@gmail.com
   SENDER_PASSWORD=abcd efgh ijkl mnop  # 16-char app password
   ADMIN_EMAIL=security@yourcompany.com
   ```

### For Other Email Providers

**Office 365 / Outlook:**
```env
SMTP_SERVER=smtp.office365.com
SMTP_PORT=587
```

**Custom SMTP:**
```env
SMTP_SERVER=mail.yourcompany.com
SMTP_PORT=587 or 465
```

## Email Templates

### Failed Login Alert Email

**Subject:** 🚨 Security Alert: Failed Login Attempt

**Content:**
- Red alert banner
- Attempt details (email, time, IP)
- "What This Means" section
- Recommended actions
- Security checklist

### Unregistered User Alert Email

**Subject:** 🔔 Login Attempt with Unregistered Email: {email}

**Content:**
- Orange warning banner
- Attempt details
- Possible scenarios (legitimate user, exploration, attack)
- Instructions to create user account
- Admin tool command

## Behavior Without Email Configuration

If email settings are **not configured** in `.env`:

✅ System continues to work normally
✅ Alerts are logged to console/file
✅ No emails sent (graceful degradation)

Example log output:
```
[WARNING] Email not configured. Would send: 🚨 Security Alert: Failed Login Attempt to admin@example.com
[INFO] Email content: A failed login attempt was detected...
```

## Testing Email Configuration

### Option 1: Using Admin Tool

```bash
python3 admin_user_manager.py
```

Add a test email function (can be added):
```python
# In admin tool menu
def test_email():
    from utils.email_service import EmailService
    service = EmailService()
    if service.test_email_configuration():
        print("✓ Email test successful!")
    else:
        print("✗ Email test failed")
```

### Option 2: Manual Test

```python
from utils.email_service import EmailService

service = EmailService()

# Check if configured
if service.is_configured:
    print("✓ Email is configured")

    # Send test email
    service.test_email_configuration()
else:
    print("✗ Email not configured")
```

### Option 3: Trigger Real Alert

1. Start the application
2. Try to login with wrong password
3. Check administrator email inbox

## Email Alert Flow

```
┌─────────────────────┐
│   User Login        │
│   Attempt           │
└──────────┬──────────┘
           │
           ▼
    ┌──────────────┐
    │  Wrong       │  YES
    │  Password?   ├────────┐
    └──────┬───────┘        │
           │ NO             │
           ▼                ▼
    ┌──────────────┐  ┌─────────────────┐
    │  Email       │  │ Check LOGIN_    │
    │  Exists?     │  │ ATTEMPTS == 0?  │
    └──────┬───────┘  └────────┬────────┘
           │ NO               │ YES
           │                  │
           ▼                  ▼
    ┌──────────────────┐  ┌───────────────┐
    │ Send Unregister  │  │ Send Failed   │
    │ User Alert       │  │ Login Alert   │
    │ (Orange Email)   │  │ (Red Email)   │
    └──────────────────┘  └───────────────┘
```

## Security Best Practices

### Recommended Settings

1. **Use dedicated email account** for sending alerts
2. **Use app-specific passwords**, not main account password
3. **Monitor admin email** regularly for alerts
4. **Set up email filters** to highlight security alerts
5. **Configure email retention** for audit trail

### Alert Response Procedures

**For Failed Login Alerts:**
1. Verify if user reported password issues
2. Check if multiple attempts from same IP
3. Consider password reset if needed
4. Monitor for patterns

**For Unregistered User Alerts:**
1. Investigate if email is legitimate employee/user
2. Check if user needs account creation
3. Run admin tool to create account if appropriate
4. Document decision for audit purposes

## Logging

All email attempts are logged regardless of success:

**Successful email:**
```
[INFO] Email sent successfully to admin@example.com: Failed Login Attempt
```

**Failed email:**
```
[ERROR] Failed to send email: SMTP Authentication Error
[INFO] Email content: A failed login attempt was detected...
```

**Email not configured:**
```
[WARNING] Email not configured. Would send: Security Alert
```

## Customization

### Custom Email Templates

Edit `utils/email_service.py` to customize templates:

```python
def send_failed_login_alert(self, attempted_email, ip_address=None):
    subject = f"Custom Subject Here"
    body = """
    Custom HTML template here
    """
    return self._send_email(self.admin_email, subject, body, is_html=True)
```

### Additional Alert Types

Add new alert methods:

```python
def send_successful_login_notification(self, email, ip_address):
    """Notify on successful login (optional feature)"""
    # Implementation here
    pass

def send_account_locked_alert(self, email):
    """Alert when account is locked after X attempts"""
    # Implementation here
    pass
```

## Troubleshooting

### Email Not Sending

**Check 1: Configuration**
```python
from utils.email_service import EmailService
service = EmailService()
print(f"Configured: {service.is_configured}")
print(f"SMTP: {service.smtp_server}:{service.smtp_port}")
```

**Check 2: SMTP Credentials**
- Verify app password (not regular password)
- Check 2FA is enabled
- Test SMTP connection manually

**Check 3: Firewall/Network**
- Port 587 (TLS) or 465 (SSL) open
- Outbound SMTP allowed
- No proxy blocking SMTP

**Check 4: Logs**
```bash
tail -f logs/bloomberg_ingestion.log
```

### Common Errors

**"SMTP Authentication Error"**
→ Wrong password or app password not generated

**"Connection refused"**
→ SMTP server/port incorrect or blocked

**"Email not configured"**
→ Missing environment variables in `.env`

## Production Recommendations

1. **Use dedicated SMTP service**
   - SendGrid
   - Amazon SES
   - Mailgun

2. **Set up SPF/DKIM** for deliverability

3. **Configure alerts aggregation** (don't spam on rapid attempts)

4. **Add rate limiting** for email alerts

5. **Store email history** in database for audit

## Summary

✅ Email alerts on first failed login attempt
✅ Email alerts for unregistered user attempts
✅ Beautiful HTML email templates
✅ IP address tracking
✅ Graceful degradation without config
✅ Gmail/Office365/Custom SMTP support
✅ Comprehensive logging
✅ Easy configuration via `.env`

The email system enhances security monitoring while being completely optional!
