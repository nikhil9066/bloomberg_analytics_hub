"""
Interactive Financial Dashboard for Bloomberg HANA Data
Provides real-time visualization and analysis of financial metrics
"""

import os
import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd
import logging
from utils.config import load_config, setup_logging
from db.data_service import FinancialDataService

# Initialize logging
logger, log_file = setup_logging()
logger.info("Starting Financial Dashboard Application")

# Load configuration
config = load_config()

# Initialize data service
data_service = FinancialDataService(config)

# Connect to HANA with better error handling
try:
    if not data_service.connect():
        logger.error("Failed to connect to HANA database - check credentials and network connectivity")
        raise ConnectionError(
            "Cannot establish connection to HANA database. "
            "Please verify HANA_ADDRESS, HANA_PORT, HANA_USER, and HANA_PASSWORD environment variables."
        )
    logger.info("Successfully connected to HANA database")
except Exception as e:
    logger.error(f"Database connection error: {str(e)}")
    raise

# Initialize Dash app with Bootstrap theme
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1"}
    ]
)

# For Cloud Foundry deployment
server = app.server
app.title = "Financial Analytics Dashboard"

# Health check endpoint for monitoring
@server.route('/health')
def health_check():
    """Health check endpoint for load balancers and monitoring"""
    from flask import jsonify
    import datetime

    try:
        # Check database connection
        is_connected = data_service.connected

        # Get basic stats to verify database is responsive
        stats = data_service.get_summary_stats() if is_connected else {}

        health_status = {
            'status': 'healthy' if is_connected and stats else 'unhealthy',
            'timestamp': datetime.datetime.now().isoformat(),
            'database': {
                'connected': is_connected,
                'records_available': bool(stats)
            },
            'version': '1.0.0'
        }

        status_code = 200 if is_connected else 503
        return jsonify(health_status), status_code

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.datetime.now().isoformat()
        }), 503

