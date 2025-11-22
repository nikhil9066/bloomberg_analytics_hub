# SAP BTP Setup Guide - Manual Steps

This guide covers all the manual steps you need to perform in SAP BTP Cockpit to enable and configure the Bloomberg HANA Integration.

---

## Prerequisites

- SAP BTP Global Account with Cloud Foundry enabled
- Subaccount with Cloud Foundry space created
- User with Space Developer or Admin role

---

## Part 1: Enable CF Scheduler Service (CRITICAL)

The application uses Cloud Foundry Scheduler to run daily at 9 AM. You need to enable this service first.

### Step 1.1: Check if Scheduler is Available

1. **Login to SAP BTP Cockpit**
   - Navigate to: https://cockpit.btp.cloud.sap/
   - Select your Global Account → Subaccount

2. **Navigate to Service Marketplace**
   - In the left menu, click **Services** → **Service Marketplace**
   - Search for **"Application Job Scheduler"** or **"Job Scheduler"**

3. **Verify Service Availability**
   - If you see "Application Job Scheduler" or "Job Scheduler Service" → ✅ Available
   - If you don't see it → ❌ Contact SAP BTP Administrator

### Step 1.2: Create Service Instance (if needed)

**Note:** The CF CLI plugin approach doesn't require this, but some BTP environments do.

1. **Create Service Instance (Optional)**
   ```
   Service: Application Job Scheduler
   Plan: standard (or lite)
   Instance Name: bloomberg-scheduler
   ```

2. **Click "Create"**

---

## Part 2: Setup HANA Cloud Database

### Step 2.1: Create or Verify HANA Instance

1. **Navigate to HANA Cloud**
   - SAP BTP Cockpit → Your Subaccount
   - Click **SAP HANA Cloud** in left menu

