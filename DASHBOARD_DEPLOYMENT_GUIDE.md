# Financial Dashboard - Deployment Guide

## Overview

This interactive dashboard visualizes Bloomberg financial data stored in SAP HANA Cloud. Built with Plotly Dash, it provides real-time analytics, company comparisons, and comprehensive data exploration.

## Features

### Dashboard Capabilities
- **Overview Tab**: Distribution charts, correlation heatmaps, margin analysis
- **Financial Ratios Tab**: Detailed ratio analysis by company
- **Advanced Metrics Tab**: Profitability, growth, and EPS analysis
- **Company Comparison**: Side-by-side comparison of multiple companies
- **Data Explorer**: Raw data table view with filtering

### Technical Features
- Auto-refresh every 5 minutes
- Responsive design (mobile-friendly)
- Bootstrap-based UI
- Real-time data from SAP HANA Cloud
- Interactive Plotly visualizations

## Prerequisites

1. **SAP HANA Cloud Instance**
   - Instance must be RUNNING
   - Tables must exist: `FINANCIAL_RATIOS` and/or `FINANCIAL_DATA_ADVANCED`
   - Contains data from Bloomberg ingestion

2. **Cloud Foundry CLI**
   ```bash
   cf --version  # Verify installation
   ```

3. **SAP BTP Account**
   - Access to Cloud Foundry environment
   - Sufficient memory quota (1GB minimum)

## Local Development Setup

### Step 1: Install Dependencies

```bash
# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

### Step 2: Configure Environment

Update your `.env` file with HANA credentials:

```env
# SAP HANA Cloud Configuration
HANA_ADDRESS=your-hana-instance.hana.prod-us10.hanacloud.ondemand.com
HANA_PORT=443
HANA_USER=DBADMIN
HANA_PASSWORD=your_hana_password
HANA_SCHEMA=BLOOMBERG_DATA
```

### Step 3: Run Locally

```bash
python app.py
```

The dashboard will be available at: `http://localhost:8080`

### Step 4: Test Locally

1. Navigate to `http://localhost:8080`
2. Verify summary cards display correct counts
3. Test each tab:
   - Overview: Charts should render
   - Financial Ratios: Dropdown should populate with tickers
   - Advanced Metrics: Select a company and view charts
   - Company Comparison: Select 2-5 companies
   - Data Explorer: Table should display data

## Cloud Foundry Deployment

### Step 1: Update Configuration

Edit `manifest.yml` with your HANA credentials:

```yaml
---
applications:
- name: financial-dashboard
  memory: 1024M
  disk_quota: 512M
  instances: 1
  buildpacks:
  - python_buildpack
  command: python app.py
  env:
    HANA_ADDRESS: your-hana-instance.hana.prod-us10.hanacloud.ondemand.com
    HANA_PORT: 443
    HANA_USER: DBADMIN
    HANA_PASSWORD: your_hana_password
    HANA_SCHEMA: BLOOMBERG_DATA
    FLASK_ENV: production
    DASH_DEBUG: false
```

**⚠️ Security Note**: For production, use Cloud Foundry user-provided services instead of hardcoding credentials:

```bash
# Create service with credentials
cf create-user-provided-service hana-creds -p '{"address":"...","port":"443","user":"...","password":"...","schema":"BLOOMBERG_DATA"}'

# Bind to app
cf bind-service financial-dashboard hana-creds
```

Then update `utils/config.py` to read from `VCAP_SERVICES`.

### Step 2: Login to Cloud Foundry

```bash
# Login to SAP BTP
cf login -a https://api.cf.us10.hana.ondemand.com

# Target your org and space
cf target -o your-org -s your-space
```

### Step 3: Push the Application

```bash
# Push to Cloud Foundry
cf push

# Monitor deployment
cf logs financial-dashboard --recent
```

### Step 4: Verify Deployment

```bash
# Check app status
cf app financial-dashboard

# View app URL
cf apps
```

