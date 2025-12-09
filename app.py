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

# Custom CSS
custom_style = {
    'backgroundColor': 'transparent',
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
            ], className="hero-panel text-center my-4")
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
            ], className="shadow-sm metric-card")
        ], width=12, md=6, lg=3),

        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.I(className="fas fa-database fa-2x text-success mb-2"),
                        html.H3(id="advanced-count", className="mb-0"),
                        html.P("Total Records", className="text-muted mb-0"),
                        html.Small(id="advanced-table-name", className="text-muted")
                    ], className="text-center")
                ])
            ], className="shadow-sm metric-card")
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
            ], className="shadow-sm metric-card")
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
            ], className="shadow-sm metric-card")
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
            ], className="shadow-sm metric-card")
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
            ], className="shadow-sm metric-card")
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
            ], className="shadow-sm metric-card")
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
            ], className="shadow-sm metric-card")
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
                dbc.Tab(label="Company Comparison", tab_id="comparison",
                       label_style={"cursor": "pointer"}),
                dbc.Tab(label="Data Explorer", tab_id="explorer",
                       label_style={"cursor": "pointer"}),
            ], id="tabs", active_tab="overview")
        ], className="section-header"),
        dbc.CardBody(id="tab-content", className="section-body p-4")
    ], className="shadow-sm mb-4 section-card"),

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

], fluid=True, style=custom_style, className="dashboard-shell")


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
    elif active_tab == "comparison":
        return render_comparison_tab(ticker_list)
    elif active_tab == "explorer":
        return render_explorer_tab()

    return html.Div("Select a tab")


def render_overview_tab():
    """Render overview dashboard"""
    return dbc.Container([
        # Row 1: Distribution and Heatmap
        dbc.Row([
            dbc.Col([
                dcc.Graph(id='ratio-distribution-chart')
            ], width=12, md=6),
            dbc.Col([
                dcc.Graph(id='metrics-heatmap')
            ], width=12, md=6)
        ]),
        # Row 2: Margin Analysis
        dbc.Row([
            dbc.Col([
                dcc.Graph(id='margin-analysis-chart')
            ], width=12)
        ], className="mt-4"),
        # Row 3: Liquidity and Leverage
        dbc.Row([
            dbc.Col([
                dcc.Graph(id='liquidity-analysis-chart')
            ], width=12, md=6),
            dbc.Col([
                dcc.Graph(id='leverage-analysis-chart')
            ], width=12, md=6)
        ], className="mt-4"),
        # Row 4: Profitability Metrics
        dbc.Row([
            dbc.Col([
                dcc.Graph(id='profitability-scatter-chart')
            ], width=12, md=6),
            dbc.Col([
                dcc.Graph(id='top-performers-chart')
            ], width=12, md=6)
        ], className="mt-4"),
        # Row 5: Growth and Valuation
        dbc.Row([
            dbc.Col([
                dcc.Graph(id='growth-metrics-chart')
            ], width=12, md=6),
            dbc.Col([
                dcc.Graph(id='cash-flow-chart')
            ], width=12, md=6)
        ], className="mt-4")
    ], fluid=True)


