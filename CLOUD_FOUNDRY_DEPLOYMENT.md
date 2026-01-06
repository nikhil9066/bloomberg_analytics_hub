# Cloud Foundry Deployment Guide

## Fix for "404 Not Found: Requested route does not exist"

### Problem
You're getting: `404 Not Found: Requested route ('financial-dashboard.cfapps.us10-001.hana.ondemand.com') does not exist.`

### Solution Steps

## 1. Update Your Deployment Files

The `manifest.yml` has been updated with:
- Explicit route mapping
- Proper PORT binding
- Gunicorn configuration with logging

## 2. Deploy with Route Mapping

### Option A: Quick Fix (Use existing route)

```bash
# Navigate to your project
cd /Users/nikhilprao/Documents/bloomberg_analytics_hub

# Login to Cloud Foundry
cf login -a https://api.cf.us10-001.hana.ondemand.com

# Push the application
cf push financial-dashboard

# Map the route explicitly
cf map-route financial-dashboard cfapps.us10-001.hana.ondemand.com --hostname financial-dashboard
```

### Option B: Clean Deploy (Recommended)

```bash
# Delete the existing app first
cf delete financial-dashboard -f

# Push with the updated manifest
cf push

# Verify the route
cf routes
```

## 3. Verify Deployment

### Check Application Status
```bash
cf apps
```

Expected output:
```
name                 requested state   instances   memory   disk   urls
financial-dashboard  started           1/1         1G       1G     financial-dashboard.cfapps.us10-001.hana.ondemand.com
```

### Check Logs
```bash
cf logs financial-dashboard --recent
```

### Access the Application
```
https://financial-dashboard.cfapps.us10-001.hana.ondemand.com/
```

Should redirect to `/login`

## 4. Initialize the Database

### Create USERS Table

After successful deployment, you need to initialize the database:

```bash
# SSH into the app
cf ssh financial-dashboard

# Run the admin tool
python3 admin_user_manager.py
```

Then:
1. It will create the USERS table automatically
2. It will create the default admin user (admin@g.com / admin)
3. Exit (option 7)

## 5. Test the Application

### Test Login Page
```
https://financial-dashboard.cfapps.us10-001.hana.ondemand.com/
```

Should show the login page.

### Test Authentication
- Email: `admin@g.com`
- Password: `admin`

Should redirect to dashboard at `/dashboard/`

## Troubleshooting

### Issue: Route Still Not Found

**Check current routes:**
```bash
cf routes
```

**Unmap old route if exists:**
```bash
cf unmap-route financial-dashboard cfapps.us10-001.hana.ondemand.com --hostname financial-dashboard
```

**Map new route:**
```bash
cf map-route financial-dashboard cfapps.us10-001.hana.ondemand.com --hostname financial-dashboard
```

### Issue: Application Crashes on Startup

**Check logs:**
```bash
cf logs financial-dashboard --recent
```

**Common issues:**
1. **Missing dependencies**: Check requirements.txt includes `cryptography`
2. **HANA connection failed**: Check HANA credentials in manifest.yml
3. **Port binding issue**: Gunicorn should bind to `$PORT`

### Issue: Login Returns 503

This means authentication service can't connect to HANA.

**Check HANA credentials:**
```bash
cf env financial-dashboard
```

Verify:
- HANA_ADDRESS
- HANA_USER
- HANA_PASSWORD
- HANA_SCHEMA

**Update if needed:**
```bash
cf set-env financial-dashboard HANA_PASSWORD "your-correct-password"
cf restage financial-dashboard
```

### Issue: Login Page Shows But Can't Login

**Check if USERS table exists:**
```bash
cf ssh financial-dashboard
python3 admin_user_manager.py
# Select option 3 to list users
```

If no users, create admin:
```bash
# In admin tool, select option 1
Email: admin@g.com
Password: admin
Name: Administrator
Role: ADMIN
```

## Cloud Foundry Commands Reference

### Deployment
```bash
cf push                          # Deploy app
cf push -f manifest.yml          # Deploy with specific manifest
cf restage financial-dashboard   # Rebuild without code changes
cf restart financial-dashboard   # Restart app
```

### Monitoring
```bash
cf apps                          # List apps
cf app financial-dashboard       # App details
cf logs financial-dashboard      # Stream logs
cf logs financial-dashboard --recent  # Recent logs
cf events financial-dashboard    # App events
```

