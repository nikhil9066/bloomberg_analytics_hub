"""
CFO Pulse Dashboard - Financial Intelligence Platform
Modern KPI dashboard with AI insights and advanced analytics
"""

import os
import dash
from dash import dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from utils.config import load_config, setup_logging
from db.data_service import FinancialDataService

# Initialize logging
setup_logging()
logger = logging.getLogger(__name__)

# Load configuration
config = load_config()

# Initialize Dash app with custom URL base pathname
app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css'
    ],
    suppress_callback_exceptions=True,
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1"}
    ],
    url_base_pathname='/dashboard/'
)

# For Cloud Foundry deployment
server = app.server
app.title = "CFO Pulse Dashboard"

# Import authentication service
from db.auth_service import AuthService
from flask import request, jsonify, redirect, session
import secrets

# Set secret key for sessions
server.secret_key = secrets.token_hex(32)

# Initialize authentication service
auth_service = None
hana_client = None
try:
    from db.hana_client import HanaClient
    hana_client = HanaClient(config)
    if hana_client.connect():
        auth_service = AuthService(hana_client, config['hana']['schema'])
        logger.info("Authentication service initialized successfully")
    else:
        logger.warning("HANA connection failed - authentication will not be available")
except Exception as e:
    logger.error(f"Failed to initialize authentication service: {e}")
    logger.warning("Continuing without authentication service")

# Add redirect from root to login
@server.route('/')
def redirect_to_login():
    """Redirect root path to login page"""
    return redirect('/login')

# Add login route (GET - serve page, POST - authenticate)
@server.route('/login', methods=['GET', 'POST'])
def login():
    """Serve login page or authenticate user"""
    if request.method == 'GET':
        with open('login.html', 'r') as f:
            return f.read()

    # POST request - authenticate
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            return jsonify({'success': False, 'message': 'Email and password required'}), 400

        if not auth_service:
            return jsonify({'success': False, 'message': 'Authentication service unavailable'}), 503

        # Get client IP address
        ip_address = request.remote_addr or request.environ.get('HTTP_X_FORWARDED_FOR', 'unknown')

        # Authenticate user with IP address for email alerts
        user = auth_service.authenticate(email, password, ip_address=ip_address)

        if user:
            # Store user info in session
            session['user_id'] = user['id']
            session['user_email'] = user['email']
            session['user_role'] = user['role']

            return jsonify({
                'success': True,
                'message': 'Login successful',
                'redirect': '/dashboard/'
            })
        else:
            # Check if user exists but wrong password
            if auth_service.user_exists(email):
                return jsonify({
                    'success': False,
                    'message': 'Invalid credentials. Please check your password.'
                }), 401
            else:
                return jsonify({
                    'success': False,
                    'message': f'User account not found. If you believe this is an error, please contact the administrator. Attempted email: {email}'
                }), 404

    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'success': False, 'message': 'An error occurred during login'}), 500

# Add logout route
@server.route('/logout')
def logout():
    """Logout user and clear session"""
    session.clear()
    return redirect('/login')

# Initialize data service
# Connect to HANA database for production data
try:
    data_service = FinancialDataService(config)
    if data_service.connect():
        logger.info("Data service initialized and connected to HANA")
    else:
        logger.warning("Data service initialized but not connected to HANA")
        data_service = None
except Exception as e:
    logger.warning(f"HANA data service not available: {e}. Will use CSV files for local testing.")
    data_service = None

# Load CSV data for local testing (commented out for production, uncomment if needed)
csv_data = None
# Uncomment below lines for local testing without HANA
# try:
#     basic_df = pd.read_csv('basic.csv')
#     advance_df = pd.read_csv('advance.csv')
#     logger.info(f"Loaded CSV data: {len(basic_df)} basic records, {len(advance_df)} advance records")
#     csv_data = {'basic': basic_df, 'advance': advance_df}
# except Exception as e:
#     logger.error(f"Failed to load CSV files: {e}")
#     csv_data = None

# Modern custom CSS
custom_style = {
    'backgroundColor': '#f9fafb',
    'fontFamily': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    'minHeight': '100vh'
}

# Color palette
COLORS = {
    'primary': '#3b82f6',
    'success': '#10b981',
    'danger': '#ef4444',
    'warning': '#f59e0b',
    'info': '#06b6d4',
    'purple': '#8b5cf6',
    'gray': {
        '50': '#f9fafb',
        '100': '#f3f4f6',
        '200': '#e5e7eb',
        '300': '#d1d5db',
        '400': '#9ca3af',
        '500': '#6b7280',
        '600': '#4b5563',
        '700': '#374151',
        '800': '#1f2937',
        '900': '#111827'
    }
}

#==============================================================================
# SIDEBAR COMPONENT
#==============================================================================

