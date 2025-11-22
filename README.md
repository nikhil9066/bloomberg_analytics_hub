# Financial Analytics Dashboard

**Branch:** `dashboard`

Interactive web-based dashboard for visualizing Bloomberg financial data stored in SAP HANA Cloud. Built with Plotly Dash for real-time analytics and insights.

## Overview

The Financial Analytics Dashboard is a modern web application that:
- Visualizes financial data from SAP HANA Cloud tables
- Provides interactive charts and real-time analytics
- Enables company-to-company comparisons
- Offers comprehensive data exploration tools
- Auto-refreshes data every 5 minutes
- Responsive design for mobile and desktop

## Features

### 📊 Dashboard Views

1. **Overview Tab**
   - Distribution of key financial ratios (box plots)
   - Correlation heatmap for metric relationships
   - Top 10 companies by margin analysis
   - Real-time summary statistics

2. **Financial Ratios Tab**
   - Company-specific ratio analysis
   - Interactive metric selection
   - Historical trend visualization
   - Key liquidity and efficiency ratios

3. **Advanced Metrics Tab**
   - Profitability analysis (EBITDA, Net Income, Gross Profit)
   - Growth metrics (Sales Growth, Net Income Growth)
   - EPS and DPS tracking
   - Comprehensive financial health indicators

4. **Company Comparison**
   - Side-by-side comparison of 2-5 companies
   - Multiple metrics support
   - Visual benchmarking
   - Competitive analysis

5. **Data Explorer**
   - Raw data table view
   - Adjustable record limits
   - Toggle between Financial Ratios and Advanced tables
   - Export-ready format

### 🎨 Technical Features

- **Auto-refresh**: Data updates every 5 minutes
- **Responsive UI**: Bootstrap-based responsive design
- **Interactive Charts**: Plotly visualizations with zoom, pan, hover
- **Real-time Queries**: Direct connection to SAP HANA Cloud
- **Modern Stack**: Dash + Plotly + Bootstrap
- **Cloud-Ready**: Optimized for Cloud Foundry deployment

## Architecture

```
┌─────────────────────┐
│   Web Browser       │
│   (User Interface)  │
└──────────┬──────────┘
           │ HTTP/HTTPS
           ▼
┌─────────────────────┐
│  Dash Application   │
│  (app.py)           │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Data Service Layer  │
│ (data_service.py)   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   HANA Client       │
│ (hana_client.py)    │
└──────────┬──────────┘
           │ hdbcli
           ▼
┌─────────────────────┐
│  SAP HANA Cloud     │
│  - FINANCIAL_RATIOS │
│  - FINANCIAL_DATA_  │
│    ADVANCED         │
└─────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.8+
- SAP HANA Cloud instance with financial data
- Cloud Foundry CLI (for deployment)

### Local Development

1. **Clone and setup**
   ```bash
   git clone <repository>
   cd bloomberg_hana_integration
   git checkout dashboard
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**

   Create `.env` file:
   ```env
   HANA_ADDRESS=your-instance.hana.prod-us10.hanacloud.ondemand.com
   HANA_PORT=443
   HANA_USER=DBADMIN
   HANA_PASSWORD=your_password
   HANA_SCHEMA=BLOOMBERG_DATA
   ```

5. **Run locally**
   ```bash
   python app.py
   ```

6. **Access dashboard**

   Open browser to: `http://localhost:8080`

### Cloud Foundry Deployment

1. **Update manifest.yml** with your HANA credentials

2. **Login to Cloud Foundry**
   ```bash
   cf login -a https://api.cf.us10.hana.ondemand.com
   cf target -o your-org -s your-space
   ```

3. **Deploy**
   ```bash
   cf push
   ```

4. **Access deployed app**
   ```bash
   cf apps  # View app URL
   ```

See [DASHBOARD_DEPLOYMENT_GUIDE.md](DASHBOARD_DEPLOYMENT_GUIDE.md) for complete deployment instructions.

## Data Requirements

The dashboard expects these tables in SAP HANA:

### FINANCIAL_RATIOS (Primary)
- `TICKER` - Stock symbol
- `IDENTIFIER_TYPE` - Identifier type
- `IDENTIFIER_VALUE` - Identifier value
- `TOT_DEBT_TO_TOT_ASSET` - Debt ratio
- `CASH_DVD_COVERAGE` - Dividend coverage
- `TOT_DEBT_TO_EBITDA` - Debt to EBITDA
- `CUR_RATIO` - Current ratio
- `QUICK_RATIO` - Quick ratio
- `GROSS_MARGIN` - Gross margin
- `INTEREST_COVERAGE_RATIO` - Interest coverage
- `EBITDA_MARGIN` - EBITDA margin
- `TIMESTAMP` - Record timestamp

### FINANCIAL_DATA_ADVANCED (Optional)
80+ advanced metrics including:
- Income statement items (NET_INCOME, EBITDA, EBIT)
- EPS metrics (IS_EPS, IS_DILUTED_EPS)
- Growth metrics (SALES_GROWTH, NET_INC_GROWTH)
- Cash flow metrics (CF_FREE_CASH_FLOW)
- And many more...

## Project Structure