@server.route('/status')
def status():
    """Detailed status endpoint"""
    from flask import jsonify
    import datetime

    try:
        stats = data_service.get_summary_stats()

        return jsonify({
            'application': 'Financial Analytics Dashboard',
            'status': 'running',
            'timestamp': datetime.datetime.now().isoformat(),
            'database': {
                'connected': data_service.connected,
                'schema': config['hana']['schema'],
                'statistics': stats
            }
        }), 200

    except Exception as e:
        logger.error(f"Status check failed: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

# Custom CSS
custom_style = {
    'backgroundColor': '#f8f9fa',
    'fontFamily': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial',
}

# Dashboard Layout
app.layout = dbc.Container([
    # Header
    dbc.Row([
        dbc.Col([
            html.Div([
                html.H1([
                    html.I(className="fas fa-chart-line me-3"),
                    "Financial Analytics Dashboard"
                ], className="text-primary mb-2"),
                html.P("Real-time Bloomberg financial data from SAP HANA",
                       className="text-muted")
            ], className="text-center my-4")
        ])
    ]),

    # Summary Cards - Row 1
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.I(className="fas fa-chart-bar fa-2x text-primary mb-2"),
                        html.H3(id="ratios-count", className="mb-0"),
                        html.P("Basic Ratios Data", className="text-muted mb-0"),
                        html.Small(id="ratios-table-name", className="text-muted")
                    ], className="text-center")
                ])
            ], className="shadow-sm")
        ], width=12, md=6, lg=3),

        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.I(className="fas fa-database fa-2x text-success mb-2"),
                        html.H3(id="advanced-count", className="mb-0"),
                        html.P("Advanced Metrics Data", className="text-muted mb-0"),
                        html.Small(id="advanced-table-name", className="text-muted")
                    ], className="text-center")
                ])
            ], className="shadow-sm")
        ], width=12, md=6, lg=3),

        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.I(className="fas fa-layer-group fa-2x text-info mb-2"),
                        html.H3(id="total-records", className="mb-0"),
                        html.P("Total Data Points", className="text-muted mb-0"),
                        html.Small("All tables combined", className="text-muted")
                    ], className="text-center")
                ])
            ], className="shadow-sm")
        ], width=12, md=6, lg=3),

        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.I(className="fas fa-building fa-2x text-warning mb-2"),
                        html.H3(id="unique-tickers", className="mb-0"),
                        html.P("Unique Companies", className="text-muted mb-0"),
                        html.Small("Tracked in database", className="text-muted")
                    ], className="text-center")
                ])
            ], className="shadow-sm")
        ], width=12, md=6, lg=3),
    ], className="mb-3"),

    # Summary Cards - Row 2
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.I(className="fas fa-clock fa-2x text-secondary mb-2"),
                        html.H6(id="last-update", className="mb-0"),
                        html.P("Last Updated", className="text-muted mb-0"),
                        html.Small("Most recent data", className="text-muted")
                    ], className="text-center")
                ])
            ], className="shadow-sm")
        ], width=12, md=6, lg=3),

        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.I(className="fas fa-server fa-2x text-primary mb-2"),
                        html.H6("SAP HANA Cloud", className="mb-0"),
                        html.P("Database Status", className="text-muted mb-0"),
                        html.Small(id="db-status", className="text-success")
                    ], className="text-center")
                ])
            ], className="shadow-sm")
        ], width=12, md=6, lg=3),

        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.I(className="fas fa-sync fa-2x text-info mb-2"),
                        html.H6("Auto-Refresh", className="mb-0"),
                        html.P("Update Interval", className="text-muted mb-0"),
                        html.Small("Every 5 minutes", className="text-muted")
                    ], className="text-center")
                ])
            ], className="shadow-sm")
        ], width=12, md=6, lg=3),

        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.I(className="fas fa-cloud fa-2x text-success mb-2"),
                        html.H6("Cloud Foundry", className="mb-0"),
                        html.P("Deployment", className="text-muted mb-0"),
                        html.Small("Production Ready", className="text-success")
                    ], className="text-center")
                ])
            ], className="shadow-sm")
        ], width=12, md=6, lg=3),
    ], className="mb-4"),

    # Main Content Tabs
    dbc.Card([
        dbc.CardHeader([
            dbc.Tabs([
                dbc.Tab(label="Overview", tab_id="overview",
                       label_style={"cursor": "pointer"}),
                dbc.Tab(label="Financial Ratios", tab_id="ratios",
                       label_style={"cursor": "pointer"}),
                dbc.Tab(label="Advanced Metrics", tab_id="advanced",
                       label_style={"cursor": "pointer"}),
                dbc.Tab(label="Company Comparison", tab_id="comparison",
                       label_style={"cursor": "pointer"}),
                dbc.Tab(label="Data Explorer", tab_id="explorer",
                       label_style={"cursor": "pointer"}),
            ], id="tabs", active_tab="overview")
        ]),
        dbc.CardBody(id="tab-content", className="p-4")
    ], className="shadow-sm mb-4"),

    # Footer
    dbc.Row([
        dbc.Col([
            html.Hr(),
            html.P([
                "Powered by SAP HANA Cloud | ",
                html.A("Bloomberg Data License", href="#", className="text-decoration-none"),
                " | Built with Plotly Dash"
            ], className="text-center text-muted small")
        ])
    ]),

    # Store components for data caching
    dcc.Store(id='ratios-data-store'),
    dcc.Store(id='advanced-data-store'),
    dcc.Store(id='ticker-list-store'),

    # Auto-refresh interval (every 5 minutes)
    dcc.Interval(
        id='interval-component',
        interval=5*60*1000,  # in milliseconds
        n_intervals=0
    )

], fluid=True, style=custom_style)


# Callbacks for tab content
@app.callback(
    Output("tab-content", "children"),
    Input("tabs", "active_tab"),
    State("ratios-data-store", "data"),
    State("advanced-data-store", "data"),
    State("ticker-list-store", "data")
)
def render_tab_content(active_tab, ratios_data, advanced_data, ticker_list):
    """Render content based on active tab"""

    if active_tab == "overview":
        return render_overview_tab()
    elif active_tab == "ratios":
        return render_ratios_tab()
    elif active_tab == "advanced":
        return render_advanced_tab()
    elif active_tab == "comparison":
        return render_comparison_tab(ticker_list)
    elif active_tab == "explorer":
        return render_explorer_tab()

    return html.Div("Select a tab")


def render_overview_tab():
    """Render overview dashboard"""
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                dcc.Graph(id='ratio-distribution-chart')
            ], width=12, md=6),
            dbc.Col([
                dcc.Graph(id='metrics-heatmap')
            ], width=12, md=6)
        ]),
        dbc.Row([
            dbc.Col([
                dcc.Graph(id='margin-analysis-chart')
            ], width=12)
        ], className="mt-4")
    ], fluid=True)