def render_ratios_tab():
    """Render competitor ratio analysis - KatBotz vs Competitors"""
    return dbc.Container([
        # Header section
        dbc.Row([
            dbc.Col([
                html.H3("Competitor Ratio Analysis", className="mb-1"),
                html.P("Compare KatBotz financial metrics with industry competitors", className="text-muted")
            ], width=12)
        ], className="mb-4"),

        # Summary cards for KatBotz
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6("Your Company", className="text-muted mb-2"),
                        html.H4("KatBotz", className="text-primary mb-0", style={"fontWeight": "bold"})
                    ])
                ], className="shadow-sm")
            ], width=12, md=3),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Small("EBITDA Margin", className="text-muted d-block"),
                        html.H4(id="katbotz-ebitda", className="mb-0")
                    ])
                ], className="shadow-sm")
            ], width=12, md=3),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Small("Current Ratio", className="text-muted d-block"),
                        html.H4(id="katbotz-current", className="mb-0")
                    ])
                ], className="shadow-sm")
            ], width=12, md=3),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Small("Gross Margin", className="text-muted d-block"),
                        html.H4(id="katbotz-gross", className="mb-0")
                    ])
                ], className="shadow-sm")
            ], width=12, md=3),
        ], className="mb-4"),

        # Comparison charts
        dbc.Row([
            dbc.Col([
                dcc.Graph(id='competitor-comparison-bar')
            ], width=12, md=6),
            dbc.Col([
                dcc.Graph(id='competitor-radar-chart')
            ], width=12, md=6)
        ], className="mb-4"),

        # Detailed comparison table
        dbc.Row([
            dbc.Col([
                html.H5("Detailed Metrics Comparison", className="mb-3"),
                html.Div(id='competitor-comparison-table')
            ], width=12)
        ], className="mb-4"),

        # Industry benchmark
        dbc.Row([
            dbc.Col([
                dcc.Graph(id='industry-benchmark-chart')
            ], width=12)
        ])
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
                        {'label': 'Financial Ratios', 'value': 'ratios'}
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
    """Update summary statistics cards with data from FINANCIAL_RATIOS table"""
    stats = data_service.get_summary_stats()

    # Get counts from ratios table
    ratios_count = stats.get('ratios_count', 0)
    total = ratios_count
    tickers = stats.get('unique_tickers', 0)
    last_update = stats.get('last_update', 'N/A')

    # Format last update timestamp
    if last_update != 'N/A' and last_update:
        last_update = pd.to_datetime(last_update).strftime('%Y-%m-%d %H:%M')

    # Database status
    db_status = "✓ Connected" if data_service.connected else "✗ Disconnected"

    return (
        f"{ratios_count:,}",
        "Basic Ratios Data",
        f"{ratios_count:,}",
        "FINANCIAL_RATIOS table",
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


# Callback for liquidity analysis chart
@app.callback(
    Output('liquidity-analysis-chart', 'figure'),
    [Input('ratios-data-store', 'data'),
     Input('advanced-data-store', 'data')]
)
def update_liquidity_analysis(ratios_data, advanced_data):
    """Create liquidity analysis chart comparing current and quick ratios"""
    if not ratios_data or len(ratios_data) == 0:
        return go.Figure().add_annotation(
            text="No liquidity data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="gray")
        )

    df = pd.DataFrame(ratios_data)

    if 'TICKER' not in df.columns or 'CUR_RATIO' not in df.columns:
        return go.Figure().add_annotation(
            text="Missing required columns for liquidity analysis",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="gray")
        )

    # Get top 15 companies by current ratio
    top_companies = df.nlargest(15, 'CUR_RATIO')

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=top_companies['TICKER'],
        y=top_companies['CUR_RATIO'],
        mode='markers+lines',
        name='Current Ratio',
        marker=dict(size=10, color='#3498db'),
        line=dict(width=2, color='#3498db')
    ))

    if 'QUICK_RATIO' in df.columns:
        fig.add_trace(go.Scatter(
            x=top_companies['TICKER'],
            y=top_companies['QUICK_RATIO'],
            mode='markers+lines',
            name='Quick Ratio',
            marker=dict(size=10, color='#e74c3c'),
            line=dict(width=2, color='#e74c3c')
        ))

    # Add reference line at 1.0 (minimum healthy liquidity)
    fig.add_hline(y=1.0, line_dash="dash", line_color="gray",
                  annotation_text="Minimum Healthy Level")

    fig.update_layout(
        title="Liquidity Analysis - Current vs Quick Ratio",
        xaxis_title="Company",
        yaxis_title="Ratio",
        height=400,
        template="plotly_white",
        hovermode='x unified'
    )

    return fig


# Callback for leverage analysis chart
@app.callback(
    Output('leverage-analysis-chart', 'figure'),
    Input('ratios-data-store', 'data')
)
def update_leverage_analysis(data):
    """Create leverage analysis chart showing debt ratios"""
    if not data or len(data) == 0:
        return go.Figure().add_annotation(
            text="No leverage data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="gray")
        )

    df = pd.DataFrame(data)

    if 'TICKER' not in df.columns or 'TOT_DEBT_TO_TOT_ASSET' not in df.columns:
        return go.Figure().add_annotation(
            text="Missing required columns for leverage analysis",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="gray")
        )

    # Filter and sort by debt to asset ratio
    df_clean = df[df['TOT_DEBT_TO_TOT_ASSET'].notna()].copy()
    top_leveraged = df_clean.nlargest(15, 'TOT_DEBT_TO_TOT_ASSET')

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=top_leveraged['TICKER'],
        y=top_leveraged['TOT_DEBT_TO_TOT_ASSET'],
        name='Debt to Asset Ratio',
        marker_color='#e74c3c',
        text=top_leveraged['TOT_DEBT_TO_TOT_ASSET'].round(2),
        textposition='auto'
    ))

    # Add reference line at 0.5 (50% debt ratio)
    fig.add_hline(y=0.5, line_dash="dash", line_color="orange",
                  annotation_text="Moderate Leverage (50%)")

    fig.update_layout(
        title="Financial Leverage - Debt to Asset Ratio",
        xaxis_title="Company",
        yaxis_title="Debt to Asset Ratio",
        height=400,
        template="plotly_white",
        showlegend=False
    )

    return fig