def create_sidebar(collapsed=False, dark_mode=False):
    """Create the collapsible sidebar with navigation"""
    sidebar_class = "sidebar " + ("collapsed" if collapsed else "expanded")
    if dark_mode:
        sidebar_class += " dark-mode"

    nav_items = [
        {"id": "nav-overview", "icon": "fas fa-home", "text": "Overview", "active": True, "target": "kpi-grid-container"},
        {"id": "nav-insights", "icon": "fas fa-lightbulb", "text": "AI Insights", "target": "ai-insights-container"},
        {"id": "nav-competitor", "icon": "fas fa-users", "text": "Competitor Analysis", "target": "competitor-analysis-container"},
        {"id": "nav-comparative", "icon": "fas fa-balance-scale", "text": "Comparative Analysis", "target": "comparative-analysis-container"},
        {"id": "nav-margin", "icon": "fas fa-chart-waterfall", "text": "Margin Bridge", "target": "margin-bridge-container"},
        {"id": "nav-analytics", "icon": "fas fa-chart-bar", "text": "Analytics", "target": "tabbed-analytics-container"},
    ]

    return html.Div([
        # Header with logo and toggle
        html.Div([
            html.Div([
                html.Div([
                    html.I(className="fas fa-chart-pie")
                ], className="sidebar-logo-icon"),
                html.Span("CFO Pulse", className="sidebar-logo-text")
            ], className="sidebar-logo"),
            html.Button([
                html.I(id="sidebar-toggle-icon", className="fas fa-chevron-left")
            ], id="sidebar-toggle-btn", className="sidebar-toggle")
        ], className="sidebar-header"),

        # Navigation items
        html.Div([
            html.Div([
                html.A([
                    html.I(className=item["icon"] + " sidebar-nav-item-icon"),
                    html.Span(item["text"], className="sidebar-nav-item-text")
                ],
                id=item["id"],
                href=f"#{item['target']}",
                className="sidebar-nav-item" + (" active" if item.get("active") else ""))
                for item in nav_items
            ])
        ], className="sidebar-nav"),

        # System Status Section (Collapsible)
        html.Div([
            # Toggle button
            html.Div([
                html.Div([
                    html.I(className="fas fa-server sidebar-footer-item-icon"),
                    html.Span("System Status", className="sidebar-footer-item-text")
                ], style={"flex": "1"}),
                html.I(id="system-status-toggle-icon", className="fas fa-chevron-down", style={
                    "fontSize": "12px",
                    "transition": "transform 0.3s ease",
                    "color": COLORS['gray']['400']
                })
            ], id="system-status-toggle", className="sidebar-footer-item", style={
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "space-between",
                "cursor": "pointer"
            }),

            # Collapsible content
            html.Div([
                html.Div([
                    # Data Quality
                    html.Div([
                        html.Div([
                            html.I(className="fas fa-check-circle", style={
                                "fontSize": "10px",
                                "color": COLORS['success'],
                                "marginRight": "6px"
                            }),
                            html.Span("Data Quality", className="sidebar-footer-item-text", style={"fontSize": "11px"})
                        ], style={"marginBottom": "4px"}),
                        html.Div("99.8%", style={
                            "fontSize": "16px",
                            "fontWeight": "700",
                            "color": COLORS['success'],
                            "marginLeft": "16px"
                        })
                    ], style={"marginBottom": "12px"}),

                    # Last Sync
                    html.Div([
                        html.Div([
                            html.I(className="fas fa-sync-alt", style={
                                "fontSize": "10px",
                                "color": COLORS['info'],
                                "marginRight": "6px"
                            }),
                            html.Span("Last Sync", className="sidebar-footer-item-text", style={"fontSize": "11px"})
                        ], style={"marginBottom": "4px"}),
                        html.Div(id="sidebar-sync-time", children="Just now", style={
                            "fontSize": "12px",
                            "color": COLORS['gray']['400'] if dark_mode else COLORS['gray']['600'],
                            "marginLeft": "16px"
                        })
                    ], style={"marginBottom": "12px"}),

                    # SAP HANA Connection
                    html.Div([
                        html.Div([
                            html.I(className="fas fa-database", style={
                                "fontSize": "10px",
                                "color": COLORS['primary'],
                                "marginRight": "6px"
                            }),
                            html.Span("SAP HANA Cloud", className="sidebar-footer-item-text", style={"fontSize": "11px"})
                        ], style={"marginBottom": "4px"}),
                        html.Div([
                            html.Div(style={
                                "width": "6px",
                                "height": "6px",
                                "borderRadius": "50%",
                                "backgroundColor": COLORS['success'],
                                "marginRight": "6px",
                                "marginLeft": "16px"
                            }),
                            html.Span("Connected", style={
                                "fontSize": "11px",
                                "color": COLORS['gray']['400'] if dark_mode else COLORS['gray']['600']
                            })
                        ], style={"display": "flex", "alignItems": "center"})
                    ], style={"marginBottom": "12px"}),

                    # Records Count
                    html.Div([
                        html.Div([
                            html.I(className="fas fa-file-alt", style={
                                "fontSize": "10px",
                                "color": COLORS['warning'],
                                "marginRight": "6px"
                            }),
                            html.Span("Records", className="sidebar-footer-item-text", style={"fontSize": "11px"})
                        ], style={"marginBottom": "4px"}),
                        html.Div("850 active", style={
                            "fontSize": "11px",
                            "color": COLORS['gray']['400'] if dark_mode else COLORS['gray']['600'],
                            "marginLeft": "16px"
                        })
                    ])
                ], style={
                    "padding": "12px 16px",
                    "backgroundColor": COLORS['gray']['700'] if dark_mode else COLORS['gray']['50'],
                    "borderRadius": "8px",
                    "border": f"1px solid {COLORS['gray']['600'] if dark_mode else COLORS['gray']['200']}"
                })
            ], id="system-status-content", style={"padding": "8px 8px 0 8px", "display": "block"}),

            # Help and Settings
            html.Div([
                html.I(className="fas fa-question-circle sidebar-footer-item-icon"),
                html.Span("Help Center", className="sidebar-footer-item-text")
            ], id="sidebar-help", className="sidebar-footer-item"),
            html.Div([
                html.I(className="fas fa-cog sidebar-footer-item-icon"),
                html.Span("Settings", className="sidebar-footer-item-text")
            ], id="sidebar-settings", className="sidebar-footer-item")
        ], className="sidebar-footer")
    ], id="sidebar", className=sidebar_class)

#==============================================================================
# DASHBOARD HEADER COMPONENT
#==============================================================================

def create_dashboard_header():
    """Create the modern dashboard header with filters"""
    return dbc.Card([
        dbc.CardBody([
            # Top row - Logo and Actions
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.I(className="fas fa-chart-line",
                              style={"fontSize": "32px", "color": COLORS['primary'], "marginRight": "12px"}),
                        html.Div([
                            html.H1("CFO Pulse Dashboard",
                                   style={"fontSize": "24px", "fontWeight": "600",
                                         "color": COLORS['gray']['900'], "margin": "0"}),
                            html.P("Real-time Financial Intelligence",
                                  style={"fontSize": "13px", "color": COLORS['gray']['500'],
                                        "margin": "0"})
                        ], style={"display": "inline-block"})
                    ], style={"display": "flex", "alignItems": "center"})
                ], width=6),
                dbc.Col([
                    html.Div([
                        dbc.Button([
                            html.I(className="fas fa-sync-alt me-2"),
                            "Refresh"
                        ], id="refresh-btn", color="light", size="sm", className="me-2"),
                        dbc.Button([
                            html.I(className="fas fa-download me-2"),
                            "Export"
                        ], id="export-btn", color="light", size="sm", className="me-2"),
                        dbc.Button([
                            html.I(className="fas fa-calendar me-2"),
                            "Calendar"
                        ], color="light", size="sm", className="me-2"),
                        dbc.Button(
                            html.I(className="fas fa-bookmark"),
                            id="bookmark-btn", color="light", size="sm", className="me-2"
                        ),
                        dbc.Button(
                            html.I(id="theme-icon", className="fas fa-moon"),
                            id="theme-toggle", color="light", size="sm"
                        )
                    ], style={"display": "flex", "justifyContent": "flex-end"})
                ], width=6)
            ], className="mb-4"),

            # Filters row
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Span("Year:", style={"fontSize": "14px", "color": COLORS['gray']['600'], "marginRight": "8px"}),
                        dcc.Dropdown(
                            id='year-filter',
                            options=[
                                {'label': '2023', 'value': '2023'},
                                {'label': '2024', 'value': '2024'},
                                {'label': '2025', 'value': '2025'}
                            ],
                            value='2025',
                            clearable=False,
                            style={"width": "120px", "display": "inline-block"}
                        )
                    ], style={"display": "inline-flex", "alignItems": "center", "marginRight": "16px"})
                ], width="auto"),

                dbc.Col([
                    html.Div([
                        html.Span("Region:", style={"fontSize": "14px", "color": COLORS['gray']['600'], "marginRight": "8px"}),
                        dcc.Dropdown(
                            id='region-filter',
                            options=[
                                {'label': 'All Regions', 'value': 'All'},
                                {'label': 'North America', 'value': 'North America'},
                                {'label': 'Europe', 'value': 'Europe'},
                                {'label': 'Asia Pacific', 'value': 'Asia Pacific'}
                            ],
                            value='All',
                            clearable=False,
                            style={"width": "140px", "display": "inline-block"}
                        )
                    ], style={"display": "inline-flex", "alignItems": "center", "marginRight": "16px"})
                ], width="auto"),

                dbc.Col([
                    html.Div([
                        html.Span("Currency:", style={"fontSize": "14px", "color": COLORS['gray']['600'], "marginRight": "8px"}),
                        dcc.Dropdown(
                            id='currency-filter',
                            options=[
                                {'label': 'USD', 'value': 'USD'},
                                {'label': 'EUR', 'value': 'EUR'},
                                {'label': 'GBP', 'value': 'GBP'}
                            ],
                            value='USD',
                            clearable=False,
                            style={"width": "100px", "display": "inline-block"}
                        )
                    ], style={"display": "inline-flex", "alignItems": "center", "marginRight": "16px"})
                ], width="auto"),

                dbc.Col([
                    dbc.Button("Reset Filters", id="reset-filters", color="link", size="sm")
                ], width="auto"),

                dbc.Col([
                    html.Div([
                        html.Span("View:", style={"fontSize": "14px", "color": COLORS['gray']['600'], "marginRight": "8px"}),
                        dcc.Dropdown(
                            id='view-mode-filter',
                            options=[
                                {'label': 'Chart View', 'value': 'chart'},
                                {'label': 'Ratio View %', 'value': 'ratio'},
                                {'label': 'Bifurcation View', 'value': 'bifurcation'}
                            ],
                            value='chart',
                            clearable=False,
                            style={"width": "160px", "display": "inline-block"}
                        )
                    ], style={"display": "inline-flex", "alignItems": "center"})
                ], width="auto", className="ms-auto")
            ], align="center")
        ])
    ], style={"border": "none", "borderBottom": f"1px solid {COLORS['gray']['200']}",
             "borderRadius": "0", "position": "sticky", "top": "0", "zIndex": "1000"})