def render_ratios_tab():
    """Render financial ratios analysis"""
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                html.H5("Select Ticker:"),
                dcc.Dropdown(
                    id='ratios-ticker-dropdown',
                    placeholder="Choose a company...",
                    className="mb-3"
                )
            ], width=12, md=4),
            dbc.Col([
                html.H5("Select Metric:"),
                dcc.Dropdown(
                    id='ratios-metric-dropdown',
                    options=[
                        {'label': 'Debt to Asset Ratio', 'value': 'TOT_DEBT_TO_TOT_ASSET'},
                        {'label': 'Current Ratio', 'value': 'CUR_RATIO'},
                        {'label': 'Quick Ratio', 'value': 'QUICK_RATIO'},
                        {'label': 'Gross Margin', 'value': 'GROSS_MARGIN'},
                        {'label': 'EBITDA Margin', 'value': 'EBITDA_MARGIN'},
                        {'label': 'Interest Coverage Ratio', 'value': 'INTEREST_COVERAGE_RATIO'},
                    ],
                    value='GROSS_MARGIN',
                    className="mb-3"
                )
            ], width=12, md=4)
        ]),
        dbc.Row([
            dbc.Col([
                dcc.Graph(id='ratios-detail-chart')
            ], width=12)
        ])
    ], fluid=True)


def render_advanced_tab():
    """Render advanced metrics analysis"""
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                html.H5("Select Company:"),
                dcc.Dropdown(
                    id='advanced-ticker-dropdown',
                    placeholder="Choose a company...",
                    className="mb-3"
                )
            ], width=12, md=6)
        ]),
        dbc.Row([
            dbc.Col([
                dcc.Graph(id='profitability-chart')
            ], width=12, md=6),
            dbc.Col([
                dcc.Graph(id='growth-chart')
            ], width=12, md=6)
        ]),
        dbc.Row([
            dbc.Col([
                dcc.Graph(id='eps-chart')
            ], width=12)
        ], className="mt-4")
    ], fluid=True)


def render_comparison_tab(ticker_list):
    """Render company comparison view"""
    ticker_options = [{'label': t, 'value': t} for t in (ticker_list or [])]

    return dbc.Container([
        dbc.Row([
            dbc.Col([
                html.H5("Select Companies to Compare:"),
                dcc.Dropdown(
                    id='comparison-tickers-dropdown',
                    options=ticker_options,
                    multi=True,
                    placeholder="Select 2-5 companies...",
                    className="mb-3"
                )
            ], width=12, md=8),
            dbc.Col([
                html.H5("Select Metric:"),
                dcc.Dropdown(
                    id='comparison-metric-dropdown',
                    options=[
                        {'label': 'Gross Margin', 'value': 'GROSS_MARGIN'},
                        {'label': 'EBITDA Margin', 'value': 'EBITDA_MARGIN'},
                        {'label': 'Current Ratio', 'value': 'CUR_RATIO'},
                        {'label': 'Quick Ratio', 'value': 'QUICK_RATIO'},
                    ],
                    value='GROSS_MARGIN',
                    className="mb-3"
                )
            ], width=12, md=4)
        ]),
        dbc.Row([
            dbc.Col([
                dcc.Graph(id='comparison-chart')
            ], width=12)
        ])
    ], fluid=True)


def render_explorer_tab():
    """Render data explorer with table view"""
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                html.H5("Data Table:"),
                dcc.Dropdown(
                    id='explorer-table-dropdown',
                    options=[
                        {'label': 'Financial Ratios', 'value': 'ratios'},
                        {'label': 'Advanced Financials', 'value': 'advanced'}
                    ],
                    value='ratios',
                    className="mb-3"
                )
            ], width=12, md=6),
            dbc.Col([
                html.H5("Records to Display:"),
                dcc.Slider(
                    id='explorer-limit-slider',
                    min=10,
                    max=100,
                    step=10,
                    value=50,
                    marks={i: str(i) for i in range(10, 101, 10)},
                    className="mb-3"
                )
            ], width=12, md=6)
        ]),
        dbc.Row([
            dbc.Col([
                html.Div(id='explorer-table-container')
            ], width=12)
        ])
    ], fluid=True)