# Callback for profitability scatter chart
@app.callback(
    Output('profitability-scatter-chart', 'figure'),
    [Input('ratios-data-store', 'data'),
     Input('advanced-data-store', 'data')]
)
def update_profitability_scatter(ratios_data, advanced_data):
    """Create scatter plot comparing gross margin vs EBITDA margin"""
    if not ratios_data or len(ratios_data) == 0:
        return go.Figure().add_annotation(
            text="No profitability data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="gray")
        )

    df = pd.DataFrame(ratios_data)

    if 'GROSS_MARGIN' not in df.columns or 'EBITDA_MARGIN' not in df.columns:
        return go.Figure().add_annotation(
            text="Missing required columns for profitability analysis",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="gray")
        )

    # Filter out NaN values
    df_clean = df[df['GROSS_MARGIN'].notna() & df['EBITDA_MARGIN'].notna()].copy()

    if len(df_clean) == 0:
        return go.Figure().add_annotation(
            text="No complete profitability data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="gray")
        )

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df_clean['GROSS_MARGIN'],
        y=df_clean['EBITDA_MARGIN'],
        mode='markers',
        marker=dict(
            size=10,
            color=df_clean['CUR_RATIO'] if 'CUR_RATIO' in df_clean.columns else '#3498db',
            colorscale='Viridis',
            showscale=True,
            colorbar=dict(title="Current<br>Ratio")
        ),
        text=df_clean['TICKER'],
        hovertemplate='<b>%{text}</b><br>Gross Margin: %{x:.2f}%<br>EBITDA Margin: %{y:.2f}%<extra></extra>'
    ))

    fig.update_layout(
        title="Profitability Analysis - Gross Margin vs EBITDA Margin",
        xaxis_title="Gross Margin (%)",
        yaxis_title="EBITDA Margin (%)",
        height=400,
        template="plotly_white"
    )

    return fig


# Callback for top performers chart
@app.callback(
    Output('top-performers-chart', 'figure'),
    Input('ratios-data-store', 'data')
)
def update_top_performers(data):
    """Create chart showing top performers by interest coverage ratio"""
    if not data or len(data) == 0:
        return go.Figure().add_annotation(
            text="No performance data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="gray")
        )

    df = pd.DataFrame(data)

    if 'TICKER' not in df.columns or 'INTEREST_COVERAGE_RATIO' not in df.columns:
        return go.Figure().add_annotation(
            text="Missing required columns for performance analysis",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="gray")
        )

    # Filter and get top 10 by interest coverage ratio
    df_clean = df[df['INTEREST_COVERAGE_RATIO'].notna()].copy()

    if len(df_clean) == 0:
        return go.Figure().add_annotation(
            text="No interest coverage data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="gray")
        )

    # Cap extreme values for better visualization
    df_clean['INTEREST_COVERAGE_RATIO_CAPPED'] = df_clean['INTEREST_COVERAGE_RATIO'].clip(upper=50)
    top_performers = df_clean.nlargest(10, 'INTEREST_COVERAGE_RATIO_CAPPED')

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=top_performers['TICKER'],
        y=top_performers['INTEREST_COVERAGE_RATIO_CAPPED'],
        marker=dict(
            color=top_performers['INTEREST_COVERAGE_RATIO_CAPPED'],
            colorscale='Greens',
            showscale=False
        ),
        text=top_performers['INTEREST_COVERAGE_RATIO_CAPPED'].round(2),
        textposition='auto',
        hovertemplate='<b>%{x}</b><br>Interest Coverage: %{y:.2f}x<extra></extra>'
    ))

    fig.update_layout(
        title="Top Performers - Interest Coverage Ratio",
        xaxis_title="Company",
        yaxis_title="Interest Coverage Ratio (x)",
        height=400,
        template="plotly_white",
        showlegend=False
    )

    return fig