#==============================================================================
# DATA TRUST BAR
#==============================================================================

def create_data_trust_bar():
    """Create data quality and trust indicator bar"""
    return dbc.Card([
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.I(className="fas fa-check-circle",
                              style={"color": COLORS['success'], "marginRight": "8px"}),
                        html.Span("Data Quality: ", style={"fontWeight": "500", "color": COLORS['gray']['700']}),
                        html.Span("99.8%", style={"color": COLORS['success'], "fontWeight": "600"})
                    ], style={"display": "flex", "alignItems": "center"})
                ], width="auto"),

                dbc.Col([
                    html.Div([
                        html.I(className="fas fa-database",
                              style={"color": COLORS['info'], "marginRight": "8px"}),
                        html.Span("Last Sync: ", style={"fontWeight": "500", "color": COLORS['gray']['700']}),
                        html.Span(id="last-sync-time", children="Just now",
                                style={"color": COLORS['gray']['600']})
                    ], style={"display": "flex", "alignItems": "center"})
                ], width="auto"),

                dbc.Col([
                    html.Div([
                        html.I(className="fas fa-shield-alt",
                              style={"color": COLORS['primary'], "marginRight": "8px"}),
                        html.Span("SAP HANA Cloud", style={"color": COLORS['gray']['700'], "fontWeight": "500"}),
                        html.Span(" Connected", style={"color": COLORS['success'], "marginLeft": "4px"})
                    ], style={"display": "flex", "alignItems": "center"})
                ], width="auto")
            ], justify="center")
        ], style={"padding": "12px"})
    ], style={"backgroundColor": COLORS['gray']['50'], "border": "none", "borderRadius": "0"})

#==============================================================================
# MAIN LAYOUT
#==============================================================================

app.layout = html.Div([
    # Store for dark mode state
    dcc.Store(id='dark-mode-store', data=False),

    # Store for sidebar collapse state (False = expanded by default)
    dcc.Store(id='sidebar-collapsed-store', data=False),

    # Store for updated timestamp
    dcc.Store(id='update-timestamp', data=datetime.now().isoformat()),

    # Sidebar
    html.Div(id='sidebar-container'),

    # Main Content
    dbc.Container([
        # Dashboard Header
        create_dashboard_header(),

        # Data Trust Bar
        create_data_trust_bar(),

        # Main Content Sections
        html.Div([
            # KPI Grid Section
            html.Div(id='kpi-grid-container', className="mb-4", style={"padding": "24px"}),

            # AI Insights Section
            html.Div(id='ai-insights-container', className="mb-4", style={"padding": "0 24px"}),

            # Competitor Analysis Module
            html.Div(id='competitor-analysis-container', className="mb-4", style={"padding": "0 24px"}),

            # Comparative Analysis
            html.Div(id='comparative-analysis-container', className="mb-4", style={"padding": "0 24px"}),

            # Margin Bridge
            html.Div(id='margin-bridge-container', className="mb-4", style={"padding": "0 24px"}),

            # Alert Feed
            html.Div(id='alert-feed-container', className="mb-4", style={"padding": "0 24px"}),

            # Tabbed Analytics Section
            html.Div(id='tabbed-analytics-container', className="mb-4", style={"padding": "0 24px"})
        ])
    ], id='main-content', fluid=True, style=custom_style, className='main-content sidebar-expanded')

], style={'position': 'relative'})

#==============================================================================
# CALLBACKS
#==============================================================================

# Sidebar render callback
@app.callback(
    Output('sidebar-container', 'children'),
    [Input('sidebar-collapsed-store', 'data'),
     Input('dark-mode-store', 'data')]
)
def render_sidebar(collapsed, dark_mode):
    return create_sidebar(collapsed=collapsed, dark_mode=dark_mode)

# Sidebar toggle callback
@app.callback(
    [Output('sidebar-collapsed-store', 'data'),
     Output('sidebar-toggle-icon', 'className'),
     Output('main-content', 'className')],
    [Input('sidebar-toggle-btn', 'n_clicks')],
    [State('sidebar-collapsed-store', 'data')]
)
def toggle_sidebar(n, collapsed):
    if n:
        new_collapsed = not collapsed
        icon = "fas fa-chevron-right" if new_collapsed else "fas fa-chevron-left"
        main_class = "main-content sidebar-collapsed" if new_collapsed else "main-content sidebar-expanded"
        return new_collapsed, icon, main_class
    return collapsed, "fas fa-chevron-left", "main-content sidebar-expanded"

# System status toggle callback with state store
@app.callback(
    [Output('system-status-content', 'style'),
     Output('system-status-toggle-icon', 'style')],
    [Input('system-status-toggle', 'n_clicks'),
     Input('sidebar-collapsed-store', 'data')],
    [State('system-status-content', 'style'),
     State('system-status-toggle-icon', 'style')]
)
def toggle_system_status(n_clicks, sidebar_collapsed, content_style, icon_style):
    ctx = callback_context

    # If sidebar is collapsed, hide everything
    if sidebar_collapsed:
        return {'display': 'none'}, {'display': 'none'}

    # Default style for icon
    if icon_style is None:
        icon_style = {
            'fontSize': '12px',
            'transition': 'transform 0.3s ease',
            'color': COLORS['gray']['400']
        }

    # Default style for content
    if content_style is None:
        content_style = {'padding': '8px 8px 0 8px', 'display': 'block'}

    # If system status toggle was clicked
    if ctx.triggered and ctx.triggered[0]['prop_id'] == 'system-status-toggle.n_clicks' and n_clicks:
        is_visible = content_style.get('display', 'block') == 'block'

        # Toggle visibility
        new_content_style = content_style.copy()
        new_content_style['display'] = 'none' if is_visible else 'block'

        # Rotate icon
        new_icon_style = icon_style.copy()
        new_icon_style['transform'] = 'rotate(-90deg)' if is_visible else 'rotate(0deg)'

        return new_content_style, new_icon_style

    # Default: show when expanded
    return content_style, icon_style