# Callback to update summary cards
@app.callback(
    [Output("ratios-count", "children"),
     Output("ratios-table-name", "children"),
     Output("advanced-count", "children"),
     Output("advanced-table-name", "children"),
     Output("total-records", "children"),
     Output("unique-tickers", "children"),
     Output("last-update", "children"),
     Output("db-status", "children")],
    Input('interval-component', 'n_intervals')
)
def update_summary_cards(n):
    """Update summary statistics cards with data from both tables"""
    stats = data_service.get_summary_stats()

    # Get counts from both tables
    ratios_count = stats.get('ratios_count', 0)
    advanced_count = stats.get('advanced_count', 0)
    total = ratios_count + advanced_count
    tickers = stats.get('unique_tickers', 0)
    last_update = stats.get('last_update', 'N/A')

    # Format last update timestamp
    if last_update != 'N/A' and last_update:
        last_update = pd.to_datetime(last_update).strftime('%Y-%m-%d %H:%M')

    # Database status
    db_status = "✓ Connected" if data_service.connected else "✗ Disconnected"

    return (
        f"{ratios_count:,}",
        "FINANCIAL_RATIOS table",
        f"{advanced_count:,}",
        "FINANCIAL_ADVANCED table",
        f"{total:,}",
        f"{tickers:,}",
        str(last_update),
        db_status
    )


# Callback to load data into stores
@app.callback(
    [Output('ratios-data-store', 'data'),
     Output('advanced-data-store', 'data'),
     Output('ticker-list-store', 'data')],
    Input('interval-component', 'n_intervals')
)
def load_data(n):
    """Load data from HANA and store in browser"""
    ratios_df = data_service.get_financial_ratios(limit=200)
    advanced_df = data_service.get_advanced_financials(limit=200)
    tickers = data_service.get_ticker_list()

    return (
        ratios_df.to_dict('records') if not ratios_df.empty else [],
        advanced_df.to_dict('records') if not advanced_df.empty else [],
        tickers
    )


# Callback for ratio distribution chart
@app.callback(
    Output('ratio-distribution-chart', 'figure'),
    Input('ratios-data-store', 'data')
)
def update_ratio_distribution(data):
    """Create distribution chart for key ratios"""
    if not data or len(data) == 0:
        return go.Figure().add_annotation(
            text="No financial ratio data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="gray")
        )

    df = pd.DataFrame(data)

    fig = go.Figure()

    metrics = ['CUR_RATIO', 'QUICK_RATIO', 'GROSS_MARGIN', 'EBITDA_MARGIN']
    colors = ['#3498db', '#2ecc71', '#f39c12', '#e74c3c']

    for metric, color in zip(metrics, colors):
        if metric in df.columns:
            fig.add_trace(go.Box(
                y=df[metric].dropna(),
                name=metric.replace('_', ' ').title(),
                marker_color=color
            ))

    fig.update_layout(
        title="Distribution of Key Financial Ratios",
        yaxis_title="Value",
        height=400,
        showlegend=True,
        template="plotly_white"
    )

    return fig


# Callback for metrics heatmap
@app.callback(
    Output('metrics-heatmap', 'figure'),
    Input('ratios-data-store', 'data')
)
def update_metrics_heatmap(data):
    """Create correlation heatmap for metrics"""
    if not data or len(data) == 0:
        return go.Figure().add_annotation(
            text="No data available for correlation heatmap",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="gray")
        )

    df = pd.DataFrame(data)

    numeric_cols = ['CUR_RATIO', 'QUICK_RATIO', 'GROSS_MARGIN',
                   'EBITDA_MARGIN', 'TOT_DEBT_TO_TOT_ASSET']

    available_cols = [col for col in numeric_cols if col in df.columns]

    if not available_cols or len(available_cols) < 2:
        return go.Figure().add_annotation(
            text="Insufficient metrics for correlation analysis",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="gray")
        )

    corr_matrix = df[available_cols].corr()

    fig = go.Figure(data=go.Heatmap(
        z=corr_matrix.values,
        x=[col.replace('_', ' ') for col in corr_matrix.columns],
        y=[col.replace('_', ' ') for col in corr_matrix.index],
        colorscale='RdBu',
        zmid=0,
        text=corr_matrix.values,
        texttemplate='%{text:.2f}',
        textfont={"size": 10}
    ))

    fig.update_layout(
        title="Metric Correlation Heatmap",
        height=400,
        template="plotly_white"
    )

    return fig


