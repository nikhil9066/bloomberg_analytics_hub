# Deployment Guide - Cloud Foundry Scheduled Job

## Overview

This application runs as a **Cloud Foundry scheduled task** that:
1. Fetches Basic Financial Ratios from Bloomberg → stores in `FINANCIAL_RATIOS` table
2. Fetches Advanced Financial Data from Bloomberg → stores in `FINANCIAL_ADVANCED` table
3. Segregates null values for FINANCIAL_RATIOS and includes them in email for review
4. Sends ONE final summary email with logs attached

**Schedule:** Runs daily at 9:00 AM UTC via CF Scheduler
**No web UI** - This is a scheduled task that executes and terminates automatically.

---

## Prerequisites

1. **Cloud Foundry CLI** installed
   ```bash
   cf --version
   ```

2. **Logged into Cloud Foundry**
   ```bash
   cf login -a <api-endpoint>
   ```

3. **HANA Cloud instance** running in your BTP subaccount

4. **Bloomberg API credentials** (already configured in manifest.yml)

5. **SendGrid account** with API key for email notifications

---

## Configuration

### Update manifest.yml

Edit [`manifest.yml`](manifest.yml) and update:

```yaml
# SAP HANA Cloud Configuration
HANA_ADDRESS: your-actual-hana-instance.hana.prod-us10.hanacloud.ondemand.com
HANA_PASSWORD: your_actual_hana_password
HANA_USER: DBADMIN

# Email Notification Configuration
SENDGRID_API_KEY: SG.your_actual_sendgrid_api_key
SENDGRID_FROM_EMAIL: nikhilpr16+alerts@katbotz.com
NOTIFICATION_EMAIL: nikhilpr16@katbotz.com
```

**Bloomberg credentials** are already configured:
- ✅ `BLOOMBERG_CLIENT_ID`: ad66b6dc591ac1134e0c3d88787d6b41
- ✅ `BLOOMBERG_CLIENT_SECRET`: 3d4cc2242371183a456144aa1ee0030f77930b682d5ff65cc16f2954ba5f5204

---

## Deployment Steps

### Step 1: Install CF Scheduler Plugin (One-Time Setup)

```bash
# Install the CF scheduler plugin
cf install-plugin -r CF-Community "scheduler-for-pcf-cliplugin"

# Verify installation
cf plugins | grep scheduler
```

**Note:** If this fails, check with your SAP BTP administrator to ensure the Scheduler service is enabled in your org/space.

---

### Step 2: Push the Application

```bash
# Push the application (with instances: 0, it won't run continuously)
cf push

# Verify the app is pushed but not running
cf apps
# You should see: bloomberg-hana-job with 0/0 instances
```

---

### Step 3: Create the Scheduled Job

```bash
# Create a job that runs daily at 9:00 AM UTC
cf create-job bloomberg-hana-job bloomberg-daily-9am "python run_job.py"

# Schedule the job (cron format: minute hour day month day-of-week)
# "0 9 * * *" = Every day at 9:00 AM UTC
cf schedule-job bloomberg-daily-9am "0 9 * * *"

# Verify the job is scheduled
cf jobs
```

**Timezone Notes:**
- CF Scheduler uses **UTC** by default
- For 9 AM EST (UTC-5): use `"0 14 * * *"`
- For 9 AM PST (UTC-8): use `"0 17 * * *"`
- For 9 AM IST (UTC+5:30): use `"30 3 * * *"`

---

### Step 4: Monitor and Manage the Job

```bash
# View all scheduled jobs
cf jobs

# View job execution history
cf job-history bloomberg-daily-9am

# View logs from the last execution
cf logs bloomberg-hana-job --recent

# Run the job immediately (for testing)
cf run-job bloomberg-daily-9am

# Delete a scheduled job (if needed)
cf delete-job bloomberg-daily-9am
```

---

## Alternative: One-Time Manual Execution

If you want to run the job manually (outside the schedule):

```bash
# Run as a one-time task
cf run-task bloomberg-hana-job "python run_job.py" --name manual-run

# Monitor the task
cf logs bloomberg-hana-job

# Check task status
cf tasks bloomberg-hana-job
```

---

## Email Notifications

You will receive **ONE comprehensive email** per run with:

### Email Content
**Subject:**
- ✓ Bloomberg Data Ingestion - SUCCESS (if both succeed)
- ⚠ Bloomberg Data Ingestion - PARTIAL SUCCESS (if one fails)
- ✗ Bloomberg Data Ingestion - FAILED (if both fail)

