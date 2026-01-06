# Cloud Foundry Deployment Troubleshooting

## Current Status

Your app is successfully staging but crashing on startup with:
```
Instances starting...
type:            web
instances:       0/1
state:           crashed
Start unsuccessful
```

## Recent Changes Made

1. **Switched from Gunicorn to Python Direct Execution**
   - Changed manifest.yml command to: `python app.py`
   - This helps diagnose if the issue is with Gunicorn or the app itself

2. **Added Resilient Error Handling**
   - App now gracefully handles HANA connection failures
   - Will start even if database connections fail
   - Added detailed startup logging

3. **Enhanced Logging**
   - Added startup diagnostic logs to see what's available
   - Will show port, debug mode, and service availability

## Deployment Steps

### 1. Redeploy the Application

```bash
cd /Users/nikhilprao/Documents/bloomberg_analytics_hub

# Login to Cloud Foundry (if not already logged in)
cf login -a https://api.cf.us10-001.hana.ondemand.com

# Push the updated application
cf push

# Watch the logs in real-time
cf logs financial-dashboard
```

### 2. Check Recent Logs

If the app crashes again, immediately check logs:

```bash
cf logs financial-dashboard --recent
```

**Look for:**
- Python errors or stack traces
- HANA connection messages
- "Starting CFO Pulse Dashboard on port..." message
- Any module import errors
- Port binding errors

### 3. Debug with SSH (if app starts but crashes)

```bash
# SSH into the container
cf ssh financial-dashboard

# Navigate to app directory
cd app

# Check Python version
python3 --version

# Test importing the app
python3 -c "import app; print('App loaded')"

# Check if all dependencies are available
python3 -c "import dash, flask, hdbcli, cryptography, pandas; print('All imports OK')"

# Exit
exit
```

### 4. Verify Environment Variables

```bash
cf env financial-dashboard
```

**Check for:**
- PORT (should be set by Cloud Foundry)
- HANA credentials (HANA_ADDRESS, HANA_PORT, HANA_USER, HANA_PASSWORD, HANA_SCHEMA)
- FLASK_ENV=production
- DASH_DEBUG=false

## Common Issues and Solutions

### Issue 1: Missing Files

**Symptom:**
```
FileNotFoundError: [Errno 2] No such file or directory: 'login.html'
```

**Solution:**
Make sure login.html is in the root directory and not excluded by .cfignore

```bash
# Check if .cfignore exists and excludes login.html
cat .cfignore

# If it does, remove that line or delete .cfignore
```

### Issue 2: HANA Connection Timeout

**Symptom:**
```
TimeoutError: Connection to HANA timed out
```

**Solution:**
The app should now handle this gracefully, but verify HANA credentials:

```bash
cf set-env financial-dashboard HANA_ADDRESS "a0b0b370-2621-4f9c-95c3-2063833ac9ef.hana.prod-us10.hanacloud.ondemand.com"
cf set-env financial-dashboard HANA_PORT "443"
cf set-env financial-dashboard HANA_USER "DBADMIN"
cf set-env financial-dashboard HANA_PASSWORD "Qwerty!123456"
cf set-env financial-dashboard HANA_SCHEMA "BLOOMBERG_DATA"

cf restage financial-dashboard
```

### Issue 3: Import Errors

**Symptom:**
```
ModuleNotFoundError: No module named 'xyz'
```

**Solution:**
Check requirements.txt includes all dependencies:

```bash
cat requirements.txt
```

Current dependencies:
- hdbcli==2.23.27
- pandas==2.2.3
- numpy==2.2.3
- dash==2.18.2
- dash-bootstrap-components==1.6.0
- plotly==5.24.1
- gunicorn==23.0.0
- cryptography==43.0.3
- python-dotenv==1.0.1

### Issue 4: Port Binding

**Symptom:**
```
OSError: [Errno 98] Address already in use
```

**Solution:**
The app should use Cloud Foundry's PORT environment variable. Check the code:

```python
port = int(os.environ.get('PORT', 8080))
app.run_server(host='0.0.0.0', port=port, debug=False)
```

