# Quick Start - Financial Dashboard

## 🚀 Deploy in 5 Minutes

### Prerequisites Checklist
- ✅ SAP HANA Cloud instance is RUNNING
- ✅ Tables exist: `FINANCIAL_RATIOS` and/or `FINANCIAL_DATA_ADVANCED`
- ✅ Cloud Foundry CLI installed (`cf --version`)
- ✅ SAP BTP account with CF access

---

## Option 1: Local Testing

### Step 1: Clone & Setup (1 min)
```bash
cd bloomberg_hana_integration
git checkout dashboard
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### Step 2: Install (2 min)
```bash
pip install -r requirements.txt
```

### Step 3: Configure (30 sec)
Edit `.env`:
```env
HANA_ADDRESS=your-instance.hana.prod-us10.hanacloud.ondemand.com
HANA_PORT=443
HANA_USER=DBADMIN
HANA_PASSWORD=your_password
HANA_SCHEMA=BLOOMBERG_DATA
```

### Step 4: Run (30 sec)
```bash
python app.py
```

### Step 5: Access (30 sec)
Open browser: `http://localhost:8080`

✅ **Done!** Dashboard should show:
- Summary cards with record counts
- Interactive charts
- Working navigation tabs

---

## Option 2: Cloud Foundry Deployment

### Step 1: Update Config (1 min)
Edit `manifest.yml` - replace placeholders:
```yaml
HANA_ADDRESS: your-actual-instance.hana.prod-us10.hanacloud.ondemand.com
HANA_USER: DBADMIN
HANA_PASSWORD: your_actual_password
HANA_SCHEMA: BLOOMBERG_DATA
```

### Step 2: Login to CF (30 sec)
```bash
cf login -a https://api.cf.us10.hana.ondemand.com
cf target -o your-org -s your-space
```

### Step 3: Deploy (2 min)
```bash
cf push
```

### Step 4: Get URL (30 sec)
```bash
cf apps
```

Look for `urls:` in output, e.g.:
```
urls: financial-dashboard.cfapps.us10.hanacloud.ondemand.com
```

### Step 5: Access (30 sec)
Open the URL in browser

✅ **Done!** Dashboard is live!

---

## Verification Checklist

After deployment, verify:

### ✅ Summary Cards Work
- [ ] Total Records shows a number > 0
- [ ] Unique Companies shows a number > 0
- [ ] Financial Ratios shows a number > 0
- [ ] Last Updated shows recent timestamp

### ✅ Tabs Work
- [ ] **Overview**: Charts render with data
- [ ] **Financial Ratios**: Dropdown has tickers, charts display
- [ ] **Advanced Metrics**: Company selection works
- [ ] **Company Comparison**: Multi-select works, comparison chart shows
- [ ] **Data Explorer**: Table displays rows

### ✅ Interactions Work
- [ ] Auto-refresh happens (wait 5 min, watch data reload)
- [ ] Dropdowns populate correctly
- [ ] Charts are interactive (zoom, pan, hover)
- [ ] Tabs switch instantly

---

## Troubleshooting

### ❌ Empty Dashboard (No Data)

**Symptoms**: Cards show 0 or "N/A"

**Fix**:
```bash
# Test HANA connection
python
>>> from utils.config import load_config
>>> from db.data_service import FinancialDataService
>>> config = load_config()
>>> service = FinancialDataService(config)
>>> service.connect()
True  # Should return True
>>> df = service.get_financial_ratios(limit=10)
>>> len(df)
10  # Should return number of rows
```

**If connection fails**:
1. Check HANA instance is RUNNING (SAP BTP Cockpit)
2. Verify credentials in manifest.yml or .env
3. Check schema name matches
4. Ensure tables exist:
   ```sql
   SELECT COUNT(*) FROM "BLOOMBERG_DATA"."FINANCIAL_RATIOS";
   ```

---

### ❌ App Crashes on Startup

**Symptoms**: `cf app financial-dashboard` shows "crashed"

**Fix**:
```bash
# View logs
cf logs financial-dashboard --recent

# Common issues:
# 1. Wrong HANA credentials → Update manifest.yml
# 2. HANA not running → Start instance in BTP Cockpit
# 3. Missing dependencies → cf restage financial-dashboard
```

---

### ❌ Charts Not Rendering

**Symptoms**: Tabs load but charts are blank

**Fix**:
1. Check browser console (F12) for errors
2. Verify data is being fetched:
   - Summary cards should show counts
   - If counts are 0, it's a data issue
3. Clear browser cache and refresh
4. Try different browser (Chrome recommended)

---

### ❌ Slow Performance

**Symptoms**: Dashboard takes >10 seconds to load

**Fix**:
```bash
# Increase memory
cf scale financial-dashboard -m 2G

# Or increase workers in Procfile:
# Edit Procfile:
web: gunicorn app:server --bind 0.0.0.0:$PORT --workers 8 --timeout 120

# Then re-deploy:
cf push
```

Or reduce data limits in `db/data_service.py`:
```python
def get_financial_ratios(self, limit=50):  # Reduce from 200
```

---

## Configuration Quick Reference

### Environment Variables
| Variable | Example | Required |
|----------|---------|----------|
| HANA_ADDRESS | `abc123.hana.prod-us10.hanacloud.ondemand.com` | Yes |
| HANA_PORT | `443` | Yes |
| HANA_USER | `DBADMIN` | Yes |
| HANA_PASSWORD | `YourPassword123!` | Yes |
| HANA_SCHEMA | `BLOOMBERG_DATA` | Yes |