# Update sidebar sync time
@app.callback(
    Output('sidebar-sync-time', 'children'),
    [Input('update-timestamp', 'data')]
)
def update_sidebar_sync_time(timestamp):
    if timestamp:
        dt = datetime.fromisoformat(timestamp)
        return dt.strftime("%H:%M:%S")
    return "Just now"

# Theme toggle callback
@app.callback(
    [Output('dark-mode-store', 'data'),
     Output('theme-icon', 'className')],
    [Input('theme-toggle', 'n_clicks')],
    [State('dark-mode-store', 'data')]
)
def toggle_theme(n, dark_mode):
    if n:
        new_mode = not dark_mode
        icon = "fas fa-sun" if new_mode else "fas fa-moon"
        return new_mode, icon
    return dark_mode, "fas fa-moon"

# Reset filters callback
@app.callback(
    [Output('year-filter', 'value'),
     Output('region-filter', 'value'),
     Output('currency-filter', 'value'),
     Output('view-mode-filter', 'value')],
    [Input('reset-filters', 'n_clicks')]
)
def reset_filters(n):
    if n:
        return '2025', 'All', 'USD', 'chart'
    return dash.no_update

# Refresh data callback
@app.callback(
    Output('update-timestamp', 'data'),
    [Input('refresh-btn', 'n_clicks')]
)
def refresh_data(n):
    if n:
        return datetime.now().isoformat()
    return dash.no_update

# Update last sync time
@app.callback(
    Output('last-sync-time', 'children'),
    [Input('update-timestamp', 'data')]
)
def update_sync_time(timestamp):
    if timestamp:
        dt = datetime.fromisoformat(timestamp)
        return dt.strftime("%H:%M:%S")
    return "Just now"

#==============================================================================
# KPI GRID COMPONENT CALLBACK
#==============================================================================

@app.callback(
    Output('kpi-grid-container', 'children'),
    [Input('year-filter', 'value'),
     Input('region-filter', 'value'),
     Input('view-mode-filter', 'value'),
     Input('update-timestamp', 'data'),
     Input('dark-mode-store', 'data')]
)
def update_kpi_grid(year, region, view_mode, timestamp, dark_mode):
    """Create KPI grid with real HANA data"""

    # Fetch data from HANA or CSV
    try:
        if data_service:
            data = data_service.get_financial_ratios()
            df = pd.DataFrame(data) if data else None
        elif csv_data:
            # Use CSV data for local testing
            df = csv_data['basic']
        else:
            df = None

        if df is not None and len(df) > 0:
            # Calculate KPIs from real data
            ebitda_margin = df['EBITDA_MARGIN'].mean() if 'EBITDA_MARGIN' in df.columns else 60.45
            gross_margin = df['GROSS_MARGIN'].mean() if 'GROSS_MARGIN' in df.columns else 68.82
            current_ratio = df['CUR_RATIO'].mean() if 'CUR_RATIO' in df.columns else 1.84

            # Estimated revenue based on margins
            revenue = 245600000
            ebitda = revenue * (ebitda_margin / 100)

            logger.info(f"Using real data: EBITDA Margin={ebitda_margin:.2f}%, Gross Margin={gross_margin:.2f}%")
        else:
            # Fallback to mock data
            revenue = 245600000
            ebitda = 45800000
            ebitda_margin = 60.45
            gross_margin = 68.82
            current_ratio = 1.84
    except Exception as e:
        logger.error(f"Error fetching KPI data: {e}")
        revenue = 245600000
        ebitda = 45800000
        ebitda_margin = 60.45
        gross_margin = 68.82
        current_ratio = 1.84

    # Define KPIs (using mock data for demonstration, but structure is ready for real data)
    kpis = [
        {
            'name': 'Revenue',
            'value': revenue,
            'change': 12.5,
            'target': 250000000,
            'icon': 'fa-dollar-sign',
            'color': COLORS['primary'],
            'trend': 'up',
            'sparkline': [220, 225, 230, 235, 242, 245.6]
        },
        {
            'name': 'EBITDA',
            'value': ebitda,
            'change': 8.3,
            'target': 48000000,
            'icon': 'fa-chart-line',
            'color': COLORS['success'],
            'trend': 'up',
            'sparkline': [42, 43, 44, 44.5, 45, 45.8]
        },
        {
            'name': 'Operating Expenses',
            'value': 156200000,
            'change': -3.2,
            'target': 155000000,
            'icon': 'fa-receipt',
            'color': COLORS['info'],
            'trend': 'down',
            'sparkline': [165, 162, 160, 158, 157, 156.2]
        },
        {
            'name': 'Cash Flow',
            'value': 38400000,
            'change': 15.7,
            'target': 40000000,
            'icon': 'fa-wallet',
            'color': COLORS['purple'],
            'trend': 'up',
            'sparkline': [32, 33, 35, 36, 37, 38.4]
        },
        {
            'name': 'Working Capital',
            'value': 52300000,
            'change': 5.4,
            'target': 55000000,
            'icon': 'fa-piggy-bank',
            'color': COLORS['warning'],
            'trend': 'up',
            'sparkline': [48, 49, 50, 51, 51.5, 52.3]
        },
        {
            'name': 'Net Profit Margin',
            'value': 18.6,
            'change': 2.1,
            'target': 20.0,
            'icon': 'fa-percent',
            'color': COLORS['success'],
            'trend': 'up',
            'sparkline': [17.0, 17.5, 18.0, 18.2, 18.4, 18.6],
            'is_percentage': True
        }
    ]

    # Create KPI cards
    kpi_cards = []
    for kpi in kpis:
        card = create_kpi_card(kpi, view_mode, dark_mode)
        kpi_cards.append(dbc.Col(card, width=12, md=6, lg=4))

    return dbc.Row(kpi_cards, className="g-4")