# Callback for margin analysis
@app.callback(
    Output('margin-analysis-chart', 'figure'),
    Input('ratios-data-store', 'data')
)
def update_margin_analysis(data):
    """Create margin analysis chart"""
    if not data or len(data) == 0:
        return go.Figure().add_annotation(
            text="No margin data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="gray")
        )

    df = pd.DataFrame(data)

    if 'TICKER' not in df.columns or 'GROSS_MARGIN' not in df.columns:
        return go.Figure().add_annotation(
            text="Missing required columns for margin analysis",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="gray")
        )

    # Get top 10 companies by gross margin
    top_companies = df.nlargest(10, 'GROSS_MARGIN')

    fig = go.Figure()

    if 'GROSS_MARGIN' in df.columns:
        fig.add_trace(go.Bar(
            x=top_companies['TICKER'],
            y=top_companies['GROSS_MARGIN'],
            name='Gross Margin',
            marker_color='#3498db'
        ))

    if 'EBITDA_MARGIN' in df.columns:
        fig.add_trace(go.Bar(
            x=top_companies['TICKER'],
            y=top_companies['EBITDA_MARGIN'],
            name='EBITDA Margin',
            marker_color='#2ecc71'
        ))

    fig.update_layout(
        title="Top 10 Companies by Margins",
        xaxis_title="Company",
        yaxis_title="Margin (%)",
        barmode='group',
        height=400,
        template="plotly_white"
    )

    return fig


# Callback to update ticker dropdowns
@app.callback(
    [Output('ratios-ticker-dropdown', 'options'),
     Output('advanced-ticker-dropdown', 'options')],
    Input('ticker-list-store', 'data')
)
def update_ticker_dropdowns(tickers):
    """Update ticker dropdown options"""
    options = [{'label': t, 'value': t} for t in (tickers or [])]
    return options, options


# Callback for explorer table
@app.callback(
    Output('explorer-table-container', 'children'),
    [Input('explorer-table-dropdown', 'value'),
     Input('explorer-limit-slider', 'value')]
)
def update_explorer_table(table_type, limit):
    """Update data explorer table"""
    if table_type == 'ratios':
        df = data_service.get_financial_ratios(limit=limit)
    else:
        df = data_service.get_advanced_financials(limit=limit)

    if df is None or df.empty or len(df) == 0:
        return html.Div("No data available", className="text-center text-muted")

    # Create table
    return dbc.Table.from_dataframe(
        df.head(limit),
        striped=True,
        bordered=True,
        hover=True,
        responsive=True,
        size='sm',
        className='table-sm'
    )


# Callback for ratios detail chart
@app.callback(
    Output('ratios-detail-chart', 'figure'),
    [Input('ratios-ticker-dropdown', 'value'),
     Input('ratios-metric-dropdown', 'value')],
    State('ratios-data-store', 'data')
)
def update_ratios_detail_chart(ticker, metric, data):
    """Update detailed ratio chart for selected ticker and metric"""
    if not data or not ticker or not metric:
        return go.Figure().add_annotation(
            text="Please select a company and metric",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="gray")
        )

    df = pd.DataFrame(data)
    ticker_data = df[df['TICKER'] == ticker]

    if ticker_data.empty or metric not in ticker_data.columns:
        return go.Figure().add_annotation(
            text=f"No data available for {ticker}",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="gray")
        )

    fig = go.Figure()
    fig.add_trace(go.Indicator(
        mode="number+gauge",
        value=ticker_data[metric].iloc[0] if not pd.isna(ticker_data[metric].iloc[0]) else 0,
        title={'text': f"{ticker} - {metric.replace('_', ' ').title()}"},
        gauge={'axis': {'range': [None, df[metric].max() * 1.2]},
               'bar': {'color': "#3498db"}}
    ))

    fig.update_layout(height=400, template="plotly_white")
    return fig


# Callback for profitability chart
@app.callback(
    Output('profitability-chart', 'figure'),
    Input('advanced-ticker-dropdown', 'value'),
    State('advanced-data-store', 'data')
)
def update_profitability_chart(ticker, data):
    """Update profitability metrics chart"""
    if not data or not ticker:
        return go.Figure().add_annotation(
            text="Please select a company",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="gray")
        )

    df = pd.DataFrame(data)
    ticker_data = df[df['TICKER'] == ticker]

    if ticker_data.empty:
        return go.Figure().add_annotation(
            text=f"No data available for {ticker}",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="gray")
        )

    metrics = ['GROSS_MARGIN', 'EBITDA_MARGIN', 'OPER_MARGIN', 'PROF_MARGIN']
    values = [ticker_data[m].iloc[0] if m in ticker_data.columns and not pd.isna(ticker_data[m].iloc[0]) else 0
              for m in metrics]
    labels = [m.replace('_', ' ').title() for m in metrics]

    fig = go.Figure(data=[
        go.Bar(x=labels, y=values, marker_color=['#3498db', '#2ecc71', '#f39c12', '#e74c3c'])
    ])

    fig.update_layout(
        title=f"Profitability Margins - {ticker}",
        xaxis_title="Metric",
        yaxis_title="Percentage (%)",
        height=400,
        template="plotly_white"
    )
    return fig