### Environment
```bash
cf env financial-dashboard                    # Show all env vars
cf set-env financial-dashboard KEY value      # Set env var
cf unset-env financial-dashboard KEY          # Remove env var
```

### Routes
```bash
cf routes                                                           # List all routes
cf map-route APP DOMAIN --hostname HOSTNAME                        # Map route
cf unmap-route APP DOMAIN --hostname HOSTNAME                      # Unmap route
cf delete-route DOMAIN --hostname HOSTNAME -f                      # Delete route
```

### SSH Access
```bash
cf ssh financial-dashboard                    # SSH into container
cf ssh financial-dashboard -c "command"       # Run command
```

### Scaling
```bash
cf scale financial-dashboard -i 2             # Scale to 2 instances
cf scale financial-dashboard -m 2G            # Scale memory to 2GB
```

## Production Checklist

Before going to production:

### Security
- [ ] Remove hardcoded credentials from manifest.yml
- [ ] Use cf set-env or bind services for credentials
- [ ] Change SECRET_PHRASE in crypto_utils.py
- [ ] Enable HTTPS (should be default in CF)
- [ ] Review CORS settings
- [ ] Set up proper email alerts (SMTP configuration)

### Performance
- [ ] Increase instances for high availability
- [ ] Adjust memory/disk if needed
- [ ] Enable application autoscaling
- [ ] Configure health checks

### Monitoring
- [ ] Set up log aggregation
- [ ] Configure application monitoring
- [ ] Set up alerting for crashes
- [ ] Monitor HANA connection pool

### Database
- [ ] Create production admin user with strong password
- [ ] Test database connection from CF
- [ ] Verify USERS table exists
- [ ] Backup strategy for HANA

## Deployment Workflow

### For Updates

```bash
# 1. Make changes locally
# 2. Test locally
python3 app.py

# 3. Commit to git
git add .
git commit -m "Your changes"
git push

# 4. Deploy to Cloud Foundry
cf push

# 5. Verify deployment
cf logs financial-dashboard --recent
```

### Zero-Downtime Deployment

```bash
# Push new version without replacing old
cf push financial-dashboard-v2 -n financial-dashboard-v2

# Test new version
curl https://financial-dashboard-v2.cfapps.us10-001.hana.ondemand.com/

# Switch traffic to new version
cf map-route financial-dashboard-v2 cfapps.us10-001.hana.ondemand.com --hostname financial-dashboard
cf unmap-route financial-dashboard cfapps.us10-001.hana.ondemand.com --hostname financial-dashboard

# Delete old version
cf delete financial-dashboard -f

# Rename new version
cf rename financial-dashboard-v2 financial-dashboard
```

## Environment Variables for Production

Instead of hardcoding in manifest.yml:

```bash
# Set HANA credentials
cf set-env financial-dashboard HANA_ADDRESS "your-hana.hanacloud.ondemand.com"
cf set-env financial-dashboard HANA_PORT "443"
cf set-env financial-dashboard HANA_USER "DBADMIN"
cf set-env financial-dashboard HANA_PASSWORD "your-password"
cf set-env financial-dashboard HANA_SCHEMA "BLOOMBERG_DATA"

# Set email configuration
cf set-env financial-dashboard SMTP_SERVER "smtp.gmail.com"
cf set-env financial-dashboard SMTP_PORT "587"
cf set-env financial-dashboard SENDER_EMAIL "alerts@yourcompany.com"
cf set-env financial-dashboard SENDER_PASSWORD "app-password"
cf set-env financial-dashboard ADMIN_EMAIL "admin@yourcompany.com"

# Restage to apply changes
cf restage financial-dashboard
```

## Support

If you continue to have issues:

1. **Check recent logs:**
   ```bash
   cf logs financial-dashboard --recent | tail -100
   ```

2. **SSH in and test:**
   ```bash
   cf ssh financial-dashboard
   python3 -c "import app; print('App loaded successfully')"
   ```

3. **Verify route binding:**
   ```bash
   cf routes | grep financial-dashboard
   ```

4. **Check application health:**
   ```bash
   cf app financial-dashboard
   ```

Your application should now be accessible at:
**https://financial-dashboard.cfapps.us10-001.hana.ondemand.com/**