```
bloomberg_hana_integration/
├── app.py                          # Main Dash application
├── db/
│   ├── hana_client.py             # HANA database client
│   ├── data_service.py            # Data retrieval service
│   └── __init__.py
├── utils/
│   ├── config.py                  # Configuration loader
│   └── __init__.py
├── requirements.txt               # Python dependencies
├── manifest.yml                   # Cloud Foundry config
├── Procfile                       # Process definition
├── .env                          # Environment variables (local)
├── .env.example                  # Environment template
├── DASHBOARD_DEPLOYMENT_GUIDE.md # Deployment guide
├── README.md                     # This file
└── logs/                         # Application logs
```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `HANA_ADDRESS` | SAP HANA Cloud hostname | Yes |
| `HANA_PORT` | HANA port (usually 443) | Yes |
| `HANA_USER` | Database user | Yes |
| `HANA_PASSWORD` | Database password | Yes |
| `HANA_SCHEMA` | Schema name | Yes |
| `PORT` | Web server port | No (default: 8080) |

### Security Best Practices

1. **Never commit credentials**: Use `.env` (gitignored)
2. **Use CF services**: Bind credentials via user-provided services
3. **HTTPS only**: Cloud Foundry provides HTTPS by default
4. **Add authentication**: Implement OAuth/Basic Auth for production
5. **Regular updates**: Keep dependencies patched

## Customization

### Add New Visualizations

Edit `app.py` and add a callback:

```python
@app.callback(
    Output('my-chart', 'figure'),
    Input('ratios-data-store', 'data')
)
def update_my_chart(data):
    df = pd.DataFrame(data)
    fig = go.Figure()
    # Your visualization logic
    return fig
```

### Change Refresh Interval

Modify the interval component in `app.py`:

```python
dcc.Interval(
    id='interval-component',
    interval=10*60*1000,  # 10 minutes
    n_intervals=0
)
```

### Customize Theme

Use different Bootstrap theme:

```python
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY]  # Dark theme
)
```

Available themes: BOOTSTRAP, CERULEAN, COSMO, DARKLY, FLATLY, JOURNAL, MINTY, SLATE, SOLAR, SUPERHERO, etc.

## Troubleshooting

### Dashboard shows no data

1. Verify HANA connection:
   ```python
   python
   >>> from utils.config import load_config
   >>> from db.data_service import FinancialDataService
   >>> config = load_config()
   >>> service = FinancialDataService(config)
   >>> service.connect()
   True
   ```

2. Check if tables exist and have data:
   ```sql
   SELECT COUNT(*) FROM "BLOOMBERG_DATA"."FINANCIAL_RATIOS";
   ```

3. Verify schema name matches in config

### Connection timeout errors

1. Ensure HANA instance is RUNNING
2. Check HANA firewall allows CF connections
3. Whitelist CF IP in HANA Cloud settings

### Memory errors

Increase memory allocation:
```bash
cf scale financial-dashboard -m 2G
```

### Slow performance

1. Reduce data limits in `data_service.py`
2. Add caching layer (Redis)
3. Increase Gunicorn workers in `Procfile`

See [DASHBOARD_DEPLOYMENT_GUIDE.md](DASHBOARD_DEPLOYMENT_GUIDE.md) for detailed troubleshooting.

## Monitoring

### View Logs
```bash
cf logs financial-dashboard --recent
```

### Check Status
```bash
cf app financial-dashboard
```

### SSH into Container
```bash
cf ssh financial-dashboard
```

## Technology Stack

- **Framework**: Plotly Dash 2.18+
- **UI Components**: Dash Bootstrap Components
- **Visualizations**: Plotly 5.24+
- **Web Server**: Gunicorn
- **Database**: SAP HANA Cloud (hdbcli)
- **Data Processing**: Pandas, NumPy
- **Deployment**: Cloud Foundry

## Performance

- **Load Time**: < 3 seconds (with 100 records)
- **Auto-refresh**: Every 5 minutes
- **Concurrent Users**: Scales with instances
- **Memory**: 1GB (default), scalable to 8GB
- **Workers**: 4 (default), configurable

## Roadmap

- [ ] Add authentication (OAuth2/SAML)
- [ ] Implement caching layer (Redis)
- [ ] Add time-series analysis
- [ ] Export to PDF/Excel
- [ ] Email report scheduling
- [ ] Alert system for anomalies
- [ ] Mobile app API
- [ ] Custom dashboard builder

## Support

For issues or questions:
1. Check [DASHBOARD_DEPLOYMENT_GUIDE.md](DASHBOARD_DEPLOYMENT_GUIDE.md)
2. Review logs: `cf logs financial-dashboard`
3. Verify HANA connection and data
4. Check SAP HANA Cloud status

## Related Documentation

- [DASHBOARD_DEPLOYMENT_GUIDE.md](DASHBOARD_DEPLOYMENT_GUIDE.md) - Complete deployment guide
- [SAP_BTP_SETUP_GUIDE.md](SAP_BTP_SETUP_GUIDE.md) - SAP BTP configuration
- [.env.example](.env.example) - Environment variable template

## License

Internal use only - Financial Analytics Team

---

**Dashboard Version**: 1.0.0
**Last Updated**: November 2025
**Branch**: `dashboard`