# Callback for growth chart
@app.callback(
    Output('growth-chart', 'figure'),
    Input('advanced-ticker-dropdown', 'value'),
    State('advanced-data-store', 'data')
)
def update_growth_chart(ticker, data):
    """Update growth metrics chart"""
    if not data or not ticker:
        return go.Figure().add_annotation(
            text="Please select a company",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="gray")
        )

    df = pd.DataFrame(data)
    ticker_data = df[df['TICKER'] == ticker]

    if ticker_data.empty:
        return go.Figure().add_annotation(
            text=f"No data available for {ticker}",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="gray")
        )

    metrics = ['SALES_GROWTH', 'NET_INC_GROWTH']
    values = [ticker_data[m].iloc[0] if m in ticker_data.columns and not pd.isna(ticker_data[m].iloc[0]) else 0
              for m in metrics]
    labels = ['Sales Growth', 'Net Income Growth']

    fig = go.Figure(data=[
        go.Bar(x=labels, y=values, marker_color=['#2ecc71', '#9b59b6'])
    ])

    fig.update_layout(
        title=f"Growth Metrics - {ticker}",
        xaxis_title="Metric",
        yaxis_title="Growth Rate (%)",
        height=400,
        template="plotly_white"
    )
    return fig


# Callback for EPS chart
@app.callback(
    Output('eps-chart', 'figure'),
    Input('advanced-ticker-dropdown', 'value'),
    State('advanced-data-store', 'data')
)
def update_eps_chart(ticker, data):
    """Update EPS metrics chart"""
    if not data or not ticker:
        return go.Figure().add_annotation(
            text="Please select a company",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="gray")
        )

    df = pd.DataFrame(data)
    ticker_data = df[df['TICKER'] == ticker]

    if ticker_data.empty:
        return go.Figure().add_annotation(
            text=f"No data available for {ticker}",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="gray")
        )

    metrics = ['IS_EPS', 'IS_DILUTED_EPS', 'EQY_DPS']
    values = [ticker_data[m].iloc[0] if m in ticker_data.columns and not pd.isna(ticker_data[m].iloc[0]) else 0
              for m in metrics]
    labels = ['Basic EPS', 'Diluted EPS', 'Dividend Per Share']

    fig = go.Figure(data=[
        go.Bar(x=labels, y=values, marker_color=['#3498db', '#e74c3c', '#f39c12'])
    ])

    fig.update_layout(
        title=f"Earnings Per Share - {ticker}",
        xaxis_title="Metric",
        yaxis_title="Value ($)",
        height=400,
        template="plotly_white"
    )
    return fig


# Callback for comparison chart
@app.callback(
    Output('comparison-chart', 'figure'),
    [Input('comparison-tickers-dropdown', 'value'),
     Input('comparison-metric-dropdown', 'value')],
    State('ratios-data-store', 'data')
)
def update_comparison_chart(tickers, metric, data):
    """Update company comparison chart"""
    if not data or not tickers or not metric:
        return go.Figure().add_annotation(
            text="Please select 2-5 companies and a metric to compare",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="gray")
        )

    if len(tickers) < 2:
        return go.Figure().add_annotation(
            text="Please select at least 2 companies",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="gray")
        )

    df = pd.DataFrame(data)
    comparison_data = df[df['TICKER'].isin(tickers)]

    if comparison_data.empty or metric not in comparison_data.columns:
        return go.Figure().add_annotation(
            text="No data available for selected companies",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="gray")
        )

    # Group by ticker and get latest value
    latest_data = comparison_data.groupby('TICKER')[metric].first().reset_index()

    fig = go.Figure(data=[
        go.Bar(
            x=latest_data['TICKER'],
            y=latest_data[metric],
            marker_color='#3498db',
            text=latest_data[metric].round(2),
            textposition='auto'
        )
    ])

    fig.update_layout(
        title=f"Company Comparison - {metric.replace('_', ' ').title()}",
        xaxis_title="Company",
        yaxis_title=metric.replace('_', ' ').title(),
        height=400,
        template="plotly_white",
        showlegend=False
    )
    return fig


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    debug = os.getenv('DASH_DEBUG', 'false').lower() == 'true'
    app.run_server(
        host='0.0.0.0',
        port=port,
        debug=debug
    )