The output will show your dashboard URL, e.g.:
```
name: financial-dashboard
urls: financial-dashboard-happy-elephant.cfapps.us10.hana.ondemand.com
```

### Step 5: Access Dashboard

Open the URL in your browser. You should see:
- Summary cards with record counts
- Interactive charts
- Functional navigation tabs

## Scaling and Performance

### Adjust Memory

```bash
# If you see memory errors, increase allocation
cf scale financial-dashboard -m 2G
```

### Adjust Instances

```bash
# For high traffic, scale horizontally
cf scale financial-dashboard -i 3
```

### Adjust Workers

Edit `Procfile` to change Gunicorn workers:

```
web: gunicorn app:server --bind 0.0.0.0:$PORT --workers 8 --timeout 120
```

Re-push after changes:
```bash
cf push
```

## Monitoring and Logs

### View Real-time Logs

```bash
cf logs financial-dashboard
```

### View Recent Logs

```bash
cf logs financial-dashboard --recent
```

### Check App Health

```bash
cf app financial-dashboard
```

### SSH into Container (if needed)

```bash
cf ssh financial-dashboard
```

## Troubleshooting

### Issue 1: App Crashes on Startup

**Symptoms**: App starts but immediately crashes

**Solutions**:
1. Check logs: `cf logs financial-dashboard --recent`
2. Verify HANA credentials in manifest.yml
3. Ensure HANA instance is RUNNING
4. Check if HANA allows CF IP connections

```bash
# Test HANA connection
cf ssh financial-dashboard
> python
>>> from db.hana_client import HanaClient
>>> from utils.config import load_config
>>> config = load_config()
>>> client = HanaClient(config)
>>> client.connect()
```

### Issue 2: Empty Dashboard / No Data

**Symptoms**: Dashboard loads but shows no data or empty charts

**Solutions**:
1. Verify tables exist in HANA:
   ```sql
   SELECT COUNT(*) FROM "BLOOMBERG_DATA"."FINANCIAL_RATIOS";
   SELECT COUNT(*) FROM "BLOOMBERG_DATA"."FINANCIAL_DATA_ADVANCED";
   ```

2. Check schema name matches in manifest.yml and HANA

3. Verify data was successfully ingested (use old ingestion job)

### Issue 3: Slow Loading

**Symptoms**: Dashboard takes long time to load

**Solutions**:
1. Reduce data limit in `data_service.py`:
   ```python
   def get_financial_ratios(self, limit=50):  # Reduce from 200
   ```

2. Add caching layer (Redis)

3. Increase memory/workers

### Issue 4: Memory Errors

**Symptoms**: `Memory quota exceeded` in logs

**Solutions**:
```bash
# Increase memory allocation
cf scale financial-dashboard -m 2G
```

Or update `manifest.yml`:
```yaml
memory: 2048M
```

### Issue 5: Connection Timeout

**Symptoms**: `HANA connection timeout` errors

**Solutions**:
1. Verify HANA Cloud instance is RUNNING
2. Check HANA firewall rules allow CF connections
3. Get CF outbound IP and whitelist:
   ```bash
   cf ssh financial-dashboard
   > curl https://api.ipify.org
   ```
4. In SAP HANA Cloud Cockpit → Manage Configuration → Connections → Add allowed IP

## Environment Variables Reference

| Variable | Description | Example |
|----------|-------------|---------|
| `HANA_ADDRESS` | SAP HANA Cloud hostname | `abc123.hana.prod-us10.hanacloud.ondemand.com` |
| `HANA_PORT` | SAP HANA port (always 443 for Cloud) | `443` |
| `HANA_USER` | Database user | `DBADMIN` |
| `HANA_PASSWORD` | Database password | `YourSecurePassword123!` |
| `HANA_SCHEMA` | Schema containing tables | `BLOOMBERG_DATA` |
| `FLASK_ENV` | Flask environment | `production` |
| `DASH_DEBUG` | Enable debug mode | `false` |
| `PORT` | Port for web server (auto-set by CF) | `8080` |