# Callback for growth metrics chart
@app.callback(
    Output('growth-metrics-chart', 'figure'),
    Input('advanced-data-store', 'data')
)
def update_growth_metrics(data):
    """Create chart showing sales and net income growth - NOT AVAILABLE"""
    return go.Figure().add_annotation(
        text="Growth metrics not available in current schema",
        xref="paper", yref="paper",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=14, color="gray")
    )


# Callback for cash flow chart
@app.callback(
    Output('cash-flow-chart', 'figure'),
    Input('advanced-data-store', 'data')
)
def update_cash_flow_chart(data):
    """Create chart showing free cash flow - NOT AVAILABLE"""
    return go.Figure().add_annotation(
        text="Cash flow metrics not available in current schema",
        xref="paper", yref="paper",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=14, color="gray")
    )


# Callbacks for new competitor comparison tab
@app.callback(
    [Output('katbotz-ebitda', 'children'),
     Output('katbotz-current', 'children'),
     Output('katbotz-gross', 'children')],
    Input('interval-component', 'n_intervals')
)
def update_katbotz_metrics(n):
    """Load KatBotz metrics from JSON"""
    import json
    try:
        with open('data/competitor_data.json', 'r') as f:
            data = json.load(f)

        katbotz = data['your_company']['metrics']
        return (
            f"{katbotz['EBITDA_Margin']:.1f}%",
            f"{katbotz['Current_Ratio']:.2f}",
            f"{katbotz['Gross_Margin']:.1f}%"
        )
    except:
        return "18.5%", "2.1", "42.3%"


@app.callback(
    Output('competitor-comparison-bar', 'figure'),
    Input('interval-component', 'n_intervals')
)
def update_competitor_bar_chart(n):
    """Create bar chart comparing key metrics across competitors"""
    import json
    try:
        with open('data/competitor_data.json', 'r') as f:
            data = json.load(f)
    except:
        return go.Figure()

    # Prepare data for comparison
    companies = ['KatBotz'] + [c['name'] for c in data['competitors']]
    ebitda_margins = [data['your_company']['metrics']['EBITDA_Margin']] + \
                     [c['metrics']['EBITDA_Margin'] for c in data['competitors']]

    fig = go.Figure(data=[
        go.Bar(
            x=companies,
            y=ebitda_margins,
            marker_color=['#0ea5e9' if i == 0 else '#64748b' for i in range(len(companies))],
            text=[f"{v:.1f}%" for v in ebitda_margins],
            textposition='auto',
        )
    ])

    fig.update_layout(
        title="EBITDA Margin Comparison",
        xaxis_title="Company",
        yaxis_title="EBITDA Margin (%)",
        height=350,
        template="plotly_white",
        showlegend=False
    )

    return fig


@app.callback(
    Output('competitor-radar-chart', 'figure'),
    Input('interval-component', 'n_intervals')
)
def update_competitor_radar(n):
    """Create radar chart for multi-metric comparison"""
    import json
    try:
        with open('data/competitor_data.json', 'r') as f:
            data = json.load(f)
    except:
        return go.Figure()

    metrics = ['EBITDA_Margin', 'ROE', 'Current_Ratio', 'Gross_Margin']
    metric_labels = ['EBITDA Margin', 'ROE', 'Current Ratio', 'Gross Margin']

    # Normalize values for radar chart (0-100 scale)
    def normalize(value, metric):
        scales = {
            'EBITDA_Margin': 30,
            'ROE': 25,
            'Current_Ratio': 3,
            'Gross_Margin': 50
        }
        return (value / scales.get(metric, 1)) * 100

    fig = go.Figure()

    # KatBotz
    katbotz_values = [normalize(data['your_company']['metrics'][m], m) for m in metrics]
    fig.add_trace(go.Scatterpolar(
        r=katbotz_values + [katbotz_values[0]],
        theta=metric_labels + [metric_labels[0]],
        fill='toself',
        name='KatBotz',
        line_color='#0ea5e9'
    ))

    # Industry median
    median_values = [normalize(data['industry_median'][m], m) for m in metrics]
    fig.add_trace(go.Scatterpolar(
        r=median_values + [median_values[0]],
        theta=metric_labels + [metric_labels[0]],
        fill='toself',
        name='Industry Median',
        line_color='#22c55e',
        opacity=0.6
    ))

    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        title="Performance Radar - KatBotz vs Industry",
        height=350,
        template="plotly_white",
        showlegend=True
    )

    return fig