### Cloud Foundry Commands
```bash
# View logs
cf logs financial-dashboard --recent

# Check status
cf app financial-dashboard

# Restart app
cf restart financial-dashboard

# Scale memory
cf scale financial-dashboard -m 2G

# Scale instances
cf scale financial-dashboard -i 3

# SSH into container
cf ssh financial-dashboard

# Delete app
cf delete financial-dashboard
```

---

## What Tables Do I Need?

### Minimum (For Basic Dashboard)
Just need **FINANCIAL_RATIOS** table:
- TICKER
- IDENTIFIER_TYPE, IDENTIFIER_VALUE
- CUR_RATIO, QUICK_RATIO
- GROSS_MARGIN, EBITDA_MARGIN
- TOT_DEBT_TO_TOT_ASSET
- TIMESTAMP

### Full Dashboard Experience
Both tables:
- **FINANCIAL_RATIOS** (basic metrics)
- **FINANCIAL_DATA_ADVANCED** (80+ advanced metrics)

### How to Create Tables
If tables don't exist, they were created by the data ingestion job.

**Check if tables exist**:
```sql
SELECT * FROM SYS.TABLES
WHERE SCHEMA_NAME = 'BLOOMBERG_DATA'
  AND TABLE_NAME IN ('FINANCIAL_RATIOS', 'FINANCIAL_DATA_ADVANCED');
```

**If missing**: Switch to `main` branch and run ingestion job first:
```bash
git checkout main
python run_job.py  # Ingests data from Bloomberg
```

Then switch back to dashboard:
```bash
git checkout dashboard
cf push
```

---

## Next Steps After Deployment

### 1. Share Dashboard URL
Get URL:
```bash
cf apps
```
Share with team:
```
Dashboard is live!
URL: https://financial-dashboard.cfapps.us10.hanacloud.ondemand.com

Features:
- Real-time financial metrics
- Company comparisons
- Interactive charts
- Auto-refresh every 5 min
```

### 2. Monitor Usage
```bash
# View real-time logs
cf logs financial-dashboard

# Check memory usage
cf app financial-dashboard
```

### 3. Add Authentication (Optional)
For production, add OAuth or Basic Auth:
- See [DASHBOARD_DEPLOYMENT_GUIDE.md](DASHBOARD_DEPLOYMENT_GUIDE.md) Section "Security"

### 4. Customize (Optional)
- Change theme: Edit `app.py` → `dbc.themes.DARKLY`
- Add metrics: Edit dropdown options
- Change colors: Edit color arrays in callbacks
- Adjust refresh: Edit interval component

---

## File Structure Overview

```
bloomberg_hana_integration/
├── app.py                       ← Main dashboard app
├── db/
│   ├── hana_client.py          ← HANA connection
│   └── data_service.py         ← Data queries
├── utils/
│   └── config.py               ← Load config
├── manifest.yml                ← CF deployment config
├── Procfile                    ← Web server config
├── requirements.txt            ← Python dependencies
├── .env                        ← Local credentials
└── DASHBOARD_DEPLOYMENT_GUIDE.md ← Full guide
```

**Key Files to Edit**:
- `manifest.yml`: HANA credentials for CF
- `.env`: HANA credentials for local
- `app.py`: Dashboard customization

---

## Support Resources

📖 **Documentation**:
- [README.md](README.md) - Overview and features
- [DASHBOARD_DEPLOYMENT_GUIDE.md](DASHBOARD_DEPLOYMENT_GUIDE.md) - Complete guide
- [DASHBOARD_FEATURES.md](DASHBOARD_FEATURES.md) - Feature details
- [DASHBOARD_SUMMARY.md](DASHBOARD_SUMMARY.md) - What changed

🔧 **Troubleshooting**:
- Check logs: `cf logs financial-dashboard --recent`
- Verify HANA: Test connection in Python
- Check status: `cf app financial-dashboard`

📊 **Data**:
- Tables: FINANCIAL_RATIOS, FINANCIAL_DATA_ADVANCED
- Schema: BLOOMBERG_DATA
- Source: Bloomberg Data License API (ingestion job)

---

## Common Questions

**Q: Can I run this without Cloud Foundry?**
A: Yes! Use `python app.py` for local deployment on any server.

**Q: How do I update the data?**
A: Data is read-only in dashboard. To update, run ingestion job from `main` branch.

**Q: Can I add more companies?**
A: Yes, add data via ingestion job. Dashboard auto-detects new tickers.

**Q: How do I change the refresh rate?**
A: Edit `app.py` → `dcc.Interval` → `interval=10*60*1000` (10 min)

**Q: Can I export charts?**
A: Yes! Click camera icon on any Plotly chart to save as PNG.

**Q: Is this production-ready?**
A: Yes! Add authentication for public access. Otherwise ready to use.

**Q: How many users can it handle?**
A: 50+ concurrent per instance. Scale with `cf scale -i 3` for more.

**Q: Does it work offline?**
A: No, requires HANA connection. Data refreshes every 5 minutes.

---

## Success!

✅ Dashboard is now live and ready to use!

**What you can do**:
- 📊 View financial metrics in real-time
- 🏢 Compare companies side-by-side
- 📈 Analyze trends and ratios
- 🔍 Explore raw data
- 📱 Access from any device

**Share with team and enjoy!** 🎉