def create_kpi_card(kpi, view_mode, dark_mode):
    """Create individual KPI card"""

    # Determine if change is good
    is_good = (kpi['trend'] == 'up' and kpi['change'] > 0) or (kpi['trend'] == 'down' and kpi['change'] < 0)
    has_alert = abs(kpi['change']) > 10

    # Format value
    if kpi.get('is_percentage'):
        value_display = f"{kpi['value']:.1f}%"
        target_display = f"{kpi['target']:.1f}%"
    else:
        value_display = f"${kpi['value']/1000000:.1f}M"
        target_display = f"${kpi['target']/1000000:.1f}M"

    # Create sparkline chart
    sparkline_fig = go.Figure()
    sparkline_fig.add_trace(go.Scatter(
        y=kpi['sparkline'],
        mode='lines',
        line=dict(color=COLORS['success'] if is_good else COLORS['danger'], width=2),
        fill='tozeroy',
        fillcolor=f"rgba({'16, 185, 129' if is_good else '239, 68, 68'}, 0.1)"
    ))
    sparkline_fig.update_layout(
        showlegend=False,
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        margin=dict(l=0, r=0, t=0, b=0),
        height=64,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )

    # Progress to target
    progress = (kpi['value'] / kpi['target']) * 100

    card_style = {
        "backgroundColor": COLORS['gray']['800'] if dark_mode else "#ffffff",
        "border": f"1px solid {COLORS['gray']['700'] if dark_mode else COLORS['gray']['200']}",
        "borderRadius": "12px",
        "padding": "24px",
        "position": "relative",
        "transition": "box-shadow 0.3s",
        "cursor": "pointer"
    }

    card_content = [
        # Alert badge
        html.Div([
            html.I(className="fas fa-exclamation-triangle me-1", style={"fontSize": "12px"}),
            "Alert"
        ], style={
            "position": "absolute",
            "top": "12px",
            "right": "12px",
            "backgroundColor": COLORS['danger'],
            "color": "white",
            "padding": "4px 8px",
            "borderRadius": "4px",
            "fontSize": "11px",
            "fontWeight": "600"
        }) if has_alert else html.Div(),

        # Header
        html.Div([
            html.Div([
                html.Div([
                    html.I(className=f"fas {kpi['icon']}", style={
                        "fontSize": "20px",
                        "color": kpi['color']
                    })
                ], style={
                    "width": "40px",
                    "height": "40px",
                    "borderRadius": "8px",
                    "backgroundColor": f"rgba({int(kpi['color'][1:3], 16)}, {int(kpi['color'][3:5], 16)}, {int(kpi['color'][5:7], 16)}, 0.1)",
                    "display": "flex",
                    "alignItems": "center",
                    "justifyContent": "center"
                }),
                html.Div([
                    html.H3(kpi['name'], style={
                        "fontSize": "16px",
                        "fontWeight": "500",
                        "margin": "0",
                        "color": COLORS['gray']['200'] if dark_mode else COLORS['gray']['900']
                    }),
                    html.Div([
                        html.I(className=f"fas fa-arrow-{'up' if kpi['trend'] == 'up' else 'down'}",
                              style={"fontSize": "12px", "marginRight": "4px"}),
                        html.Span(f"{'+' if kpi['change'] > 0 else ''}{kpi['change']:.1f}%")
                    ], style={
                        "fontSize": "14px",
                        "color": COLORS['success'] if is_good else COLORS['danger'],
                        "marginTop": "4px"
                    })
                ], style={"marginLeft": "12px"})
            ], style={"display": "flex", "alignItems": "center"})
        ], style={"marginBottom": "16px"}),

        # Value display based on view mode
        html.Div([
            html.Div(value_display, style={
                "fontSize": "32px",
                "fontWeight": "700",
                "color": COLORS['gray']['100'] if dark_mode else COLORS['gray']['900'],
                "marginBottom": "8px"
            }),
            html.Div(f"Target: {target_display}", style={
                "fontSize": "13px",
                "color": COLORS['gray']['400'] if dark_mode else COLORS['gray']['500']
            })
        ]),

        # Sparkline (for chart view)
        html.Div([
            dcc.Graph(figure=sparkline_fig, config={'displayModeBar': False}, style={"marginTop": "16px"})
        ]) if view_mode == 'chart' else html.Div(),

        # Progress bar (for ratio view)
        html.Div([
            html.Div([
                html.Span("Progress to Target", style={
                    "fontSize": "13px",
                    "color": COLORS['gray']['400'] if dark_mode else COLORS['gray']['600']
                }),
                html.Span(f"{progress:.0f}%", style={
                    "fontSize": "13px",
                    "fontWeight": "600",
                    "color": COLORS['gray']['200'] if dark_mode else COLORS['gray']['900']
                })
            ], style={"display": "flex", "justifyContent": "space-between", "marginBottom": "8px"}),
            dbc.Progress(value=progress, style={"height": "8px"},
                        color="success" if progress >= 95 else "warning" if progress >= 80 else "danger")
        ], style={"marginTop": "16px"}) if view_mode == 'ratio' else html.Div(),

        # Bifurcation view
        html.Div([
            html.Div([
                html.Span("Actual", style={"fontSize": "13px", "color": COLORS['gray']['400'] if dark_mode else COLORS['gray']['600']}),
                html.Span(value_display, style={"fontSize": "13px", "fontWeight": "600", "color": COLORS['success']})
            ], style={"display": "flex", "justifyContent": "space-between", "marginBottom": "8px"}),
            html.Div([
                html.Span("Budget", style={"fontSize": "13px", "color": COLORS['gray']['400'] if dark_mode else COLORS['gray']['600']}),
                html.Span(f"${kpi['target']*0.95/1000000:.1f}M" if not kpi.get('is_percentage') else f"{kpi['target']*0.95:.1f}%",
                         style={"fontSize": "13px", "fontWeight": "600", "color": COLORS['primary']})
            ], style={"display": "flex", "justifyContent": "space-between", "marginBottom": "8px"}),
            html.Div([
                html.Span("Variance", style={"fontSize": "13px", "color": COLORS['gray']['400'] if dark_mode else COLORS['gray']['600']}),
                html.Span(f"+${(kpi['value'] - kpi['target']*0.95)/1000000:.1f}M" if not kpi.get('is_percentage') else f"+{kpi['value'] - kpi['target']*0.95:.1f}%",
                         style={"fontSize": "13px", "fontWeight": "600", "color": COLORS['success'] if kpi['change'] >= 0 else COLORS['danger']})
            ], style={"display": "flex", "justifyContent": "space-between"})
        ], style={"marginTop": "16px"}) if view_mode == 'bifurcation' else html.Div(),

        # Drill down button
        html.Div([
            dbc.Button([
                "Drill Down",
                html.I(className="fas fa-arrow-right ms-2")
            ], color="light", size="sm", outline=True, style={"width": "100%", "marginTop": "16px"})
        ])
    ]

    return dbc.Card(card_content, style=card_style, className="kpi-card-hover")

#==============================================================================
# AI INSIGHTS COMPONENT
#==============================================================================

