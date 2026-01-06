# Cloud Foundry Deployment Instructions

## Important: DO NOT commit API keys to Git!

The SendGrid API key must be set via Cloud Foundry environment variables, NOT in manifest.yml.

## Deployment Steps

### 1. Deploy the Application

```bash
cf push
```

### 2. Set SendGrid API Key

**IMPORTANT:** After deployment, immediately set the SendGrid API key:

```bash
cf set-env financial-dashboard SENDGRID_API_KEY "your_sendgrid_api_key_here"
```

Replace `your_sendgrid_api_key_here` with your actual SendGrid API key (starts with `SG.`).

### 3. Restage the Application

```bash
cf restage financial-dashboard
```

### 4. Verify Email Configuration

SSH into the app and test:

```bash
cf ssh financial-dashboard
cd app
python3 test_email.py
exit
```

You should see:
```
✓ Test email sent successfully!
```

## Email Configuration Summary

The following environment variables are configured:

- **SENDGRID_FROM_EMAIL**: nikhilpr16+alerts@katbotz.com (verified sender)
- **NOTIFICATION_EMAIL**: nikhilpr16@katbotz.com (receives alerts)
- **SENDGRID_API_KEY**: Set via `cf set-env` command (NEVER commit to Git)

## Testing Email Alerts

1. Navigate to the deployed app: https://financial-dashboard.cfapps.us10-001.hana.ondemand.com/
2. Try to login with wrong password
3. Check email at nikhilpr16@katbotz.com
4. You should receive a "Failed Login Attempt" alert

## Security Notes

- ✅ API keys are set via Cloud Foundry environment variables
- ✅ .env file is in .gitignore (local development only)
- ✅ GitHub push protection blocks accidental key commits
- ✅ manifest.yml contains NO secrets (safe to commit)

## Quick Reference

```bash
# View all environment variables
cf env financial-dashboard

# Update SendGrid API key
cf set-env financial-dashboard SENDGRID_API_KEY "your_new_key"
cf restage financial-dashboard

# View recent logs
cf logs financial-dashboard --recent

# Test the application
curl https://financial-dashboard.cfapps.us10-001.hana.ondemand.com/
```