### Issue 5: Secret Key or Session Issues

**Symptom:**
```
RuntimeError: The session is unavailable because no secret key was set
```

**Solution:**
The app now generates a secret key automatically:
```python
server.secret_key = secrets.token_hex(32)
```

## Step-by-Step Diagnosis

Run these commands in order:

```bash
# 1. Check app status
cf apps

# 2. If crashed, get recent logs
cf logs financial-dashboard --recent | tail -100

# 3. Check if route exists
cf routes | grep financial-dashboard

# 4. Check environment variables
cf env financial-dashboard | grep -E "PORT|HANA|FLASK"

# 5. Check events
cf events financial-dashboard

# 6. Try to restart (if it started before)
cf restart financial-dashboard

# 7. If still failing, check staging logs
cf logs financial-dashboard --recent | grep -i "staging\|error"
```

## Expected Successful Startup Logs

When the app starts successfully, you should see:

```
2024-xx-xx INFO Starting CFO Pulse Dashboard on port 8080
2024-xx-xx INFO Debug mode: false
2024-xx-xx INFO Authentication service initialized successfully
2024-xx-xx INFO Data service initialized and connected to HANA
2024-xx-xx INFO Authentication service available: True
2024-xx-xx INFO Data service available: True
 * Serving Flask app 'app'
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:8080
 * Running on http://x.x.x.x:8080
```

## What to Share for Further Debugging

If the app still crashes, share:

1. **Full recent logs:**
```bash
cf logs financial-dashboard --recent > cf_logs.txt
```

2. **App info:**
```bash
cf app financial-dashboard > app_info.txt
```

3. **Environment variables (redact passwords):**
```bash
cf env financial-dashboard > env_info.txt
# Edit env_info.txt to remove sensitive data before sharing
```

4. **Route information:**
```bash
cf routes | grep financial-dashboard
```

## Rollback Strategy

If the new version doesn't work, you can try using Gunicorn again:

**Edit manifest.yml:**
```yaml
command: gunicorn app:server --bind 0.0.0.0:$PORT --workers 4 --timeout 120 --access-logfile - --error-logfile -
```

Then:
```bash
cf push
```

## Alternative: Try Procfile Instead of Manifest Command

Create a `Procfile` in the root (already exists):
```
web: python app.py
```

Then remove the `command:` line from manifest.yml and push again.

## Next Steps After Successful Deployment

Once the app starts successfully:

1. **Initialize the database:**
```bash
cf ssh financial-dashboard
python3 admin_user_manager.py
# Create USERS table and admin user
exit
```

2. **Test the application:**
```bash
curl https://financial-dashboard.cfapps.us10-001.hana.ondemand.com/
# Should redirect to /login
```

3. **Test login:**
- Navigate to: https://financial-dashboard.cfapps.us10-001.hana.ondemand.com/
- Login with: admin@g.com / admin
- Should redirect to dashboard

## Support Checklist

Before asking for help, verify:

- [ ] Latest code is pushed to Cloud Foundry (`cf push`)
- [ ] All dependencies in requirements.txt
- [ ] login.html exists in root directory
- [ ] HANA credentials are correct in manifest.yml
- [ ] Recent logs captured (`cf logs financial-dashboard --recent`)
- [ ] App status checked (`cf app financial-dashboard`)
- [ ] Routes verified (`cf routes`)

## Quick Reference Commands

```bash
# Deploy
cf push

# Watch logs
cf logs financial-dashboard

# Recent logs
cf logs financial-dashboard --recent

# App status
cf app financial-dashboard

# Restart
cf restart financial-dashboard

# SSH access
cf ssh financial-dashboard

# Delete and redeploy
cf delete financial-dashboard -f
cf push

# Scale
cf scale financial-dashboard -i 2  # 2 instances
cf scale financial-dashboard -m 2G # 2GB memory
```

## Success Indicators

✅ App status shows: `state: started`
✅ Instances shows: `instances: 1/1`
✅ URL is accessible: https://financial-dashboard.cfapps.us10-001.hana.ondemand.com/
✅ Login page loads
✅ Can authenticate and reach dashboard