## Data Requirements

The dashboard expects the following tables in HANA:

### FINANCIAL_RATIOS (Required)
Minimum columns:
- `TICKER`
- `IDENTIFIER_TYPE`
- `IDENTIFIER_VALUE`
- `CUR_RATIO`
- `QUICK_RATIO`
- `GROSS_MARGIN`
- `EBITDA_MARGIN`
- `TIMESTAMP`

### FINANCIAL_DATA_ADVANCED (Optional)
For advanced metrics tab:
- All columns from `FINANCIAL_DATA_ADVANCED` table
- Key metrics: `NET_INCOME`, `EBITDA`, `EBIT`, `EPS`, etc.

If tables are missing, the dashboard will display empty charts.

## Customization Guide

### Add New Charts

Edit `app.py` and add callback:

```python
@app.callback(
    Output('my-new-chart', 'figure'),
    Input('ratios-data-store', 'data')
)
def update_my_chart(data):
    df = pd.DataFrame(data)

    fig = go.Figure()
    # Your chart logic here

    return fig
```

### Change Refresh Interval

Edit the interval component in `app.py`:

```python
dcc.Interval(
    id='interval-component',
    interval=10*60*1000,  # 10 minutes instead of 5
    n_intervals=0
)
```

### Add New Metrics to Comparison

Edit the dropdown options in `render_comparison_tab()`:

```python
options=[
    {'label': 'New Metric', 'value': 'NEW_METRIC_COLUMN'},
    # ... existing options
]
```

### Customize Theme/Colors

Edit the color scheme in callbacks:

```python
colors = ['#FF5733', '#33FF57', '#3357FF', '#F3FF33']  # Your colors
```

Or use different Bootstrap theme in `app.py`:

```python
external_stylesheets=[dbc.themes.DARKLY]  # Dark theme
```

Available themes: BOOTSTRAP, CERULEAN, COSMO, CYBORG, DARKLY, FLATLY, JOURNAL, LITERA, LUMEN, LUX, MATERIA, MINTY, PULSE, SANDSTONE, SIMPLEX, SKETCHY, SLATE, SOLAR, SPACELAB, SUPERHERO, UNITED, YETI

## Security Best Practices

1. **Never commit credentials**: Use `.gitignore` for `.env` and sensitive files
2. **Use CF services**: Bind HANA credentials via user-provided services
3. **Enable authentication**: Add OAuth or Basic Auth for production
4. **Use HTTPS**: Cloud Foundry provides HTTPS by default
5. **Regular updates**: Keep dependencies updated for security patches

## Maintenance

### Update Dashboard Code

```bash
# Make code changes locally
git add .
git commit -m "Update dashboard features"

# Re-deploy
cf push
```

### Update Dependencies

```bash
# Update requirements.txt
pip freeze > requirements.txt

# Re-deploy
cf push
```

### Backup Configuration

```bash
# Export environment variables
cf env financial-dashboard > env-backup.json
```

## Support and Resources

- **SAP HANA Cloud**: [SAP Help Portal](https://help.sap.com/hana_cloud)
- **Plotly Dash**: [Official Documentation](https://dash.plotly.com/)
- **Cloud Foundry**: [CF CLI Reference](https://docs.cloudfoundry.org/cf-cli/)
- **Bootstrap Components**: [Dash Bootstrap](https://dash-bootstrap-components.opensource.faculty.ai/)

## Next Steps

1. ✅ Deploy dashboard to Cloud Foundry
2. 🔄 Set up authentication (OAuth2/SAML)
3. 📊 Add more advanced visualizations
4. 🔔 Set up alerting for data anomalies
5. 📈 Add time-series analysis features
6. 💾 Implement caching layer (Redis)
7. 📱 Mobile app integration via API
8. 🎨 Custom branding and themes

---

**Dashboard Version**: 1.0.0
**Last Updated**: November 2025
**Maintained By**: Financial Analytics Team