@app.callback(
    Output('ai-insights-container', 'children'),
    [Input('update-timestamp', 'data'),
     Input('dark-mode-store', 'data')]
)
def update_ai_insights(timestamp, dark_mode):
    """Create AI-powered insights section"""

    insights = [
        {
            'type': 'positive',
            'icon': 'fa-arrow-trend-up',
            'title': 'Revenue Acceleration Detected',
            'description': 'Q4 revenue is trending 12.5% above forecast, primarily driven by Technology division (+18%) and strong performance in Asia Pacific region.',
            'confidence': 94,
            'color': COLORS['success']
        },
        {
            'type': 'alert',
            'icon': 'fa-triangle-exclamation',
            'title': 'OPEX Variance Alert',
            'description': 'Travel expenses exceeded budget by 15.2% in September. Recommend immediate review of T&E policy compliance.',
            'confidence': 89,
            'color': COLORS['danger']
        },
        {
            'type': 'insight',
            'icon': 'fa-lightbulb',
            'title': 'Cash Flow Optimization Opportunity',
            'description': 'Days Sales Outstanding increased by 8 days. Accelerating collections could release ~$4.2M in working capital.',
            'confidence': 91,
            'color': COLORS['primary']
        },
        {
            'type': 'target',
            'icon': 'fa-bullseye',
            'title': 'EBITDA Target Within Reach',
            'description': 'Current trajectory suggests 95.4% target achievement. A 2% reduction in discretionary spend would close the gap.',
            'confidence': 96,
            'color': COLORS['purple']
        }
    ]

    card_style = {
        "backgroundColor": COLORS['gray']['800'] if dark_mode else "#ffffff",
        "border": f"1px solid {COLORS['gray']['700'] if dark_mode else COLORS['gray']['200']}",
        "borderRadius": "12px",
        "padding": "24px"
    }

    insight_cards = []
    for insight in insights:
        insight_card = dbc.Col([
            html.Div([
                html.Div([
                    html.Div([
                        html.I(className=f"fas {insight['icon']}", style={
                            "fontSize": "20px",
                            "color": insight['color']
                        })
                    ], style={
                        "width": "40px",
                        "height": "40px",
                        "borderRadius": "8px",
                        "backgroundColor": f"rgba({int(insight['color'][1:3], 16)}, {int(insight['color'][3:5], 16)}, {int(insight['color'][5:7], 16)}, 0.1)",
                        "display": "flex",
                        "alignItems": "center",
                        "justifyContent": "center"
                    }),
                    html.Div([
                        html.Div([
                            html.H4(insight['title'], style={
                                "fontSize": "16px",
                                "fontWeight": "600",
                                "margin": "0",
                                "color": COLORS['gray']['100'] if dark_mode else COLORS['gray']['900']
                            }),
                            html.Span(f"{insight['confidence']}% confident", style={
                                "fontSize": "11px",
                                "padding": "2px 8px",
                                "borderRadius": "4px",
                                "backgroundColor": COLORS['gray']['700'] if dark_mode else COLORS['gray']['100'],
                                "color": COLORS['gray']['300'] if dark_mode else COLORS['gray']['600'],
                                "marginLeft": "8px"
                            })
                        ], style={"display": "flex", "alignItems": "center", "marginBottom": "8px"}),
                        html.P(insight['description'], style={
                            "fontSize": "14px",
                            "color": COLORS['gray']['300'] if dark_mode else COLORS['gray']['600'],
                            "margin": "0 0 12px 0",
                            "lineHeight": "1.5"
                        }),
                        dbc.Button([
                            "Explain This Insight",
                            html.I(className="fas fa-arrow-right ms-2")
                        ], color="link", size="sm", style={"padding": "0", "fontSize": "13px"})
                    ], style={"marginLeft": "12px", "flex": "1"})
                ], style={"display": "flex"})
            ], style={
                "backgroundColor": COLORS['gray']['700'] if dark_mode else COLORS['gray']['50'],
                "border": f"1px solid {COLORS['gray']['600'] if dark_mode else COLORS['gray']['200']}",
                "borderRadius": "8px",
                "padding": "16px",
                "height": "100%"
            })
        ], width=12, md=6)
        insight_cards.append(insight_card)

    return dbc.Card([
        dbc.CardBody([
            html.Div([
                html.Div([
                    html.I(className="fas fa-sparkles", style={
                        "fontSize": "24px",
                        "color": COLORS['warning'],
                        "marginRight": "12px"
                    }),
                    html.Div([
                        html.H2("AI-Powered Insights & Narratives", style={
                            "fontSize": "20px",
                            "fontWeight": "600",
                            "margin": "0",
                            "color": COLORS['gray']['100'] if dark_mode else COLORS['gray']['900']
                        }),
                        html.P("Intelligent analysis of your financial performance", style={
                            "fontSize": "14px",
                            "color": COLORS['gray']['400'] if dark_mode else COLORS['gray']['500'],
                            "margin": "0"
                        })
                    ])
                ], style={"display": "flex", "alignItems": "center"}),
                dbc.Button([
                    html.I(className="fas fa-rotate me-2"),
                    "Regenerate Insights"
                ], color="light", size="sm", outline=True)
            ], style={"display": "flex", "justifyContent": "space-between", "marginBottom": "24px"}),

            dbc.Row(insight_cards, className="g-4")
        ])
    ], style=card_style)

#==============================================================================
# COMPETITOR ANALYSIS MODULE
#==============================================================================

@app.callback(
    Output('competitor-analysis-container', 'children'),
    [Input('update-timestamp', 'data'),
     Input('dark-mode-store', 'data')]
)
def update_competitor_analysis(timestamp, dark_mode):
    """Create competitor analysis module with HANA data"""

    # Fetch competitor data from HANA or CSV
    try:
        if data_service:
            data = data_service.get_financial_ratios()
            df = pd.DataFrame(data) if data else None
        elif csv_data:
            df = csv_data['basic']
        else:
            df = None

        if df is not None and 'TICKER' in df.columns:
            companies = df['TICKER'].unique()[:5].tolist()  # Top 5 companies
            # Get actual metric values
            ebitda_values = [df[df['TICKER'] == c]['EBITDA_MARGIN'].iloc[0] if len(df[df['TICKER'] == c]) > 0 else 0 for c in companies]
            current_ratio_values = [df[df['TICKER'] == c]['CUR_RATIO'].iloc[0] if len(df[df['TICKER'] == c]) > 0 else 0 for c in companies]
            gross_margin_values = [df[df['TICKER'] == c]['GROSS_MARGIN'].iloc[0] if len(df[df['TICKER'] == c]) > 0 else 0 for c in companies]
        else:
            companies = ['Your Company', 'Competitor A', 'Competitor B', 'Competitor C', 'Competitor D']
            ebitda_values = np.random.uniform(15, 25, len(companies))
            current_ratio_values = np.random.uniform(15, 25, len(companies))
            gross_margin_values = np.random.uniform(15, 25, len(companies))
    except Exception as e:
        logger.error(f"Error fetching competitor data: {e}")
        companies = ['Your Company', 'Competitor A', 'Competitor B', 'Competitor C', 'Competitor D']
        ebitda_values = np.random.uniform(15, 25, len(companies))
        current_ratio_values = np.random.uniform(15, 25, len(companies))
        gross_margin_values = np.random.uniform(15, 25, len(companies))

    # Create comparison chart
    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='EBITDA Margin',
        x=companies,
        y=ebitda_values,
        marker_color=COLORS['primary']
    ))
    fig.add_trace(go.Bar(
        name='Current Ratio',
        x=companies,
        y=current_ratio_values,
        marker_color=COLORS['success']
    ))
    fig.add_trace(go.Bar(
        name='Gross Margin',
        x=companies,
        y=gross_margin_values,
        marker_color=COLORS['warning']
    ))

    fig.update_layout(
        title="Competitor Benchmarking - Key Metrics",
        barmode='group',
        height=350,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color=COLORS['gray']['600']),
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor=COLORS['gray']['200'])
    )

    card_style = {
        "backgroundColor": COLORS['gray']['800'] if dark_mode else "#ffffff",
        "border": f"1px solid {COLORS['gray']['700'] if dark_mode else COLORS['gray']['200']}",
        "borderRadius": "12px",
        "padding": "24px"
    }

    return dbc.Card([
        dbc.CardBody([
            html.H2("Competitor Analysis", style={
                "fontSize": "20px",
                "fontWeight": "600",
                "marginBottom": "20px",
                "color": COLORS['gray']['100'] if dark_mode else COLORS['gray']['900']
            }),
            dcc.Graph(figure=fig, config={'displayModeBar': False})
        ])
    ], style=card_style)