**Body includes:**
- **Summary Table:**
  - FINANCIAL_RATIOS: Status, Rows Inserted, Rows Skipped (nulls)
  - FINANCIAL_ADVANCED: Status, Rows Inserted, Rows Skipped

- **Null Value Warning (if applicable):**
  - Table showing rows with null values in FINANCIAL_RATIOS
  - Requires human intervention for data quality issues

- **Error Details (if applicable):**
  - Specific error messages for each failed step

- **Attachments:**
  - `ingestion_log.txt` - Complete execution logs for debugging

---

## Monitoring

### View Real-Time Logs
```bash
cf logs bloomberg-hana-job
```

### View Recent Logs
```bash
cf logs bloomberg-hana-job --recent
```

### Check Application Status
```bash
cf app bloomberg-hana-job
```

### View Environment Variables
```bash
cf env bloomberg-hana-job
```

---

## Troubleshooting

### Issue 1: Bloomberg API 401 Error

**Error:** "Invalid IP, IP X.X.X.X not allowlisted"

**Solution:**
1. Get your Cloud Foundry app's outbound IP:
   ```bash
   cf ssh bloomberg-hana-job
   curl https://api.ipify.org
   ```
2. Contact Bloomberg support: dlsupport@bloomberg.net
3. Request to allowlist the IP address

### Issue 2: HANA Connection Failed

**Check:**
1. HANA instance is running (BTP Cockpit)
2. HANA credentials are correct in manifest.yml
3. Network connectivity from Cloud Foundry to HANA

### Issue 3: Email Not Received

**Check:**
1. SendGrid API key is valid
2. Check SendGrid dashboard for delivery status
3. Check spam folder
4. Verify `NOTIFICATION_EMAIL` is correct in manifest.yml

### Issue 4: Job Crashes or Times Out

**Solution:**
1. Increase memory in manifest.yml:
   ```yaml
   memory: 2048M
   ```
2. Check logs for specific errors:
   ```bash
   cf logs bloomberg-hana-job --recent | grep ERROR
   ```

---

## Verifying Data in HANA

After the job completes, verify data in HANA:

```sql
-- Check Basic Financial Ratios
SELECT COUNT(*) FROM "BLOOMBERG_DATA"."FINANCIAL_RATIOS";

-- Check Advanced Financial Data
SELECT COUNT(*) FROM "BLOOMBERG_DATA"."FINANCIAL_ADVANCED";

-- Preview Basic data
SELECT * FROM "BLOOMBERG_DATA"."FINANCIAL_RATIOS" LIMIT 5;

-- Preview Advanced data
SELECT * FROM "BLOOMBERG_DATA"."FINANCIAL_ADVANCED" LIMIT 5;
```

You should see:
- **FINANCIAL_RATIOS**: 15 rows (or more if run multiple times)
- **FINANCIAL_ADVANCED**: 15 rows (or more if run multiple times)

---

## Running Locally (for Testing)

Before deploying to Cloud Foundry, test locally:

```bash
# 1. Create .env file with your credentials
cp .env.example .env
# Edit .env and add your credentials

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the job
python run_job.py
```

You should receive email notifications and see logs in the console.

---

## Clean Up

### Delete the Application
```bash
cf delete bloomberg-hana-job
```

### Delete Scheduled Jobs (if using scheduler)
```bash
cf delete-job bloomberg-daily-job
```

---

## Application Structure

```
run_job.py                  # Main job script
├── Step 1: Basic Financial Ratios
│   ├── Fetch from Bloomberg API
│   ├── Store in FINANCIAL_RATIOS table
│   └── Send email notification
└── Step 2: Advanced Financial Data
    ├── Fetch from Bloomberg API
    ├── Store in FINANCIAL_ADVANCED table
    └── Send email notification

utils/email_notifier.py     # Email notification service
api/bloomberg_api.py        # Bloomberg API client (with identifier mapping)
db/hana_client.py           # SAP HANA database client
```

---

## Next Steps

1. ✅ Update HANA credentials in manifest.yml
2. ✅ Update SendGrid credentials in manifest.yml
3. ✅ Contact Bloomberg to allowlist Cloud Foundry IP
4. ⏳ Deploy: `cf push`
5. ⏳ Monitor logs and email notifications
6. ⏳ Verify data in HANA
7. ⏳ (Optional) Set up CF Scheduler for recurring runs

---

**Happy Deploying!** 🚀