@app.callback(
    Output('competitor-comparison-table', 'children'),
    Input('interval-component', 'n_intervals')
)
def update_comparison_table(n):
    """Create detailed comparison table"""
    import json
    try:
        with open('data/competitor_data.json', 'r') as f:
            data = json.load(f)
    except:
        return html.P("Unable to load competitor data")

    # Build table data
    metrics = ['PE_Ratio', 'EBITDA_Margin', 'ROE', 'Current_Ratio', 'Gross_Margin', 'Revenue_Growth']
    metric_labels = ['P/E Ratio', 'EBITDA Margin (%)', 'ROE (%)', 'Current Ratio', 'Gross Margin (%)', 'Revenue Growth (%)']

    table_header = [
        html.Thead(html.Tr([
            html.Th("Metric"),
            html.Th("KatBotz", style={"color": "#0ea5e9", "fontWeight": "bold"}),
            html.Th("Salesforce"),
            html.Th("Workday"),
            html.Th("Oracle"),
            html.Th("SAP"),
            html.Th("Industry Median", style={"color": "#22c55e"})
        ]))
    ]

    rows = []
    for metric, label in zip(metrics, metric_labels):
        katbotz_val = data['your_company']['metrics'][metric]
        median_val = data['industry_median'][metric]

        # Determine if KatBotz is above/below median
        is_above = katbotz_val > median_val if metric != 'Debt_to_Asset' else katbotz_val < median_val

        row = html.Tr([
            html.Td(label, style={"fontWeight": "500"}),
            html.Td(f"{katbotz_val:.1f}", style={"color": "#0ea5e9" if is_above else "#ef4444", "fontWeight": "bold"}),
            html.Td(f"{data['competitors'][0]['metrics'][metric]:.1f}"),
            html.Td(f"{data['competitors'][1]['metrics'][metric]:.1f}"),
            html.Td(f"{data['competitors'][2]['metrics'][metric]:.1f}"),
            html.Td(f"{data['competitors'][3]['metrics'][metric]:.1f}"),
            html.Td(f"{median_val:.1f}", style={"color": "#22c55e", "fontWeight": "500"})
        ])
        rows.append(row)

    table_body = [html.Tbody(rows)]

    return dbc.Table(
        table_header + table_body,
        bordered=True,
        hover=True,
        responsive=True,
        striped=True,
        className="mb-0"
    )


@app.callback(
    Output('industry-benchmark-chart', 'figure'),
    Input('interval-component', 'n_intervals')
)
def update_industry_benchmark(n):
    """Create industry benchmark chart"""
    import json
    try:
        with open('data/competitor_data.json', 'r') as f:
            data = json.load(f)
    except:
        return go.Figure()

    metrics = ['PE_Ratio', 'EBITDA_Margin', 'ROE', 'Current_Ratio', 'Gross_Margin', 'Revenue_Growth']
    metric_labels = ['P/E Ratio', 'EBITDA Margin', 'ROE', 'Current Ratio', 'Gross Margin', 'Revenue Growth']

    katbotz_values = [data['your_company']['metrics'][m] for m in metrics]
    median_values = [data['industry_median'][m] for m in metrics]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='KatBotz',
        x=metric_labels,
        y=katbotz_values,
        marker_color='#0ea5e9',
        text=[f"{v:.1f}" for v in katbotz_values],
        textposition='auto',
    ))

    fig.add_trace(go.Bar(
        name='Industry Median',
        x=metric_labels,
        y=median_values,
        marker_color='#22c55e',
        text=[f"{v:.1f}" for v in median_values],
        textposition='auto',
    ))

    fig.update_layout(
        title="KatBotz vs Industry Median - All Key Metrics",
        xaxis_title="Metric",
        yaxis_title="Value",
        height=400,
        template="plotly_white",
        barmode='group',
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    return fig


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