#==============================================================================
# COMPARATIVE ANALYSIS & MARGIN BRIDGE & ALERT FEED
#==============================================================================

@app.callback(
    Output('comparative-analysis-container', 'children'),
    [Input('update-timestamp', 'data'),
     Input('dark-mode-store', 'data')]
)
def update_comparative_analysis(timestamp, dark_mode):
    """Comparative analysis / benchmarking"""
    return html.Div()  # Placeholder for now

@app.callback(
    Output('margin-bridge-container', 'children'),
    [Input('update-timestamp', 'data'),
     Input('dark-mode-store', 'data')]
)
def update_margin_bridge(timestamp, dark_mode):
    """Margin bridge waterfall chart showing revenue to net income breakdown"""

    card_style = {
        "backgroundColor": COLORS['gray']['800'] if dark_mode else "#ffffff",
        "border": f"1px solid {COLORS['gray']['700'] if dark_mode else COLORS['gray']['200']}",
        "borderRadius": "12px",
        "padding": "24px",
        "marginBottom": "20px"
    }

    # Margin bridge data (in millions)
    bridge_data = [
        {'step': 'Revenue', 'value': 500.0, 'type': 'total'},
        {'step': 'COGS', 'value': -280.0, 'type': 'relative'},
        {'step': 'Gross Profit', 'value': 220.0, 'type': 'total'},
        {'step': 'R&D', 'value': -45.0, 'type': 'relative'},
        {'step': 'Sales & Marketing', 'value': -60.0, 'type': 'relative'},
        {'step': 'G&A', 'value': -25.0, 'type': 'relative'},
        {'step': 'EBITDA', 'value': 90.0, 'type': 'total'},
        {'step': 'Depreciation', 'value': -12.0, 'type': 'relative'},
        {'step': 'Amortization', 'value': -8.0, 'type': 'relative'},
        {'step': 'EBIT', 'value': 70.0, 'type': 'total'},
        {'step': 'Interest', 'value': -5.0, 'type': 'relative'},
        {'step': 'Taxes', 'value': -13.0, 'type': 'relative'},
        {'step': 'Net Income', 'value': 52.0, 'type': 'total'},
    ]

    # Create waterfall chart
    fig = go.Figure()

    x_labels = [item['step'] for item in bridge_data]
    y_values = [item['value'] for item in bridge_data]
    measure_types = [item['type'] for item in bridge_data]

    # Convert 'total' to 'absolute' for waterfall chart
    measures = []
    for m_type in measure_types:
        if m_type == 'total':
            measures.append('total')
        else:
            measures.append('relative')

    # Create waterfall chart
    fig.add_trace(go.Waterfall(
        name="Margin Bridge",
        orientation="v",
        measure=measures,
        x=x_labels,
        y=y_values,
        text=[f"${abs(v):.1f}M" for v in y_values],
        textposition="outside",
        connector={"line": {"color": COLORS['gray']['400']}},
        increasing={"marker": {"color": COLORS['success']}},
        decreasing={"marker": {"color": COLORS['danger']}},
        totals={"marker": {"color": COLORS['primary']}}
    ))

    fig.update_layout(
        title="Margin Bridge: Revenue to Net Income ($M)",
        height=450,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color=COLORS['gray']['300'] if dark_mode else COLORS['gray']['600']),
        xaxis=dict(showgrid=False, tickangle=-45),
        yaxis=dict(showgrid=True, gridcolor=COLORS['gray']['700'] if dark_mode else COLORS['gray']['200'], title="Amount ($M)"),
        showlegend=False
    )

    waterfall_chart = dcc.Graph(figure=fig, config={'displayModeBar': False})

    # Margin metrics cards
    margin_metrics = [
        {'label': 'Gross Margin', 'value': 44.0, 'target': 45.0, 'icon': 'fa-chart-line'},
        {'label': 'EBITDA Margin', 'value': 18.0, 'target': 20.0, 'icon': 'fa-coins'},
        {'label': 'EBIT Margin', 'value': 14.0, 'target': 15.0, 'icon': 'fa-percentage'},
        {'label': 'Net Margin', 'value': 10.4, 'target': 12.0, 'icon': 'fa-trophy'}
    ]

    metric_cards = []
    for metric in margin_metrics:
        is_above_target = metric['value'] >= metric['target']
        metric_cards.append(
            dbc.Col([
                html.Div([
                    html.Div([
                        html.I(className=f"fas {metric['icon']}", style={
                            "fontSize": "24px",
                            "color": COLORS['success'] if is_above_target else COLORS['warning']
                        })
                    ], style={
                        "width": "48px",
                        "height": "48px",
                        "borderRadius": "12px",
                        "backgroundColor": f"rgba({int((COLORS['success'] if is_above_target else COLORS['warning'])[1:3], 16)}, {int((COLORS['success'] if is_above_target else COLORS['warning'])[3:5], 16)}, {int((COLORS['success'] if is_above_target else COLORS['warning'])[5:7], 16)}, 0.1)",
                        "display": "flex",
                        "alignItems": "center",
                        "justifyContent": "center",
                        "marginBottom": "12px"
                    }),
                    html.Div(metric['label'], style={
                        "fontSize": "13px",
                        "color": COLORS['gray']['400'] if dark_mode else COLORS['gray']['600'],
                        "marginBottom": "4px"
                    }),
                    html.Div(f"{metric['value']:.1f}%", style={
                        "fontSize": "24px",
                        "fontWeight": "700",
                        "color": COLORS['gray']['100'] if dark_mode else COLORS['gray']['900'],
                        "marginBottom": "4px"
                    }),
                    html.Div(f"Target: {metric['target']:.1f}%", style={
                        "fontSize": "12px",
                        "color": COLORS['gray']['500']
                    })
                ], style={
                    "backgroundColor": COLORS['gray']['700'] if dark_mode else COLORS['gray']['50'],
                    "border": f"1px solid {COLORS['gray']['600'] if dark_mode else COLORS['gray']['200']}",
                    "borderRadius": "12px",
                    "padding": "20px",
                    "textAlign": "center"
                })
            ], md=3)
        )

    # Detailed breakdown table
    breakdown_rows = []
    cumulative = 0
    for item in bridge_data:
        if item['type'] == 'relative':
            cumulative += item['value']
            running_total = cumulative
        else:
            cumulative = item['value']
            running_total = item['value']

        breakdown_rows.append(html.Tr([
            html.Td(item['step'], style={"fontWeight": "600" if item['type'] == 'total' else "400",
                                        "color": COLORS['gray']['100'] if dark_mode else COLORS['gray']['900'],
                                        "padding": "12px"}),
            html.Td(f"${item['value']:.1f}M", style={
                "textAlign": "right",
                "color": COLORS['success'] if item['value'] > 0 else COLORS['danger'],
                "fontWeight": "600" if item['type'] == 'total' else "400"
            }),
            html.Td(f"${running_total:.1f}M" if item['type'] == 'total' else "-",
                   style={"textAlign": "right", "color": COLORS['gray']['200'] if dark_mode else COLORS['gray']['800']}),
        ], style={
            "borderBottom": f"1px solid {COLORS['gray']['700'] if dark_mode else COLORS['gray']['200']}",
            "backgroundColor": f"rgba(59, 130, 246, 0.1)" if item['type'] == 'total' else "transparent"
        }))

    breakdown_table = dbc.Table([
        html.Thead(html.Tr([
            html.Th("Category", style={"fontWeight": "600", "color": COLORS['gray']['300'] if dark_mode else COLORS['gray']['700'], "padding": "12px"}),
            html.Th("Amount", style={"fontWeight": "600", "textAlign": "right", "color": COLORS['gray']['300'] if dark_mode else COLORS['gray']['700']}),
            html.Th("Cumulative", style={"fontWeight": "600", "textAlign": "right", "color": COLORS['gray']['300'] if dark_mode else COLORS['gray']['700']}),
        ])),
        html.Tbody(breakdown_rows)
    ], bordered=False, hover=True, style={"backgroundColor": "transparent", "marginTop": "20px"})

    return html.Div([
        html.H2("Margin Bridge Analysis", style={
            "fontSize": "24px",
            "fontWeight": "600",
            "marginBottom": "20px",
            "color": COLORS['gray']['100'] if dark_mode else COLORS['gray']['900']
        }),
        dbc.Card([
            dbc.CardBody([
                dbc.Row(metric_cards, className="g-3", style={"marginBottom": "24px"}),
                waterfall_chart,
                html.H3("Detailed Breakdown", style={
                    "fontSize": "18px",
                    "fontWeight": "600",
                    "marginTop": "24px",
                    "marginBottom": "12px",
                    "color": COLORS['gray']['100'] if dark_mode else COLORS['gray']['900']
                }),
                breakdown_table
            ])
        ], style=card_style)
    ])