2. **Create HANA Instance** (if you don't have one)
   - Click **Create** → **SAP HANA Database**
   - Fill in details:
     - Instance Name: `bloomberg-hana-db`
     - Administrator Password: [Choose a strong password]
     - Memory: 30 GB (minimum recommended)
     - Storage: 120 GB
     - Compute: 2 vCPUs

3. **Start the Instance**
   - Make sure the instance is **RUNNING** (green status)

### Step 2.2: Configure HANA Allowed Connections

By default, HANA Cloud blocks external connections. You need to allow Cloud Foundry to connect.

1. **Get Cloud Foundry IP Range**
   - In CF CLI, run:
     ```bash
     cf app bloomberg-hana-job
     ```
   - Note the route/domain (e.g., `cfapps.us10.hana.ondemand.com`)

2. **Update HANA Connections**
   - In SAP BTP Cockpit → HANA Cloud
   - Click on your HANA instance → **Manage Configuration**
   - Under **Connections**, click **Edit**
   - Select **"Allow all IP addresses"** (for testing)
   - OR specify CF IP ranges (recommended for production)
   - Click **Save**

### Step 2.3: Get HANA Connection Details

You'll need these for the `manifest.yml` file:

1. **Click on your HANA instance**
2. **Copy the following:**
   - **SQL Endpoint** (e.g., `abc123.hana.prod-us10.hanacloud.ondemand.com:443`)
   - **Administrator Username** (usually `DBADMIN`)
   - **Password** (the one you set during creation)

**Update manifest.yml with these values:**
```yaml
HANA_ADDRESS: abc123.hana.prod-us10.hanacloud.ondemand.com
HANA_PORT: 443
HANA_USER: DBADMIN
HANA_PASSWORD: your_secure_password
```

---

## Part 3: Configure SendGrid for Email Notifications

### Step 3.1: Create SendGrid Account

1. **Sign up at SendGrid**
   - Go to: https://sendgrid.com/
   - Create a free account (100 emails/day free tier)

2. **Verify Your Email Address**
   - SendGrid will send verification email
   - Click the link to verify

### Step 3.2: Create API Key

1. **Login to SendGrid Dashboard**
   - Navigate to **Settings** → **API Keys**
   - Click **Create API Key**

2. **Configure API Key**
   - Name: `bloomberg-hana-integration`
   - Permissions: **Full Access** (or at minimum **Mail Send**)
   - Click **Create & View**

3. **Copy the API Key** (you'll only see it once!)
   - Format: `SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

### Step 3.3: Verify Sender Email

1. **Navigate to Sender Authentication**
   - In SendGrid Dashboard → **Settings** → **Sender Authentication**
   - Click **Verify a Single Sender**

2. **Fill in Sender Details**
   - From Email: `nikhilpr16+alerts@katbotz.com` (or your email)
   - From Name: `Bloomberg Integration Alert`
   - Reply To: Your email
   - Company, Address, etc. (required by SendGrid)

3. **Check Your Email**
   - SendGrid sends verification email
   - Click verification link

4. **Update manifest.yml:**
   ```yaml
   SENDGRID_API_KEY: SG.your_actual_api_key_here
   SENDGRID_FROM_EMAIL: nikhilpr16+alerts@katbotz.com
   NOTIFICATION_EMAIL: nikhilpr16@katbotz.com
   ```

---

## Part 4: Configure Cloud Foundry Space

### Step 4.1: Login to Cloud Foundry

```bash
# Login to CF
cf login -a https://api.cf.us10.hana.ondemand.com

# Or use SSO
cf login -a https://api.cf.us10.hana.ondemand.com --sso

# Select your org and space
```

### Step 4.2: Verify Quotas and Limits

```bash
# Check space quota
cf space bloomberg-space

# Check app quotas
cf quotas
```

**Ensure you have:**
- At least 1 GB memory available
- Task execution enabled
- Job scheduler plugin available

---

## Part 5: Bloomberg API Configuration

### Step 5.1: Verify Bloomberg Credentials

You already have these in `manifest.yml`:
```yaml
BLOOMBERG_CLIENT_ID: ad66b6dc591ac1134e0c3d88787d6b41
BLOOMBERG_CLIENT_SECRET: 3d4cc2242371183a456144aa1ee0030f77930b682d5ff65cc16f2954ba5f5204
```

### Step 5.2: Whitelist Cloud Foundry IP (CRITICAL)

Bloomberg API blocks requests from non-whitelisted IPs.

1. **Get Your CF App's Outbound IP:**
   ```bash
   # After deploying the app
   cf ssh bloomberg-hana-job
   curl https://api.ipify.org
   exit
   ```

2. **Contact Bloomberg Support:**
   - Email: `dlsupport@bloomberg.net`
   - Subject: "IP Whitelist Request for Data License API"
   - Body:
     ```
     Hello Bloomberg Support,

     Please whitelist the following IP address for our Data License API access:

     IP Address: [The IP you got from above]
     Client ID: ad66b6dc591ac1134e0c3d88787d6b41
     Company: [Your Company Name]
     Purpose: Automated daily data ingestion to SAP HANA Cloud

     Thank you,
     [Your Name]
     ```

3. **Wait for Confirmation** (usually 1-2 business days)

---

## Part 6: Verify Everything is Ready

### Checklist Before Deployment

- [ ] ✅ CF Scheduler plugin installed: `cf plugins | grep scheduler`
- [ ] ✅ HANA Cloud instance RUNNING
- [ ] ✅ HANA allows CF connections
- [ ] ✅ HANA credentials in manifest.yml
- [ ] ✅ SendGrid API key created
- [ ] ✅ SendGrid sender email verified
- [ ] ✅ SendGrid credentials in manifest.yml
- [ ] ✅ Bloomberg credentials in manifest.yml
- [ ] ✅ Bloomberg IP whitelist requested
- [ ] ✅ CF space has enough quota

---

## Part 7: Deploy and Schedule

Follow the [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for:

1. Push the application: `cf push`
2. Create scheduled job: `cf create-job bloomberg-hana-job bloomberg-daily-9am "python run_job.py"`
3. Schedule for 9 AM: `cf schedule-job bloomberg-daily-9am "0 9 * * *"`
4. Verify: `cf jobs`

---

## Troubleshooting SAP BTP Issues

### Issue 1: "Scheduler plugin not found"

**Solution:**
```bash
# Install the plugin
cf install-plugin -r CF-Community "scheduler-for-pcf-cliplugin"

# If that fails, download manually from:
# https://github.com/cloudfoundry/app-autoscaler-cli-plugin/releases
```

### Issue 2: "Service 'scheduler' not found"

**Cause:** CF Scheduler service not enabled in your BTP org

**Solution:**
1. Contact your SAP BTP Global Account Administrator
2. Ask them to enable "Application Job Scheduler" service
3. Wait for approval and enablement

### Issue 3: HANA Connection Timeout

**Possible Causes:**
- HANA instance not running
- HANA not allowing CF connections
- Wrong HANA credentials

**Solution:**
1. Check HANA instance status in BTP Cockpit
2. Verify HANA allows connections from "All IP addresses"
3. Test credentials using HANA Database Explorer

### Issue 4: "Insufficient resources"

**Cause:** CF space doesn't have enough quota

**Solution:**
```bash
# Check current quota
cf space bloomberg-space

# Request quota increase from BTP admin
```

### Issue 5: Bloomberg API "IP not whitelisted"

**Cause:** Your CF app's IP not whitelisted by Bloomberg

**Solution:**
1. Get CF outbound IP (see Part 5.2)
2. Email Bloomberg support
3. Wait for confirmation (1-2 days)
4. Test again

---

## Need Help?

**SAP BTP Support:**
- SAP Support Portal: https://support.sap.com
- BTP Documentation: https://help.sap.com/docs/btp

**Bloomberg Support:**
- Email: dlsupport@bloomberg.net
- Phone: Check your Bloomberg terminal

**SendGrid Support:**
- Support Center: https://sendgrid.com/support/
- Documentation: https://docs.sendgrid.com/

---

## Next Steps

Once all SAP BTP setup is complete, proceed to:
1. [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - Deploy the application
2. Test the scheduled job with `cf run-job bloomberg-daily-9am`
3. Monitor execution logs with `cf logs bloomberg-hana-job`
4. Check your email for the summary report

---

**Setup Complete! 🎉**

Your Bloomberg to HANA integration will now run automatically every day at 9 AM UTC.