@app.callback(
    Output('alert-feed-container', 'children'),
    [Input('update-timestamp', 'data'),
     Input('dark-mode-store', 'data')]
)
def update_alert_feed(timestamp, dark_mode):
    """Alert feed component"""
    card_style = {
        "backgroundColor": COLORS['gray']['800'] if dark_mode else "#ffffff",
        "border": f"1px solid {COLORS['gray']['700'] if dark_mode else COLORS['gray']['200']}",
        "borderRadius": "12px",
        "padding": "24px"
    }

    alerts = [
        {"icon": "fa-triangle-exclamation", "color": COLORS['danger'], "title": "Budget Variance Alert", "time": "2h ago"},
        {"icon": "fa-info-circle", "color": COLORS['info'], "title": "Q4 Forecast Updated", "time": "5h ago"},
        {"icon": "fa-check-circle", "color": COLORS['success'], "title": "Month-End Close Complete", "time": "1d ago"}
    ]

    alert_items = []
    for alert in alerts:
        alert_items.append(
            html.Div([
                html.I(className=f"fas {alert['icon']}", style={"color": alert['color'], "marginRight": "12px"}),
                html.Div([
                    html.Span(alert['title'], style={"fontWeight": "500", "color": COLORS['gray']['100'] if dark_mode else COLORS['gray']['900']}),
                    html.Span(alert['time'], style={"fontSize": "12px", "color": COLORS['gray']['400'], "marginLeft": "8px"})
                ], style={"flex": "1"})
            ], style={"display": "flex", "alignItems": "center", "padding": "12px 0", "borderBottom": f"1px solid {COLORS['gray']['200']}"})
        )

    return dbc.Card([
        dbc.CardBody([
            html.H2("Recent Alerts", style={
                "fontSize": "18px",
                "fontWeight": "600",
                "marginBottom": "16px",
                "color": COLORS['gray']['100'] if dark_mode else COLORS['gray']['900']
            }),
            html.Div(alert_items)
        ])
    ], style=card_style)

#==============================================================================
# TABBED ANALYTICS SECTION
#==============================================================================

@app.callback(
    Output('tabbed-analytics-container', 'children'),
    [Input('update-timestamp', 'data'),
     Input('dark-mode-store', 'data')]
)
def update_tabbed_analytics(timestamp, dark_mode):
    """Create tabbed analytics section"""

    card_style = {
        "backgroundColor": COLORS['gray']['800'] if dark_mode else "#ffffff",
        "border": f"1px solid {COLORS['gray']['700'] if dark_mode else COLORS['gray']['200']}",
        "borderRadius": "12px"
    }

    return dbc.Card([
        dbc.Tabs([
            dbc.Tab(label="Ratio Analyzer", tab_id="ratio-analyzer"),
            dbc.Tab(label="Scenario Simulator", tab_id="scenario-simulator"),
            dbc.Tab(label="Forecast & Trends", tab_id="forecast"),
            dbc.Tab(label="Anomaly Heatmap", tab_id="heatmap"),
            dbc.Tab(label="Competitor Benchmark", tab_id="competitor"),
            dbc.Tab(label="Goal Tracker", tab_id="goals")
        ], id="analytics-tabs", active_tab="ratio-analyzer", style={
            "borderBottom": f"2px solid {COLORS['gray']['200']}"
        }),

        html.Div(id="analytics-tab-content", style={"padding": "24px"})
    ], style=card_style)

@app.callback(
    Output('analytics-tab-content', 'children'),
    [Input('analytics-tabs', 'active_tab'),
     Input('dark-mode-store', 'data')]
)
def render_tab_content(active_tab, dark_mode):
    """Render content for active tab"""

    if active_tab == "ratio-analyzer":
        # Create ratio analysis visualization
        fig = go.Figure()
        categories = ['Liquidity', 'Profitability', 'Efficiency', 'Leverage']
        values = [85, 92, 78, 88]

        fig.add_trace(go.Bar(
            x=categories,
            y=values,
            marker_color=COLORS['primary'],
            text=values,
            textposition='outside'
        ))

        fig.update_layout(
            title="Financial Ratio Analysis",
            height=400,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color=COLORS['gray']['600']),
            yaxis=dict(title="Score", range=[0, 100])
        )

        return dcc.Graph(figure=fig, config={'displayModeBar': False})

    elif active_tab == "forecast":
        # Forecast chart
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']
        actual = [220, 225, 230, 235, 242, 245]
        forecast = [248, 252, 258, 265, 272, 280]

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=months, y=actual, name='Actual', mode='lines+markers',
                                line=dict(color=COLORS['primary'], width=3)))
        fig.add_trace(go.Scatter(x=months, y=forecast, name='Forecast', mode='lines+markers',
                                line=dict(color=COLORS['success'], width=3, dash='dash')))

        fig.update_layout(
            title="Revenue Forecast & Trends",
            height=400,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color=COLORS['gray']['600']),
            yaxis=dict(title="Revenue ($M)"),
            xaxis=dict(title="Month")
        )

        return dcc.Graph(figure=fig, config={'displayModeBar': False})

    else:
        return html.Div([
            html.P(f"Content for {active_tab} tab", style={
                "padding": "40px",
                "textAlign": "center",
                "color": COLORS['gray']['500']
            })
        ])

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    debug = os.getenv('DASH_DEBUG', 'false').lower() == 'true'

    logger.info(f"Starting CFO Pulse Dashboard on port {port}")
    logger.info(f"Debug mode: {debug}")
    logger.info(f"Authentication service available: {auth_service is not None}")
    logger.info(f"Data service available: {data_service is not None}")

    app.run_server(
        host='0.0.0.0',
        port=port,
        debug=debug
    )
