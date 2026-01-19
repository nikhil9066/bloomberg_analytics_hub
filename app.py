"""
CFO Pulse Dashboard - Financial Intelligence Platform
Modern KPI dashboard with AI insights and advanced analytics
"""

import os
import json
import dash
from dash import dcc, html, Input, Output, State, callback_context, ALL, MATCH
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from utils.config import load_config, setup_logging
from db.data_service import FinancialDataService
from utils.advanced_charts import (
    AdvancedCharts,
    example_waterfall,
    example_sankey,
    example_heatmap,
    example_treemap,
    example_funnel
)

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
app.title = "CFO Pulse - Financial Intelligence Dashboard"

# Add favicon
app._favicon = "favicon.svg"

# Import authentication service
from db.auth_service import AuthService
from flask import request, jsonify, redirect, session
import secrets

# Configure Flask session for production deployment
server.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))

# Detect if running in production (Cloud Foundry)
is_production = os.environ.get('FLASK_ENV') == 'production'

# Session configuration for SAP Cloud Foundry / production
server.config.update(
    SESSION_COOKIE_SECURE=is_production,  # Require HTTPS only in production
    SESSION_COOKIE_HTTPONLY=True,  # Prevent JavaScript access
    SESSION_COOKIE_SAMESITE='Lax',  # Allow same-site requests
    PERMANENT_SESSION_LIFETIME=timedelta(hours=24),  # 24-hour session
    SESSION_COOKIE_NAME='financial_dashboard_session'
)

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
            session.permanent = True  # Make session persistent
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

# Add access request route
@server.route('/request-access', methods=['POST'])
def request_access():
    """Handle new user access requests and send email notification"""
    try:
        data = request.get_json()
        name = data.get('name')
        email = data.get('email')
        company = data.get('company')
        reason = data.get('reason')

        if not all([name, email, company, reason]):
            return jsonify({'success': False, 'message': 'All fields are required'}), 400

        # Import email service and send notification
        from utils.email_service import EmailService
        email_service = EmailService()

        # Log the request
        logger.info(f"Access request received: {name} ({email}) from {company}")

        # Send email notification
        email_sent = email_service.send_access_request_alert(name, email, company, reason)

        if email_sent:
            logger.info(f"Access request email sent for {email}")
        else:
            logger.warning(f"Could not send access request email for {email} (email service may not be configured)")

        return jsonify({
            'success': True,
            'message': 'Your access request has been submitted. We will review and get back to you soon!'
        })

    except Exception as e:
        logger.error(f"Access request error: {str(e)}")
        return jsonify({'success': False, 'message': 'An error occurred while submitting your request'}), 500

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

# Load CSV data (fallback for when HANA is unavailable)
csv_data = None
import os
APP_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    basic_csv_path = os.path.join(APP_DIR, 'basic.csv')
    financial_ratios_df = pd.read_csv(basic_csv_path)
    logger.info(f"Loaded basic.csv from {basic_csv_path}: {len(financial_ratios_df)} records")
    csv_data = {'financial_ratios': financial_ratios_df}

    # Load ANNUAL_FINANCIALS CSV (advance.csv)
    try:
        advance_csv_path = os.path.join(APP_DIR, 'advance.csv')
        annual_financials_df = pd.read_csv(advance_csv_path)
        logger.info(f"Loaded advance.csv from {advance_csv_path}: {len(annual_financials_df)} records")
        csv_data['annual_financials'] = annual_financials_df
    except Exception as e:
        logger.warning(f"advance.csv not found or failed to load: {e}")
        csv_data['annual_financials'] = None
except Exception as e:
    logger.error(f"Failed to load CSV files: {e}")
    csv_data = None

# Define numeric columns for competitor analysis metrics
NUMERIC_METRIC_COLUMNS = [
    'TOT_DEBT_TO_TOT_ASSET',
    'CASH_DVD_COVERAGE',
    'TOT_DEBT_TO_EBITDA',
    'CUR_RATIO',
    'QUICK_RATIO',
    'GROSS_MARGIN',
    'INTEREST_COVERAGE_RATIO',
    'EBITDA_MARGIN',
    'TOT_LIAB_AND_EQY',
    'NET_DEBT_TO_SHRHLDR_EQTY'
]

# Friendly names for metrics
METRIC_LABELS = {
    'TOT_DEBT_TO_TOT_ASSET': 'Total Debt to Total Asset',
    'CASH_DVD_COVERAGE': 'Cash Dividend Coverage',
    'TOT_DEBT_TO_EBITDA': 'Total Debt to EBITDA',
    'CUR_RATIO': 'Current Ratio',
    'QUICK_RATIO': 'Quick Ratio',
    'GROSS_MARGIN': 'Gross Margin (%)',
    'INTEREST_COVERAGE_RATIO': 'Interest Coverage Ratio',
    'EBITDA_MARGIN': 'EBITDA Margin (%)',
    'TOT_LIAB_AND_EQY': 'Total Liabilities & Equity',
    'NET_DEBT_TO_SHRHLDR_EQTY': 'Net Debt to Shareholder Equity'
}

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

def create_footer(dark_mode=False):
    """Create production-level professional footer"""

    bg_color = COLORS['gray']['900'] if dark_mode else COLORS['gray']['50']
    text_color = COLORS['gray']['300'] if dark_mode else COLORS['gray']['600']
    text_light = COLORS['gray']['400'] if dark_mode else COLORS['gray']['500']
    border_color = COLORS['gray']['700'] if dark_mode else COLORS['gray']['200']

    return html.Footer([
        # Main footer content
        html.Div([
            dbc.Row([
                # Column 1: About & Branding
                dbc.Col([
                    html.Div([
                        html.I(className="fas fa-chart-pie", style={
                            "fontSize": "24px",
                            "color": COLORS['primary'],
                            "marginBottom": "12px"
                        }),
                        html.H5("CFO Pulse", style={
                            "fontWeight": "700",
                            "marginBottom": "8px",
                            "color": COLORS['gray']['100'] if dark_mode else COLORS['gray']['900']
                        }),
                        html.P("Financial Intelligence Dashboard", style={
                            "fontSize": "13px",
                            "color": text_light,
                            "marginBottom": "12px"
                        }),
                        html.P("Real-time analytics powered by SAP HANA Cloud", style={
                            "fontSize": "12px",
                            "color": text_light,
                            "marginBottom": "0"
                        })
                    ])
                ], md=3, sm=6, xs=12, className="mb-3"),

                # Column 2: System Status
                dbc.Col([
                    html.H6("System Status", style={
                        "fontWeight": "600",
                        "marginBottom": "12px",
                        "fontSize": "14px",
                        "color": COLORS['gray']['100'] if dark_mode else COLORS['gray']['900']
                    }),
                    html.Div([
                        html.Div([
                            html.I(className="fas fa-circle", style={
                                "fontSize": "8px",
                                "color": COLORS['success'],
                                "marginRight": "8px"
                            }),
                            html.Span("Data Connection Active", style={"fontSize": "12px"})
                        ], style={"marginBottom": "6px"}),
                        html.Div([
                            html.I(className="fas fa-sync-alt", style={
                                "fontSize": "10px",
                                "marginRight": "8px",
                                "color": COLORS['info']
                            }),
                            html.Span([
                                "Auto-refresh: Every 5 min | Next: ",
                                html.Span(id="footer-next-refresh", children="09:00 AM EST", style={
                                    "fontWeight": "600",
                                    "color": COLORS['primary']
                                })
                            ], style={"fontSize": "12px"})
                        ], style={"marginBottom": "6px"}),
                        html.Div([
                            html.I(className="fas fa-database", style={
                                "fontSize": "10px",
                                "marginRight": "8px",
                                "color": COLORS['warning']
                            }),
                            html.Span("SAP HANA Cloud", style={"fontSize": "12px"})
                        ])
                    ], style={"color": text_color})
                ], md=3, sm=6, xs=12, className="mb-3"),

                # Column 3: Account & Quick Links
                dbc.Col([
                    html.H6("Account", style={
                        "fontWeight": "600",
                        "marginBottom": "12px",
                        "fontSize": "14px",
                        "color": COLORS['gray']['100'] if dark_mode else COLORS['gray']['900']
                    }),
                    html.Div([
                        html.Div([
                            html.I(className="fas fa-user", style={
                                "fontSize": "10px",
                                "marginRight": "8px"
                            }),
                            html.Span("Logged in as: ", style={"fontSize": "12px"}),
                            html.Span(id="footer-user-email", children="admin@g.com", style={
                                "fontSize": "12px",
                                "fontWeight": "600",
                                "color": COLORS['primary']
                            })
                        ], style={"marginBottom": "8px"}),
                        html.Div([
                            html.A([
                                html.I(className="fas fa-sign-out-alt", style={"marginRight": "6px"}),
                                "Logout"
                            ], href="/logout", style={
                                "fontSize": "12px",
                                "color": COLORS['danger'],
                                "textDecoration": "none",
                                "fontWeight": "500",
                                "display": "inline-block",
                                "padding": "4px 12px",
                                "border": f"1px solid {COLORS['danger']}",
                                "borderRadius": "4px",
                                "transition": "all 0.2s"
                            }, className="footer-logout-btn")
                        ])
                    ], style={"color": text_color})
                ], md=3, sm=6, xs=12, className="mb-3"),

                # Column 4: Support & Legal
                dbc.Col([
                    html.H6("Support & Legal", style={
                        "fontWeight": "600",
                        "marginBottom": "12px",
                        "fontSize": "14px",
                        "color": COLORS['gray']['100'] if dark_mode else COLORS['gray']['900']
                    }),
                    html.Div([
                        html.Div([
                            html.A([
                                html.I(className="fas fa-question-circle", style={"marginRight": "6px"}),
                                "Help & Support"
                            ], href="#", style={
                                "fontSize": "12px",
                                "color": text_color,
                                "textDecoration": "none",
                                "display": "block",
                                "marginBottom": "6px"
                            })
                        ]),
                        html.Div([
                            html.A([
                                html.I(className="fas fa-file-contract", style={"marginRight": "6px"}),
                                "Terms of Service"
                            ], href="#", style={
                                "fontSize": "12px",
                                "color": text_color,
                                "textDecoration": "none",
                                "display": "block",
                                "marginBottom": "6px"
                            })
                        ]),
                        html.Div([
                            html.A([
                                html.I(className="fas fa-shield-alt", style={"marginRight": "6px"}),
                                "Privacy Policy"
                            ], href="#", style={
                                "fontSize": "12px",
                                "color": text_color,
                                "textDecoration": "none",
                                "display": "block"
                            })
                        ])
                    ])
                ], md=3, sm=6, xs=12, className="mb-3"),
            ], className="g-4"),

            # Bottom bar with copyright
            html.Hr(style={
                "margin": "24px 0 16px 0",
                "border": "none",
                "borderTop": f"1px solid {border_color}",
                "opacity": "0.5"
            }),

            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Span("© 2026 CFO Pulse Dashboard", style={
                            "fontSize": "12px",
                            "color": text_light
                        }),
                        html.Span(" | ", style={
                            "margin": "0 8px",
                            "color": text_light
                        }),
                        html.Span("All rights reserved", style={
                            "fontSize": "12px",
                            "color": text_light
                        })
                    ], style={"textAlign": "left"})
                ], md=6, xs=12),

                dbc.Col([
                    html.Div([
                        html.Span("Version 1.0.0", style={
                            "fontSize": "11px",
                            "color": text_light,
                            "marginRight": "16px"
                        }),
                        html.Span(" | ", style={
                            "margin": "0 8px",
                            "color": text_light
                        }),
                        html.Span([
                            html.I(className="fas fa-server", style={"marginRight": "4px"}),
                            "Production"
                        ], style={
                            "fontSize": "11px",
                            "color": COLORS['success'],
                            "fontWeight": "500"
                        })
                    ], style={"textAlign": "right"})
                ], md=6, xs=12)
            ])
        ], style={
            "padding": "32px 48px 24px 48px",
            "backgroundColor": bg_color,
            "color": text_color,
            "borderTop": f"2px solid {COLORS['primary']}"
        })
    ], style={
        "marginTop": "48px",
        "width": "100%"
    })

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
        {"id": "nav-advanced-charts", "icon": "fas fa-chart-line", "text": "Advanced Charts", "target": "advanced-charts-container"},
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

        # Data Refresh Status Section (Collapsible)
        html.Div([
            # Toggle button
            html.Div([
                html.Div([
                    html.I(className="fas fa-sync-alt sidebar-footer-item-icon"),
                    html.Span("Data Refresh Status", className="sidebar-footer-item-text")
                ], style={"flex": "1"}),
                html.I(id="data-refresh-toggle-icon", className="fas fa-chevron-down", style={
                    "fontSize": "12px",
                    "transition": "transform 0.3s ease",
                    "color": COLORS['gray']['400']
                })
            ], id="data-refresh-toggle", className="sidebar-footer-item", style={
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "space-between",
                "cursor": "pointer"
            }),

            # Collapsible content
            html.Div([
                html.Div([
                    # Last Run
                    html.Div([
                        html.Div([
                            html.I(className="fas fa-check-circle", style={
                                "fontSize": "10px",
                                "color": COLORS['success'],
                                "marginRight": "6px"
                            }),
                            html.Span("Last Run", className="sidebar-footer-item-text", style={"fontSize": "11px"})
                        ], style={"marginBottom": "4px"}),
                        html.Div(id="last-run-time", children="Jan 6, 2026 09:00 AM EST", style={
                            "fontSize": "11px",
                            "color": COLORS['gray']['400'] if dark_mode else COLORS['gray']['600'],
                            "marginLeft": "16px"
                        })
                    ], style={"marginBottom": "12px"}),

                    # Duration
                    html.Div([
                        html.Div([
                            html.I(className="fas fa-clock", style={
                                "fontSize": "10px",
                                "color": COLORS['info'],
                                "marginRight": "6px"
                            }),
                            html.Span("Duration", className="sidebar-footer-item-text", style={"fontSize": "11px"})
                        ], style={"marginBottom": "4px"}),
                        html.Div("45 seconds", style={
                            "fontSize": "11px",
                            "color": COLORS['gray']['400'] if dark_mode else COLORS['gray']['600'],
                            "marginLeft": "16px"
                        })
                    ], style={"marginBottom": "12px"}),

                    # Records Updated
                    html.Div([
                        html.Div([
                            html.I(className="fas fa-database", style={
                                "fontSize": "10px",
                                "color": COLORS['primary'],
                                "marginRight": "6px"
                            }),
                            html.Span("Records Updated", className="sidebar-footer-item-text", style={"fontSize": "11px"})
                        ], style={"marginBottom": "4px"}),
                        html.Div("850", style={
                            "fontSize": "11px",
                            "color": COLORS['gray']['400'] if dark_mode else COLORS['gray']['600'],
                            "marginLeft": "16px"
                        })
                    ], style={"marginBottom": "12px"}),

                    # Next Run
                    html.Div([
                        html.Div([
                            html.I(className="fas fa-calendar-alt", style={
                                "fontSize": "10px",
                                "color": COLORS['warning'],
                                "marginRight": "6px"
                            }),
                            html.Span("Next Run", className="sidebar-footer-item-text", style={"fontSize": "11px"})
                        ], style={"marginBottom": "4px"}),
                        html.Div("Jan 7, 2026 09:00 AM EST", style={
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
            ], id="data-refresh-content", style={"padding": "8px 8px 0 8px", "display": "block"}),
        ], style={"marginBottom": "8px"}),

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
# ONBOARDING & LOADING SCREENS
#==============================================================================

# Load test data from Kt.json
def load_test_data():
    """Load test company data from Kt.json"""
    try:
        with open('Kt.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load Kt.json: {e}")
        return None

# Funny loading messages
LOADING_MESSAGES = [
    "Crunching numbers like a caffeinated accountant...",
    "Teaching AI to count beans...",
    "Convincing Excel that we're still friends...",
    "Bribing the database with virtual cookies...",
    "Asking ChatGPT to double-check our math...",
    "Converting coffee into financial insights...",
    "Pretending to understand your balance sheet...",
    "Making your competitors nervous...",
    "Calculating how many cups of coffee your CFO needs...",
    "Turning boring numbers into exciting charts..."
]

def create_onboarding_screen():
    """Create the onboarding form for user company details"""

    input_style = {
        "backgroundColor": "#ffffff",
        "border": f"1px solid {COLORS['gray']['300']}",
        "borderRadius": "8px",
        "padding": "12px 16px",
        "fontSize": "14px",
        "width": "100%",
        "marginBottom": "4px"
    }

    label_style = {
        "fontSize": "13px",
        "fontWeight": "500",
        "color": COLORS['gray']['700'],
        "marginBottom": "6px",
        "display": "block"
    }

    section_title_style = {
        "fontSize": "16px",
        "fontWeight": "600",
        "color": COLORS['gray']['800'],
        "marginBottom": "16px",
        "marginTop": "24px",
        "paddingBottom": "8px",
        "borderBottom": f"2px solid {COLORS['primary']}"
    }

    return html.Div([
        # Background with gradient
        html.Div(style={
            "position": "fixed",
            "top": "0",
            "left": "0",
            "right": "0",
            "bottom": "0",
            "background": f"linear-gradient(135deg, {COLORS['gray']['900']} 0%, {COLORS['gray']['800']} 50%, #1e3a5f 100%)",
            "zIndex": "-1"
        }),

        # Main container
        html.Div([
            # Header
            html.Div([
                html.I(className="fas fa-chart-pie", style={
                    "fontSize": "48px",
                    "color": COLORS['primary'],
                    "marginBottom": "16px"
                }),
                html.H1("Welcome to CFO Pulse", style={
                    "fontSize": "32px",
                    "fontWeight": "700",
                    "color": "#ffffff",
                    "marginBottom": "8px"
                }),
                html.P("Enter your company details to benchmark against industry leaders", style={
                    "fontSize": "16px",
                    "color": COLORS['gray']['400'],
                    "marginBottom": "32px"
                })
            ], style={"textAlign": "center"}),

            # Form Card
            html.Div([
                # Company Basic Info Section
                html.H3("Company Information", style=section_title_style),

                dbc.Row([
                    dbc.Col([
                        html.Label("Company Name *", style=label_style),
                        dcc.Input(
                            id='onboard-company-name',
                            type='text',
                            placeholder='e.g., Acme Corporation',
                            style=input_style
                        )
                    ], md=6),
                    dbc.Col([
                        html.Label("Industry", style=label_style),
                        dcc.Dropdown(
                            id='onboard-industry',
                            options=[
                                {'label': 'Technology', 'value': 'tech'},
                                {'label': 'Healthcare', 'value': 'healthcare'},
                                {'label': 'Finance', 'value': 'finance'},
                                {'label': 'Retail', 'value': 'retail'},
                                {'label': 'Manufacturing', 'value': 'manufacturing'},
                                {'label': 'Energy', 'value': 'energy'},
                                {'label': 'Other', 'value': 'other'}
                            ],
                            placeholder='Select industry...',
                            style={"marginBottom": "4px"}
                        )
                    ], md=6)
                ], className="mb-3"),

                # Financial Ratios Section
                html.H3("Financial Ratios", style=section_title_style),
                html.P("Enter your key financial metrics for comparison", style={
                    "fontSize": "13px",
                    "color": COLORS['gray']['500'],
                    "marginBottom": "16px"
                }),

                dbc.Row([
                    dbc.Col([
                        html.Label("EBITDA Margin (%)", style=label_style),
                        dcc.Input(id='onboard-ebitda-margin', type='number', placeholder='e.g., 15.5', style=input_style)
                    ], md=4),
                    dbc.Col([
                        html.Label("Gross Margin (%)", style=label_style),
                        dcc.Input(id='onboard-gross-margin', type='number', placeholder='e.g., 45.0', style=input_style)
                    ], md=4),
                    dbc.Col([
                        html.Label("Current Ratio", style=label_style),
                        dcc.Input(id='onboard-current-ratio', type='number', placeholder='e.g., 1.5', style=input_style)
                    ], md=4)
                ], className="mb-3"),

                dbc.Row([
                    dbc.Col([
                        html.Label("Quick Ratio", style=label_style),
                        dcc.Input(id='onboard-quick-ratio', type='number', placeholder='e.g., 1.2', style=input_style)
                    ], md=4),
                    dbc.Col([
                        html.Label("Debt to Asset (%)", style=label_style),
                        dcc.Input(id='onboard-debt-to-asset', type='number', placeholder='e.g., 25.0', style=input_style)
                    ], md=4),
                    dbc.Col([
                        html.Label("Debt to EBITDA", style=label_style),
                        dcc.Input(id='onboard-debt-to-ebitda', type='number', placeholder='e.g., 2.5', style=input_style)
                    ], md=4)
                ], className="mb-3"),

                dbc.Row([
                    dbc.Col([
                        html.Label("Interest Coverage Ratio", style=label_style),
                        dcc.Input(id='onboard-interest-coverage', type='number', placeholder='e.g., 8.0', style=input_style)
                    ], md=4),
                    dbc.Col([
                        html.Label("Net Debt to Equity (%)", style=label_style),
                        dcc.Input(id='onboard-net-debt-equity', type='number', placeholder='e.g., 50.0', style=input_style)
                    ], md=4),
                    dbc.Col([
                        html.Label("Cash Dividend Coverage", style=label_style),
                        dcc.Input(id='onboard-cash-dividend', type='number', placeholder='e.g., 3.0', style=input_style)
                    ], md=4)
                ], className="mb-3"),

                # Privacy Notice
                html.Div([
                    html.I(className="fas fa-shield-halved", style={
                        "color": COLORS['success'],
                        "marginRight": "8px"
                    }),
                    html.Span("We don't store any of your company data. It's only used for comparison during this session.", style={
                        "fontSize": "13px",
                        "color": COLORS['gray']['600']
                    })
                ], style={
                    "backgroundColor": COLORS['gray']['100'],
                    "padding": "12px 16px",
                    "borderRadius": "8px",
                    "marginTop": "24px",
                    "marginBottom": "24px",
                    "display": "flex",
                    "alignItems": "center"
                }),

                # Buttons
                html.Div([
                    dbc.Button([
                        html.I(className="fas fa-rocket me-2"),
                        "Launch Dashboard"
                    ], id='btn-launch-dashboard', color="primary", size="lg", style={
                        "padding": "12px 32px",
                        "fontWeight": "600",
                        "borderRadius": "8px"
                    }),

                    dbc.Button([
                        html.I(className="fas fa-flask me-2"),
                        "Use Test Data"
                    ], id='btn-use-test-data', color="secondary", outline=True, size="lg", style={
                        "padding": "12px 32px",
                        "fontWeight": "600",
                        "borderRadius": "8px",
                        "marginLeft": "16px"
                    })
                ], style={"textAlign": "center", "marginTop": "8px"})

            ], style={
                "backgroundColor": "#ffffff",
                "borderRadius": "16px",
                "padding": "32px",
                "maxWidth": "800px",
                "margin": "0 auto",
                "boxShadow": "0 20px 60px rgba(0,0,0,0.3)"
            })

        ], style={
            "minHeight": "100vh",
            "padding": "40px 20px",
            "display": "flex",
            "flexDirection": "column",
            "justifyContent": "center"
        })
    ], id='onboarding-screen')

def create_loading_screen():
    """Create a funny loading screen"""
    return html.Div([
        html.Div([
            # Animated logo
            html.Div([
                html.I(className="fas fa-chart-line", style={
                    "fontSize": "64px",
                    "color": COLORS['primary'],
                    "animation": "pulse 1.5s ease-in-out infinite"
                })
            ], style={"marginBottom": "32px"}),

            # Loading spinner
            html.Div([
                html.Span([dbc.Spinner(color="primary", type="grow", size="lg")]),
                html.Span([dbc.Spinner(color="success", type="grow", size="lg")], style={"marginLeft": "16px"}),
                html.Span([dbc.Spinner(color="warning", type="grow", size="lg")], style={"marginLeft": "16px"})
            ], style={"marginBottom": "32px", "display": "flex", "justifyContent": "center"}),

            # Funny message (will be updated dynamically)
            html.H2(id='loading-message', children="Preparing your dashboard...", style={
                "fontSize": "24px",
                "fontWeight": "600",
                "color": "#ffffff",
                "marginBottom": "16px",
                "textAlign": "center"
            }),

            # Progress indicator
            html.Div([
                html.Div(id='loading-progress-bar', style={
                    "width": "0%",
                    "height": "4px",
                    "backgroundColor": COLORS['primary'],
                    "borderRadius": "2px",
                    "transition": "width 0.3s ease"
                })
            ], style={
                "width": "300px",
                "height": "4px",
                "backgroundColor": COLORS['gray']['700'],
                "borderRadius": "2px",
                "overflow": "hidden"
            }),

            # Countdown
            html.P(id='loading-countdown', children="", style={
                "fontSize": "14px",
                "color": COLORS['gray']['400'],
                "marginTop": "16px"
            })
        ], style={
            "textAlign": "center"
        })
    ], id='loading-screen', style={
        "position": "fixed",
        "top": "0",
        "left": "0",
        "right": "0",
        "bottom": "0",
        "background": f"linear-gradient(135deg, {COLORS['gray']['900']} 0%, {COLORS['gray']['800']} 50%, #1e3a5f 100%)",
        "display": "none",
        "alignItems": "center",
        "justifyContent": "center",
        "zIndex": "9999"
    })

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

    # Store for selected competitors (used across the page)
    dcc.Store(id='selected-competitors-store', data=['META']),

    # Store for user company data
    dcc.Store(id='user-company-store', data=None),

    # Store for onboarding completion
    dcc.Store(id='onboarding-complete-store', data=False),

    # Interval for loading animation
    dcc.Interval(id='loading-interval', interval=500, n_intervals=0, disabled=True),

    # Onboarding Screen
    html.Div(id='onboarding-container', children=create_onboarding_screen()),

    # Loading Screen
    create_loading_screen(),

    # Main Dashboard (hidden initially)
    html.Div([
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
                html.Div(id='tabbed-analytics-container', className="mb-4", style={"padding": "0 24px"}),

                # Advanced Charts Section
                html.Div(id='advanced-charts-container', className="mb-4", style={"padding": "0 24px"}),

                # Footer
                html.Div(id='footer-container')
            ])
        ], id='main-content', fluid=True, style=custom_style, className='main-content sidebar-expanded')
    ], id='dashboard-container', style={'display': 'none', 'position': 'relative'})

], style={'position': 'relative'})

#==============================================================================
# ONBOARDING CALLBACKS
#==============================================================================

import random

# Callback to handle Launch Dashboard button
@app.callback(
    [Output('user-company-store', 'data'),
     Output('onboarding-container', 'style'),
     Output('loading-screen', 'style'),
     Output('loading-interval', 'disabled')],
    [Input('btn-launch-dashboard', 'n_clicks'),
     Input('btn-use-test-data', 'n_clicks')],
    [State('onboard-company-name', 'value'),
     State('onboard-industry', 'value'),
     State('onboard-ebitda-margin', 'value'),
     State('onboard-gross-margin', 'value'),
     State('onboard-current-ratio', 'value'),
     State('onboard-quick-ratio', 'value'),
     State('onboard-debt-to-asset', 'value'),
     State('onboard-debt-to-ebitda', 'value'),
     State('onboard-interest-coverage', 'value'),
     State('onboard-net-debt-equity', 'value'),
     State('onboard-cash-dividend', 'value')],
    prevent_initial_call=True
)
def handle_onboarding_submit(launch_clicks, test_clicks, company_name, industry,
                              ebitda_margin, gross_margin, current_ratio, quick_ratio,
                              debt_to_asset, debt_to_ebitda, interest_coverage,
                              net_debt_equity, cash_dividend):
    ctx = callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]

    loading_style = {
        "position": "fixed",
        "top": "0",
        "left": "0",
        "right": "0",
        "bottom": "0",
        "background": f"linear-gradient(135deg, {COLORS['gray']['900']} 0%, {COLORS['gray']['800']} 50%, #1e3a5f 100%)",
        "display": "flex",
        "alignItems": "center",
        "justifyContent": "center",
        "zIndex": "9999"
    }

    if triggered_id == 'btn-use-test-data':
        # Load test data from Kt.json
        test_data = load_test_data()
        if test_data:
            # Get ANNUAL_FINANCIALS section from Kt.json for KPI cards
            annual_financials = test_data.get('ANNUAL_FINANCIALS', {})
            user_data = {
                'company_name': 'Test Company (Kt.json)',
                'industry': 'tech',
                'TICKER': 'TEST',
                'EBITDA_MARGIN': test_data.get('FINANCIAL_ADVANCED', {}).get('EBITDA_MARGIN', 0),
                'GROSS_MARGIN': 45.0,  # Default as not in Kt.json
                'CUR_RATIO': test_data.get('FINANCIAL_RATIOS', {}).get('CURRENT_RATIO', 0),
                'QUICK_RATIO': test_data.get('FINANCIAL_RATIOS', {}).get('QUICK_RATIO', 0),
                'TOT_DEBT_TO_TOT_ASSET': test_data.get('FINANCIAL_RATIOS', {}).get('TOT_DEBT_TO_TOT_ASSET', 0),
                'TOT_DEBT_TO_EBITDA': 2.0,  # Default
                'INTEREST_COVERAGE_RATIO': test_data.get('FINANCIAL_RATIOS', {}).get('INTEREST_COVERAGE_RATIO', 0),
                'NET_DEBT_TO_SHRHLDR_EQTY': test_data.get('FINANCIAL_RATIOS', {}).get('NET_DEBT_TO_SHRHLDR_EQTY', 0),
                'CASH_DVD_COVERAGE': test_data.get('FINANCIAL_RATIOS', {}).get('CASH_RATIO', 0),
                # Add ANNUAL_FINANCIALS data for KPI cards
                'annual_financials': {
                    'SALES_REV_TURN': annual_financials.get('SALES_REV_TURN', 0),
                    'EBITDA': test_data.get('FINANCIAL_ADVANCED', {}).get('EBITDA', 0),
                    'OPER_EXPENSES': annual_financials.get('OPER_EXPENSES', 0),
                    'CASH_FROM_OPER_ACTIV': annual_financials.get('CASH_FROM_OPER_ACTIV', 0),
                    'WORKING_CAPITAL': annual_financials.get('WORKING_CAPITAL', 0),
                    'NET_PROFIT_MARGIN': annual_financials.get('NET_PROFIT_MARGIN', 0)
                }
            }
        else:
            user_data = {
                'company_name': 'Test Company',
                'industry': 'tech',
                'TICKER': 'TEST',
                'EBITDA_MARGIN': 15.0,
                'GROSS_MARGIN': 45.0,
                'CUR_RATIO': 1.5,
                'QUICK_RATIO': 1.2,
                'TOT_DEBT_TO_TOT_ASSET': 25.0,
                'TOT_DEBT_TO_EBITDA': 2.0,
                'INTEREST_COVERAGE_RATIO': 8.0,
                'NET_DEBT_TO_SHRHLDR_EQTY': 50.0,
                'CASH_DVD_COVERAGE': 3.0,
                # Default annual financials
                'annual_financials': {
                    'SALES_REV_TURN': 15000,
                    'EBITDA': 3000,
                    'OPER_EXPENSES': 12000,
                    'CASH_FROM_OPER_ACTIV': 1700,
                    'WORKING_CAPITAL': 800,
                    'NET_PROFIT_MARGIN': 5.0
                }
            }
    else:
        # Use user-entered data
        user_data = {
            'company_name': company_name or 'Your Company',
            'industry': industry or 'other',
            'TICKER': 'USER',
            'EBITDA_MARGIN': ebitda_margin or 0,
            'GROSS_MARGIN': gross_margin or 0,
            'CUR_RATIO': current_ratio or 0,
            'QUICK_RATIO': quick_ratio or 0,
            'TOT_DEBT_TO_TOT_ASSET': debt_to_asset or 0,
            'TOT_DEBT_TO_EBITDA': debt_to_ebitda or 0,
            'INTEREST_COVERAGE_RATIO': interest_coverage or 0,
            'NET_DEBT_TO_SHRHLDR_EQTY': net_debt_equity or 0,
            'CASH_DVD_COVERAGE': cash_dividend or 0,
            # Default annual financials for user-entered companies
            # These would ideally come from additional onboarding fields
            'annual_financials': {
                'SALES_REV_TURN': 0,
                'EBITDA': 0,
                'OPER_EXPENSES': 0,
                'CASH_FROM_OPER_ACTIV': 0,
                'WORKING_CAPITAL': 0,
                'NET_PROFIT_MARGIN': 0
            }
        }

    # Hide onboarding, show loading
    return user_data, {'display': 'none'}, loading_style, False

# Callback for loading animation and transition to dashboard
@app.callback(
    [Output('loading-message', 'children'),
     Output('loading-progress-bar', 'style'),
     Output('dashboard-container', 'style'),
     Output('loading-screen', 'style', allow_duplicate=True),
     Output('loading-interval', 'disabled', allow_duplicate=True)],
    [Input('loading-interval', 'n_intervals')],
    [State('user-company-store', 'data')],
    prevent_initial_call=True
)
def update_loading_screen(n_intervals, user_data):
    if n_intervals is None or n_intervals == 0:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update

    # Calculate progress (8 intervals = 4 seconds at 500ms each)
    total_intervals = 8
    progress = min((n_intervals / total_intervals) * 100, 100)

    progress_style = {
        "width": f"{progress}%",
        "height": "4px",
        "backgroundColor": COLORS['primary'],
        "borderRadius": "2px",
        "transition": "width 0.3s ease"
    }

    # Pick a random funny message
    message = random.choice(LOADING_MESSAGES)

    # Check if loading is complete
    if n_intervals >= total_intervals:
        # Show dashboard, hide loading
        return message, progress_style, {'display': 'block', 'position': 'relative'}, {'display': 'none'}, True

    return message, progress_style, dash.no_update, dash.no_update, dash.no_update

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

# Data refresh status toggle callback
@app.callback(
    [Output('data-refresh-content', 'style'),
     Output('data-refresh-toggle-icon', 'style')],
    [Input('data-refresh-toggle', 'n_clicks'),
     Input('sidebar-collapsed-store', 'data')],
    [State('data-refresh-content', 'style'),
     State('data-refresh-toggle-icon', 'style')]
)
def toggle_data_refresh_status(n_clicks, sidebar_collapsed, content_style, icon_style):
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

    # If data refresh toggle was clicked
    if ctx.triggered and ctx.triggered[0]['prop_id'] == 'data-refresh-toggle.n_clicks' and n_clicks:
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

# Footer render callback
@app.callback(
    Output('footer-container', 'children'),
    [Input('dark-mode-store', 'data')]
)
def render_footer(dark_mode):
    return create_footer(dark_mode=dark_mode)

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
     Input('dark-mode-store', 'data'),
     Input('selected-competitors-store', 'data'),
     Input('user-company-store', 'data')]
)
def update_kpi_grid(year, region, view_mode, timestamp, dark_mode, selected_competitors, user_company):
    """Create KPI grid with ANNUAL_FINANCIALS data from selected competitors"""

    # Default values
    avg_revenue = 0
    avg_ebitda = 0
    avg_opex = 0
    avg_cash_flow = 0
    avg_working_capital = 0
    avg_net_profit_margin = 0

    # Get user company values from Kt.json (stored in user_company)
    user_revenue = 0
    user_ebitda = 0
    user_opex = 0
    user_cash_flow = 0
    user_working_capital = 0
    user_net_profit_margin = 0

    if user_company:
        # Extract user company data from ANNUAL_FINANCIALS section of Kt.json
        annual_data = user_company.get('annual_financials', {})
        if annual_data:
            user_revenue = annual_data.get('SALES_REV_TURN', 0) or 0
            user_ebitda = annual_data.get('EBITDA', 0) or 0
            user_opex = annual_data.get('OPER_EXPENSES', 0) or 0
            user_cash_flow = annual_data.get('CASH_FROM_OPER_ACTIV', 0) or 0
            user_working_capital = annual_data.get('WORKING_CAPITAL', 0) or 0
            user_net_profit_margin = annual_data.get('NET_PROFIT_MARGIN', 0) or 0

    # Fetch ANNUAL_FINANCIALS data
    try:
        df = None
        if data_service and data_service.connected:
            # Get data from HANA
            df = data_service.get_annual_financials(selected_competitors)
        elif csv_data and csv_data.get('annual_financials') is not None:
            # Use CSV data for local testing
            df = csv_data['annual_financials'].copy()
            if selected_competitors:
                df = df[df['TICKER'].isin(selected_competitors)]

        if df is not None and len(df) > 0:
            # Calculate averages across all years for selected competitors
            # Group by ticker first, then get mean across tickers
            ticker_avgs = df.groupby('TICKER').agg({
                'SALES_REV_TURN': 'mean',
                'EBITDA': 'mean',
                'IS_SGA_EXPENSE': 'mean',  # Operating expenses proxy
                'CF_FREE_CASH_FLOW': 'mean',
                'NET_INCOME': 'mean'
            }).reset_index()

            # Calculate overall averages
            avg_revenue = ticker_avgs['SALES_REV_TURN'].mean() if 'SALES_REV_TURN' in ticker_avgs.columns else 0
            avg_ebitda = ticker_avgs['EBITDA'].mean() if 'EBITDA' in ticker_avgs.columns else 0
            avg_opex = ticker_avgs['IS_SGA_EXPENSE'].mean() if 'IS_SGA_EXPENSE' in ticker_avgs.columns else 0
            avg_cash_flow = ticker_avgs['CF_FREE_CASH_FLOW'].mean() if 'CF_FREE_CASH_FLOW' in ticker_avgs.columns else 0

            # Get working capital directly from data if available
            if 'WORKING_CAPITAL' in df.columns:
                avg_working_capital = df.groupby('TICKER')['WORKING_CAPITAL'].mean().mean()
            elif 'CUR_RATIO' in df.columns and 'BS_CUR_LIAB' in df.columns:
                # Fallback: Calculate from Current Ratio and Current Liabilities
                df['WORKING_CAPITAL'] = (df['CUR_RATIO'] * df['BS_CUR_LIAB']) - df['BS_CUR_LIAB']
                avg_working_capital = df.groupby('TICKER')['WORKING_CAPITAL'].mean().mean()
            else:
                avg_working_capital = 0

            # Calculate net profit margin
            if 'NET_INCOME' in df.columns and 'SALES_REV_TURN' in df.columns:
                df['NET_PROFIT_MARGIN'] = (df['NET_INCOME'] / df['SALES_REV_TURN'] * 100).replace([float('inf'), -float('inf')], 0).fillna(0)
                avg_net_profit_margin = df.groupby('TICKER')['NET_PROFIT_MARGIN'].mean().mean()
            else:
                avg_net_profit_margin = 0

            logger.info(f"KPI Cards - Selected {len(selected_competitors) if selected_competitors else 0} competitors: Avg Revenue=${avg_revenue:.2f}M, Avg EBITDA=${avg_ebitda:.2f}M")

    except Exception as e:
        logger.error(f"Error fetching KPI data: {e}")

    # Calculate change percentage (your company vs avg of competitors)
    def calc_change(user_val, avg_val, lower_is_better=False):
        if avg_val == 0:
            return 0
        change = ((user_val - avg_val) / avg_val) * 100
        return change if not lower_is_better else -change

    # Determine trend direction based on comparison
    def get_trend(user_val, avg_val, lower_is_better=False):
        if lower_is_better:
            return 'down' if user_val < avg_val else 'up'
        return 'up' if user_val > avg_val else 'down'

    # Define KPIs with competitor averages and user company comparison
    kpis = [
        {
            'name': 'Revenue',
            'value': avg_revenue,  # Average of selected competitors
            'user_value': user_revenue,  # Your company value
            'change': calc_change(user_revenue, avg_revenue),
            'target': avg_revenue * 1.1 if avg_revenue > 0 else 250000,
            'icon': 'fa-dollar-sign',
            'color': COLORS['primary'],
            'trend': get_trend(user_revenue, avg_revenue),
            'sparkline': [avg_revenue * 0.9, avg_revenue * 0.92, avg_revenue * 0.95, avg_revenue * 0.97, avg_revenue * 0.99, avg_revenue],
            'is_millions': True
        },
        {
            'name': 'EBITDA',
            'value': avg_ebitda,
            'user_value': user_ebitda,
            'change': calc_change(user_ebitda, avg_ebitda),
            'target': avg_ebitda * 1.1 if avg_ebitda > 0 else 48000,
            'icon': 'fa-chart-line',
            'color': COLORS['success'],
            'trend': get_trend(user_ebitda, avg_ebitda),
            'sparkline': [avg_ebitda * 0.9, avg_ebitda * 0.92, avg_ebitda * 0.95, avg_ebitda * 0.97, avg_ebitda * 0.99, avg_ebitda],
            'is_millions': True
        },
        {
            'name': 'Operating Expenses',
            'value': avg_opex,
            'user_value': user_opex,
            'change': calc_change(user_opex, avg_opex, lower_is_better=True),  # Lower is better for expenses
            'target': avg_opex * 0.95 if avg_opex > 0 else 155000,
            'icon': 'fa-receipt',
            'color': COLORS['info'],
            'trend': get_trend(user_opex, avg_opex, lower_is_better=True),
            'sparkline': [avg_opex * 1.05, avg_opex * 1.03, avg_opex * 1.01, avg_opex, avg_opex * 0.99, avg_opex * 0.98],
            'is_millions': True,
            'lower_is_better': True
        },
        {
            'name': 'Cash Flow',
            'value': avg_cash_flow,
            'user_value': user_cash_flow,
            'change': calc_change(user_cash_flow, avg_cash_flow),
            'target': avg_cash_flow * 1.1 if avg_cash_flow > 0 else 40000,
            'icon': 'fa-wallet',
            'color': COLORS['purple'],
            'trend': get_trend(user_cash_flow, avg_cash_flow),
            'sparkline': [avg_cash_flow * 0.85, avg_cash_flow * 0.88, avg_cash_flow * 0.92, avg_cash_flow * 0.95, avg_cash_flow * 0.98, avg_cash_flow],
            'is_millions': True
        },
        {
            'name': 'Working Capital',
            'value': avg_working_capital,
            'user_value': user_working_capital,
            'change': calc_change(user_working_capital, avg_working_capital),
            'target': avg_working_capital * 1.1 if avg_working_capital > 0 else 55000,
            'icon': 'fa-piggy-bank',
            'color': COLORS['warning'],
            'trend': get_trend(user_working_capital, avg_working_capital),
            'sparkline': [avg_working_capital * 0.9, avg_working_capital * 0.92, avg_working_capital * 0.94, avg_working_capital * 0.96, avg_working_capital * 0.98, avg_working_capital],
            'is_millions': True
        },
        {
            'name': 'Net Profit Margin',
            'value': avg_net_profit_margin,
            'user_value': user_net_profit_margin,
            'change': calc_change(user_net_profit_margin, avg_net_profit_margin),
            'target': avg_net_profit_margin * 1.1 if avg_net_profit_margin > 0 else 20.0,
            'icon': 'fa-percent',
            'color': COLORS['success'],
            'trend': get_trend(user_net_profit_margin, avg_net_profit_margin),
            'sparkline': [avg_net_profit_margin * 0.9, avg_net_profit_margin * 0.92, avg_net_profit_margin * 0.95, avg_net_profit_margin * 0.97, avg_net_profit_margin * 0.99, avg_net_profit_margin],
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

    # Determine if change is good based on whether lower is better
    lower_is_better = kpi.get('lower_is_better', False)
    if lower_is_better:
        is_good = kpi['change'] > 0  # For expenses, positive change means you're below avg (good)
    else:
        is_good = kpi['change'] > 0  # For revenue etc., positive change means you're above avg (good)

    has_alert = abs(kpi['change']) > 50

    # Helper function to format large numbers nicely
    def format_currency(val):
        if val == 0:
            return "$0"
        abs_val = abs(val)
        if abs_val >= 1000:
            # Values in ANNUAL_FINANCIALS are in millions, so 1000 = 1 billion
            return f"${val/1000:.1f}B"
        elif abs_val >= 1:
            return f"${val:.1f}M"
        else:
            return f"${val:.2f}M"

    # Format value based on type
    if kpi.get('is_percentage'):
        value_display = f"{kpi['value']:.1f}%"
        target_display = f"{kpi['target']:.1f}%"
        user_value_display = f"{kpi.get('user_value', 0):.1f}%"
    elif kpi.get('is_millions'):
        # Values are already in millions in ANNUAL_FINANCIALS (e.g., 130497 = $130.5B)
        value_display = format_currency(kpi['value'])
        target_display = format_currency(kpi['target'])
        user_value_display = format_currency(kpi.get('user_value', 0))
    else:
        value_display = f"${kpi['value']/1000000:.1f}M"
        target_display = f"${kpi['target']/1000000:.1f}M"
        user_value_display = f"${kpi.get('user_value', 0)/1000000:.1f}M"

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
                    # Comparison arrow: Your company vs Average
                    html.Div([
                        html.I(className=f"fas fa-arrow-{'up' if is_good else 'down'}",
                              style={"fontSize": "12px", "marginRight": "4px"}),
                        html.Span(f"{'+' if kpi['change'] > 0 else ''}{kpi['change']:.1f}% vs avg")
                    ], style={
                        "fontSize": "14px",
                        "color": COLORS['success'] if is_good else COLORS['danger'],
                        "marginTop": "4px"
                    })
                ], style={"marginLeft": "12px"})
            ], style={"display": "flex", "alignItems": "center"})
        ], style={"marginBottom": "16px"}),

        # Value display - Show Competitor Average
        html.Div([
            html.Div([
                html.Span("Competitor Avg: ", style={
                    "fontSize": "14px",
                    "color": COLORS['gray']['400'] if dark_mode else COLORS['gray']['500']
                }),
                html.Span(value_display, style={
                    "fontSize": "28px",
                    "fontWeight": "700",
                    "color": COLORS['gray']['100'] if dark_mode else COLORS['gray']['900']
                })
            ], style={"marginBottom": "8px"}),
            html.Div([
                html.Span("Your Company: ", style={
                    "fontSize": "13px",
                    "color": COLORS['gray']['400'] if dark_mode else COLORS['gray']['500']
                }),
                html.Span(user_value_display, style={
                    "fontSize": "16px",
                    "fontWeight": "600",
                    "color": COLORS['success'] if is_good else COLORS['danger']
                })
            ])
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

def get_available_tickers():
    """Get list of available tickers from data source"""
    try:
        df = None
        # Try HANA first
        if data_service and data_service.connected:
            data = data_service.get_financial_ratios(limit=500)
            if data is not None and isinstance(data, pd.DataFrame) and not data.empty:
                df = data

        # Fallback to CSV
        if df is None or df.empty:
            if csv_data and csv_data.get('financial_ratios') is not None:
                df = csv_data['financial_ratios']

        if df is not None and not df.empty and 'TICKER' in df.columns:
            tickers = df['TICKER'].unique().tolist()
            logger.info(f"Available tickers: {len(tickers)}")
            return tickers
    except Exception as e:
        logger.error(f"Error getting tickers: {e}")
    return []

def get_competitor_data():
    """Get financial ratios dataframe"""
    try:
        # Try HANA first
        if data_service and data_service.connected:
            data = data_service.get_financial_ratios(limit=500)
            if data is not None and isinstance(data, pd.DataFrame) and not data.empty:
                logger.info(f"Got {len(data)} records from HANA FINANCIAL_RATIOS")
                return data
            else:
                logger.warning("HANA FINANCIAL_RATIOS returned empty data, falling back to CSV")

        # Fallback to CSV data
        if csv_data and csv_data.get('financial_ratios') is not None:
            df = csv_data['financial_ratios']
            if df is not None and not df.empty:
                logger.info(f"Using CSV data for financial ratios: {len(df)} records")
                return df
    except Exception as e:
        logger.error(f"Error getting competitor data: {e}")

    logger.error("No data available from HANA or CSV")
    return None

@app.callback(
    Output('competitor-analysis-container', 'children'),
    [Input('update-timestamp', 'data'),
     Input('dark-mode-store', 'data'),
     Input('selected-competitors-store', 'data'),
     Input('user-company-store', 'data')]
)
def update_competitor_analysis(timestamp, dark_mode, selected_competitors, user_company):
    """Create competitor analysis module with filters"""

    # Get available tickers
    available_tickers = get_available_tickers()
    if not available_tickers:
        available_tickers = ['META', 'NVDA', 'MSFT', 'GOOGL', 'AVGO', 'WMT', 'ORCL', 'XOM']

    # Add user company to available tickers if exists
    user_company_name = None
    if user_company:
        user_company_name = user_company.get('company_name', 'Your Company')
        if user_company_name not in available_tickers:
            available_tickers = [user_company_name] + available_tickers

    # Default selected competitors if none
    if not selected_competitors:
        selected_competitors = available_tickers[:5]

    # Ensure user company is in selected list
    if user_company_name and user_company_name not in selected_competitors:
        selected_competitors = [user_company_name] + selected_competitors[:4]

    card_style = {
        "backgroundColor": COLORS['gray']['800'] if dark_mode else "#ffffff",
        "border": f"1px solid {COLORS['gray']['700'] if dark_mode else COLORS['gray']['200']}",
        "borderRadius": "12px",
        "padding": "24px"
    }

    filter_btn_style = {
        "border": f"1px solid {COLORS['gray']['600'] if dark_mode else COLORS['gray']['300']}",
        "borderRadius": "8px",
        "padding": "8px 12px",
        "backgroundColor": "transparent",
        "cursor": "pointer",
        "display": "flex",
        "alignItems": "center",
        "justifyContent": "center",
        "minWidth": "40px",
        "height": "38px"
    }

    filter_btn_active_style = {
        **filter_btn_style,
        "backgroundColor": COLORS['primary'],
        "borderColor": COLORS['primary'],
        "color": "#ffffff"
    }

    text_color = COLORS['gray']['100'] if dark_mode else COLORS['gray']['900']
    label_color = COLORS['gray']['400'] if dark_mode else COLORS['gray']['600']

    # Filter pill button style
    filter_pill_style = {
        "border": f"1px solid {COLORS['gray']['600'] if dark_mode else COLORS['gray']['300']}",
        "borderRadius": "20px",
        "padding": "6px 14px",
        "backgroundColor": "transparent",
        "cursor": "pointer",
        "display": "inline-flex",
        "alignItems": "center",
        "justifyContent": "center",
        "fontSize": "13px",
        "fontWeight": "500",
        "color": COLORS['gray']['400'] if dark_mode else COLORS['gray']['600'],
        "transition": "all 0.2s ease"
    }

    filter_pill_active_style = {
        **filter_pill_style,
        "backgroundColor": COLORS['primary'],
        "borderColor": COLORS['primary'],
        "color": "#ffffff"
    }

    return html.Div([
        # Chart Section (Full Width)
        dbc.Card([
            dbc.CardBody([
                # Header with inline filters
                html.Div([
                    # Title
                    html.Div([
                        html.I(className="fas fa-chart-bar", style={
                            "fontSize": "20px",
                            "color": COLORS['primary'],
                            "marginRight": "10px"
                        }),
                        html.H2("Competitor Ratio Analysis", style={
                            "fontSize": "18px",
                            "fontWeight": "600",
                            "margin": "0",
                            "color": text_color
                        })
                    ], style={"display": "flex", "alignItems": "center"}),

                    # Compact Filters Row
                    html.Div([
                        # Chart Type Pills
                        html.Div([
                            html.Button([
                                html.I(className="fas fa-chart-bar me-1"),
                                "Bar"
                            ], id='chart-type-bar', n_clicks=0, style=filter_pill_active_style),
                            html.Button([
                                html.I(className="fas fa-chart-line me-1"),
                                "Line"
                            ], id='chart-type-line', n_clicks=0, style=filter_pill_style),
                            html.Button([
                                html.I(className="fas fa-chart-pie me-1"),
                                "Pie"
                            ], id='chart-type-pie', n_clicks=0, style=filter_pill_style),
                        ], style={"display": "flex", "gap": "6px", "marginRight": "12px"}),

                        # Divider
                        html.Div(style={
                            "width": "1px",
                            "height": "24px",
                            "backgroundColor": COLORS['gray']['600'] if dark_mode else COLORS['gray']['300'],
                            "marginRight": "12px"
                        }),

                        # View Mode Pills
                        html.Div([
                            html.Button([
                                html.I(className="fas fa-chart-simple me-1"),
                                "Chart"
                            ], id='view-mode-graph', n_clicks=0, style=filter_pill_active_style),
                            html.Button([
                                html.I(className="fas fa-table me-1"),
                                "Table"
                            ], id='view-mode-table', n_clicks=0, style=filter_pill_style),
                        ], style={"display": "flex", "gap": "6px"})
                    ], style={"display": "flex", "alignItems": "center"})
                ], style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "center",
                    "marginBottom": "16px",
                    "flexWrap": "wrap",
                    "gap": "12px"
                }),

                # Metric and Company Selectors in a nice row
                html.Div([
                    html.Div([
                        html.Span("Metric: ", style={
                            "fontSize": "13px",
                            "color": label_color,
                            "marginRight": "8px"
                        }),
                        dcc.Dropdown(
                            id='competitor-metric-selector',
                            options=[{'label': METRIC_LABELS.get(col, col), 'value': col} for col in NUMERIC_METRIC_COLUMNS],
                            value='EBITDA_MARGIN',
                            clearable=False,
                            style={"width": "200px", "display": "inline-block"}
                        )
                    ], style={"display": "flex", "alignItems": "center", "marginRight": "24px"}),

                    html.Div([
                        html.Span("Companies: ", style={
                            "fontSize": "13px",
                            "color": label_color,
                            "marginRight": "8px"
                        }),
                        dcc.Dropdown(
                            id='add-competitor-dropdown',
                            options=[{'label': t, 'value': t} for t in available_tickers],
                            value=selected_competitors,
                            multi=True,
                            placeholder="Select companies...",
                            style={"width": "400px", "display": "inline-block"}
                        )
                    ], style={"display": "flex", "alignItems": "center", "flex": "1"})
                ], style={
                    "display": "flex",
                    "alignItems": "center",
                    "padding": "12px 16px",
                    "backgroundColor": COLORS['gray']['700'] if dark_mode else COLORS['gray']['50'],
                    "borderRadius": "8px",
                    "marginBottom": "16px",
                    "flexWrap": "wrap",
                    "gap": "12px"
                }),

                # Store for chart type and view mode
                dcc.Store(id='chart-type-store', data='bar'),
                dcc.Store(id='view-mode-store', data='graph'),

                # Chart/Table Container
                html.Div(id='competitor-chart-container')
            ])
        ], style=card_style, className="mb-4"),

        # Company Comparison Cards Section (Below Chart - Full Width)
        dbc.Card([
            dbc.CardBody([
                # Header
                html.Div([
                    html.I(className="fas fa-balance-scale", style={
                        "fontSize": "20px",
                        "color": COLORS['info'],
                        "marginRight": "10px"
                    }),
                    html.H2("Quick Compare", style={
                        "fontSize": "18px",
                        "fontWeight": "600",
                        "margin": "0",
                        "color": text_color
                    }),
                    html.Span("Color coded: ", style={
                        "fontSize": "12px",
                        "color": label_color,
                        "marginLeft": "auto",
                        "marginRight": "8px"
                    }),
                    html.Span("Good", style={
                        "fontSize": "11px",
                        "color": "#10b981",
                        "backgroundColor": "#10b98115",
                        "padding": "2px 8px",
                        "borderRadius": "4px",
                        "marginRight": "6px"
                    }),
                    html.Span("Medium", style={
                        "fontSize": "11px",
                        "color": COLORS['warning'],
                        "backgroundColor": f"{COLORS['warning']}15",
                        "padding": "2px 8px",
                        "borderRadius": "4px",
                        "marginRight": "6px"
                    }),
                    html.Span("Poor", style={
                        "fontSize": "11px",
                        "color": "#ef4444",
                        "backgroundColor": "#ef444415",
                        "padding": "2px 8px",
                        "borderRadius": "4px"
                    })
                ], style={
                    "display": "flex",
                    "alignItems": "center",
                    "marginBottom": "20px",
                    "flexWrap": "wrap",
                    "gap": "8px"
                }),

                # Comparison Cards Container
                html.Div(id='company-comparison-cards')
            ])
        ], style=card_style),

        # Data Integration Sources Message
        html.Div([
            html.Div([
                html.I(className="fas fa-database", style={
                    "fontSize": "16px",
                    "color": COLORS['primary'],
                    "marginRight": "10px"
                }),
                html.Span("Data Integration Sources", style={
                    "fontSize": "14px",
                    "fontWeight": "600",
                    "color": text_color
                })
            ], style={"display": "flex", "alignItems": "center", "marginBottom": "12px"}),

            html.Div([
                # EDGAR
                html.Div([
                    html.Span("EDGAR", style={
                        "fontWeight": "600",
                        "color": COLORS['info'],
                        "marginRight": "6px"
                    }),
                    html.Span(": SEC filings including 10-K, 10-Q forms with financial statements and ratios", style={
                        "color": label_color,
                        "fontSize": "13px"
                    })
                ], style={"marginBottom": "6px"}),

                # Bloomberg Terminal
                html.Div([
                    html.Span("Bloomberg Terminal", style={
                        "fontWeight": "600",
                        "color": COLORS['warning'],
                        "marginRight": "6px"
                    }),
                    html.Span(": Real-time market data, analyst estimates, and proprietary financial metrics", style={
                        "color": label_color,
                        "fontSize": "13px"
                    })
                ], style={"marginBottom": "6px"}),

                # Mixed
                html.Div([
                    html.Span("Mixed", style={
                        "fontWeight": "600",
                        "color": COLORS['success'],
                        "marginRight": "6px"
                    }),
                    html.Span(": Combination of EDGAR regulatory filings and Bloomberg market intelligence", style={
                        "color": label_color,
                        "fontSize": "13px"
                    })
                ])
            ]),

            # Last updated line
            html.Div([
                html.I(className="fas fa-clock", style={
                    "fontSize": "11px",
                    "color": COLORS['gray']['400'],
                    "marginRight": "6px"
                }),
                html.Span(f"Last updated: {datetime.now().strftime('%b %d, %Y, %I:%M %p')} EST", style={
                    "fontSize": "12px",
                    "color": COLORS['gray']['400']
                }),
                html.Span(" • ", style={"color": COLORS['gray']['400'], "margin": "0 6px"}),
                html.Span("Ratio calculations use trailing twelve months (TTM) data", style={
                    "fontSize": "12px",
                    "color": COLORS['gray']['400']
                })
            ], style={"marginTop": "12px", "display": "flex", "alignItems": "center"})
        ], style={
            "backgroundColor": COLORS['gray']['700'] if dark_mode else COLORS['gray']['50'],
            "border": f"1px solid {COLORS['gray']['600'] if dark_mode else COLORS['gray']['200']}",
            "borderRadius": "8px",
            "padding": "16px 20px",
            "marginTop": "16px"
        }),

        # Peer Comparison Benchmarking Table Section
        dbc.Card([
            dbc.CardBody([
                # Header
                html.Div([
                    html.Div([
                        html.I(className="fas fa-table", style={
                            "fontSize": "20px",
                            "color": COLORS['purple'],
                            "marginRight": "10px"
                        }),
                        html.H2("Peer Comparison Benchmarking Table", style={
                            "fontSize": "18px",
                            "fontWeight": "600",
                            "margin": "0",
                            "color": text_color
                        })
                    ], style={"display": "flex", "alignItems": "center"}),
                    html.Span("Comprehensive peer analysis with insights", style={
                        "fontSize": "12px",
                        "color": label_color
                    })
                ], style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "center",
                    "marginBottom": "20px",
                    "flexWrap": "wrap",
                    "gap": "8px"
                }),

                # Peer Comparison Table Container
                html.Div(id='peer-comparison-table')
            ])
        ], style={**card_style, "marginTop": "16px"}),

        # Industry Median Benchmarking Section
        dbc.Card([
            dbc.CardBody([
                # Header
                html.Div([
                    html.Div([
                        html.I(className="fas fa-industry", style={
                            "fontSize": "20px",
                            "color": COLORS['success'],
                            "marginRight": "10px"
                        }),
                        html.H2("Industry Median Benchmarking", style={
                            "fontSize": "18px",
                            "fontWeight": "600",
                            "margin": "0",
                            "color": text_color
                        })
                    ], style={"display": "flex", "alignItems": "center"}),
                    html.Div([
                        html.Span("Above Median", style={
                            "fontSize": "11px",
                            "color": "#10b981",
                            "backgroundColor": "#10b98115",
                            "padding": "2px 8px",
                            "borderRadius": "4px",
                            "marginRight": "6px"
                        }),
                        html.Span("Below Median", style={
                            "fontSize": "11px",
                            "color": "#ef4444",
                            "backgroundColor": "#ef444415",
                            "padding": "2px 8px",
                            "borderRadius": "4px"
                        })
                    ], style={"display": "flex", "alignItems": "center"})
                ], style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "center",
                    "marginBottom": "20px",
                    "flexWrap": "wrap",
                    "gap": "8px"
                }),

                # Industry Median Table Container
                html.Div(id='industry-median-table')
            ])
        ], style={**card_style, "marginTop": "16px"})
    ])

# Callback to update selected competitors store
@app.callback(
    Output('selected-competitors-store', 'data'),
    [Input('add-competitor-dropdown', 'value')],
    prevent_initial_call=True
)
def update_selected_competitors(selected):
    if selected:
        return selected
    return ['META']

# Callback for Peer Comparison Benchmarking Table
@app.callback(
    Output('peer-comparison-table', 'children'),
    [Input('selected-competitors-store', 'data'),
     Input('dark-mode-store', 'data'),
     Input('user-company-store', 'data')]
)
def render_peer_comparison_table(selected_competitors, dark_mode, user_company):
    """Render the peer comparison benchmarking table"""

    # Get data
    df = get_competitor_data()

    if df is None:
        df = pd.DataFrame()

    # Add user company data if available
    user_company_name = None
    if user_company:
        user_company_name = user_company.get('company_name', 'Your Company')
        user_row = {
            'TICKER': user_company_name,
            'TOT_DEBT_TO_TOT_ASSET': user_company.get('TOT_DEBT_TO_TOT_ASSET', 0),
            'CASH_DVD_COVERAGE': user_company.get('CASH_DVD_COVERAGE', 0),
            'TOT_DEBT_TO_EBITDA': user_company.get('TOT_DEBT_TO_EBITDA', 0),
            'CUR_RATIO': user_company.get('CUR_RATIO', 0),
            'QUICK_RATIO': user_company.get('QUICK_RATIO', 0),
            'GROSS_MARGIN': user_company.get('GROSS_MARGIN', 0),
            'INTEREST_COVERAGE_RATIO': user_company.get('INTEREST_COVERAGE_RATIO', 0),
            'EBITDA_MARGIN': user_company.get('EBITDA_MARGIN', 0),
            'NET_DEBT_TO_SHRHLDR_EQTY': user_company.get('NET_DEBT_TO_SHRHLDR_EQTY', 0),
            'TOT_LIAB_AND_EQY': 50000.0  # Placeholder
        }
        user_df = pd.DataFrame([user_row])
        df = pd.concat([user_df, df], ignore_index=True)

    if df.empty or not selected_competitors:
        return html.Div("Select companies to compare", style={
            "textAlign": "center", "padding": "40px", "color": COLORS['gray']['500']
        })

    # Filter for selected competitors
    df_filtered = df[df['TICKER'].isin(selected_competitors)]

    # Remove duplicates - keep only one row per ticker
    df_filtered = df_filtered.drop_duplicates(subset=['TICKER'], keep='first')

    if df_filtered.empty:
        return html.Div("No data available", style={
            "textAlign": "center", "padding": "40px", "color": COLORS['gray']['500']
        })

    text_color = COLORS['gray']['100'] if dark_mode else COLORS['gray']['900']
    header_bg = COLORS['gray']['700'] if dark_mode else COLORS['gray']['100']
    row_bg = COLORS['gray']['800'] if dark_mode else "#ffffff"
    alt_row_bg = COLORS['gray']['750'] if dark_mode else COLORS['gray']['50']
    border_color = COLORS['gray']['600'] if dark_mode else COLORS['gray']['200']

    # Define metrics with comments
    metrics_config = [
        {'key': 'TOT_LIAB_AND_EQY', 'label': 'Total Assets', 'format': '${:.1f}B', 'divisor': 1000,
         'comment': 'Scale comparison - larger companies have different dynamics'},
        {'key': 'EBITDA_MARGIN', 'label': 'EBITDA Margin', 'format': '{:.1f}%', 'divisor': 1,
         'comment': 'Operational efficiency indicator - higher is better'},
        {'key': 'GROSS_MARGIN', 'label': 'Gross Margin', 'format': '{:.1f}%', 'divisor': 1,
         'comment': 'Pricing power and cost structure efficiency'},
        {'key': 'CUR_RATIO', 'label': 'Current Ratio', 'format': '{:.2f}x', 'divisor': 1,
         'comment': 'Liquidity health - above 1.5x is generally healthy'},
        {'key': 'QUICK_RATIO', 'label': 'Quick Ratio', 'format': '{:.2f}x', 'divisor': 1,
         'comment': 'Stringent liquidity test - excludes inventory'},
        {'key': 'TOT_DEBT_TO_TOT_ASSET', 'label': 'Debt/Asset', 'format': '{:.1f}%', 'divisor': 1,
         'comment': 'Leverage indicator - lower generally means less risk'},
        {'key': 'INTEREST_COVERAGE_RATIO', 'label': 'Interest Coverage', 'format': '{:.1f}x', 'divisor': 1,
         'comment': 'Ability to service debt - higher is safer'},
    ]

    # Build table header
    companies = df_filtered['TICKER'].tolist()
    header_cells = [
        html.Th("Metric", style={
            "padding": "12px 16px",
            "textAlign": "left",
            "fontWeight": "600",
            "fontSize": "13px",
            "color": text_color,
            "backgroundColor": header_bg,
            "borderBottom": f"2px solid {COLORS['primary']}",
            "minWidth": "120px"
        })
    ]

    for i, company in enumerate(companies):
        is_user = user_company_name and company == user_company_name
        header_cells.append(
            html.Th([
                html.Div([
                    html.I(className="fas fa-star me-1" if is_user else "fas fa-building me-1", style={
                        "fontSize": "10px",
                        "color": COLORS['warning'] if is_user else COLORS['gray']['400']
                    }),
                    html.Span(company if len(company) <= 12 else company[:10] + "...", title=company)
                ], style={"display": "flex", "alignItems": "center", "justifyContent": "center"}),
                html.Div("You" if is_user else f"Peer {i}" if not is_user else "", style={
                    "fontSize": "10px",
                    "color": COLORS['primary'] if is_user else COLORS['gray']['400'],
                    "marginTop": "2px"
                })
            ], style={
                "padding": "12px 8px",
                "textAlign": "center",
                "fontWeight": "600",
                "fontSize": "12px",
                "color": text_color,
                "backgroundColor": COLORS['primary'] + "20" if is_user else header_bg,
                "borderBottom": f"2px solid {COLORS['primary']}",
                "minWidth": "90px"
            })
        )

    header_cells.append(
        html.Th("Insight", style={
            "padding": "12px 16px",
            "textAlign": "left",
            "fontWeight": "600",
            "fontSize": "13px",
            "color": text_color,
            "backgroundColor": header_bg,
            "borderBottom": f"2px solid {COLORS['primary']}",
            "minWidth": "200px"
        })
    )

    # Build table rows
    rows = []
    for idx, metric in enumerate(metrics_config):
        row_cells = [
            html.Td(metric['label'], style={
                "padding": "12px 16px",
                "fontWeight": "500",
                "fontSize": "13px",
                "color": text_color,
                "backgroundColor": alt_row_bg if idx % 2 == 0 else row_bg,
                "borderBottom": f"1px solid {border_color}"
            })
        ]

        values = []
        for company in companies:
            company_data = df_filtered[df_filtered['TICKER'] == company]
            if not company_data.empty:
                val = company_data[metric['key']].iloc[0]
                values.append(val if pd.notnull(val) else 0)
            else:
                values.append(0)

        # Find best value for highlighting
        if metric['key'] in ['TOT_DEBT_TO_TOT_ASSET', 'NET_DEBT_TO_SHRHLDR_EQTY']:
            best_idx = values.index(min(values)) if values else -1
        else:
            best_idx = values.index(max(values)) if values else -1

        for i, (company, val) in enumerate(zip(companies, values)):
            is_user = user_company_name and company == user_company_name
            is_best = i == best_idx

            formatted_val = metric['format'].format(val / metric['divisor']) if val else "-"

            cell_style = {
                "padding": "12px 8px",
                "textAlign": "center",
                "fontSize": "13px",
                "fontWeight": "600" if is_best else "400",
                "color": COLORS['success'] if is_best else text_color,
                "backgroundColor": (COLORS['primary'] + "10" if is_user else alt_row_bg) if idx % 2 == 0 else (COLORS['primary'] + "10" if is_user else row_bg),
                "borderBottom": f"1px solid {border_color}"
            }

            row_cells.append(html.Td([
                html.Span(formatted_val),
                html.I(className="fas fa-trophy ms-1", style={
                    "fontSize": "10px",
                    "color": COLORS['warning']
                }) if is_best else None
            ], style=cell_style))

        # Comment cell
        row_cells.append(
            html.Td(metric['comment'], style={
                "padding": "12px 16px",
                "fontSize": "12px",
                "color": COLORS['gray']['400'] if dark_mode else COLORS['gray']['500'],
                "backgroundColor": alt_row_bg if idx % 2 == 0 else row_bg,
                "borderBottom": f"1px solid {border_color}",
                "fontStyle": "italic"
            })
        )

        rows.append(html.Tr(row_cells))

    return html.Div([
        html.Table([
            html.Thead([html.Tr(header_cells)]),
            html.Tbody(rows)
        ], style={
            "width": "100%",
            "borderCollapse": "collapse",
            "borderRadius": "8px",
            "overflow": "hidden",
            "border": f"1px solid {border_color}"
        })
    ], style={"overflowX": "auto"})

# Callback for Industry Median Benchmarking Table
@app.callback(
    Output('industry-median-table', 'children'),
    [Input('dark-mode-store', 'data'),
     Input('user-company-store', 'data'),
     Input('selected-competitors-store', 'data')]
)
def render_industry_median_table(dark_mode, user_company, selected_competitors):
    """Render the industry median benchmarking table"""

    # Get data for calculating industry median
    df = get_competitor_data()

    if df is None or df.empty:
        return html.Div("No industry data available", style={
            "textAlign": "center", "padding": "40px", "color": COLORS['gray']['500']
        })

    text_color = COLORS['gray']['100'] if dark_mode else COLORS['gray']['900']
    header_bg = COLORS['gray']['700'] if dark_mode else COLORS['gray']['100']
    row_bg = COLORS['gray']['800'] if dark_mode else "#ffffff"
    alt_row_bg = COLORS['gray']['750'] if dark_mode else COLORS['gray']['50']
    border_color = COLORS['gray']['600'] if dark_mode else COLORS['gray']['200']

    # Get user company values
    user_company_name = "Your Company"
    user_values = {}
    if user_company:
        user_company_name = user_company.get('company_name', 'Your Company')
        user_values = {
            'EBITDA_MARGIN': user_company.get('EBITDA_MARGIN', 0),
            'GROSS_MARGIN': user_company.get('GROSS_MARGIN', 0),
            'CUR_RATIO': user_company.get('CUR_RATIO', 0),
            'QUICK_RATIO': user_company.get('QUICK_RATIO', 0),
            'TOT_DEBT_TO_TOT_ASSET': user_company.get('TOT_DEBT_TO_TOT_ASSET', 0),
            'INTEREST_COVERAGE_RATIO': user_company.get('INTEREST_COVERAGE_RATIO', 0),
        }
    else:
        # Use first selected company as "your company" for demo
        if selected_competitors and len(selected_competitors) > 0:
            first_company = df[df['TICKER'] == selected_competitors[0]]
            if not first_company.empty:
                user_company_name = selected_competitors[0]
                user_values = {
                    'EBITDA_MARGIN': first_company['EBITDA_MARGIN'].iloc[0],
                    'GROSS_MARGIN': first_company['GROSS_MARGIN'].iloc[0],
                    'CUR_RATIO': first_company['CUR_RATIO'].iloc[0],
                    'QUICK_RATIO': first_company['QUICK_RATIO'].iloc[0],
                    'TOT_DEBT_TO_TOT_ASSET': first_company['TOT_DEBT_TO_TOT_ASSET'].iloc[0],
                    'INTEREST_COVERAGE_RATIO': first_company['INTEREST_COVERAGE_RATIO'].iloc[0],
                }

    # Calculate industry medians
    industry_medians = {
        'EBITDA_MARGIN': df['EBITDA_MARGIN'].median(),
        'GROSS_MARGIN': df['GROSS_MARGIN'].median(),
        'CUR_RATIO': df['CUR_RATIO'].median(),
        'QUICK_RATIO': df['QUICK_RATIO'].median(),
        'TOT_DEBT_TO_TOT_ASSET': df['TOT_DEBT_TO_TOT_ASSET'].median(),
        'INTEREST_COVERAGE_RATIO': df['INTEREST_COVERAGE_RATIO'].median(),
    }

    # Define metrics with interpretation
    metrics_config = [
        {'key': 'EBITDA_MARGIN', 'label': 'EBITDA Margin', 'format': '{:.1f}%', 'higher_is_better': True,
         'good_text': 'Superior efficiency vs industry', 'bad_text': 'Below industry efficiency'},
        {'key': 'GROSS_MARGIN', 'label': 'Gross Margin', 'format': '{:.1f}%', 'higher_is_better': True,
         'good_text': 'Strong pricing power', 'bad_text': 'Pricing pressure vs peers'},
        {'key': 'CUR_RATIO', 'label': 'Current Ratio', 'format': '{:.2f}x', 'higher_is_better': True,
         'good_text': 'Healthy liquidity position', 'bad_text': 'Liquidity below industry norm'},
        {'key': 'QUICK_RATIO', 'label': 'Quick Ratio', 'format': '{:.2f}x', 'higher_is_better': True,
         'good_text': 'Strong quick liquidity', 'bad_text': 'Quick liquidity needs attention'},
        {'key': 'TOT_DEBT_TO_TOT_ASSET', 'label': 'Debt/Asset', 'format': '{:.1f}%', 'higher_is_better': False,
         'good_text': 'Conservative leverage - lower risk', 'bad_text': 'Higher leverage than industry'},
        {'key': 'INTEREST_COVERAGE_RATIO', 'label': 'Interest Coverage', 'format': '{:.1f}x', 'higher_is_better': True,
         'good_text': 'Strong debt service capacity', 'bad_text': 'Debt service capacity below median'},
    ]

    # Build table header
    header_cells = [
        html.Th("Metric", style={"padding": "12px 16px", "textAlign": "left", "fontWeight": "600", "fontSize": "13px", "color": text_color, "backgroundColor": header_bg, "borderBottom": f"2px solid {COLORS['success']}", "minWidth": "140px"}),
        html.Th(user_company_name, style={"padding": "12px 16px", "textAlign": "center", "fontWeight": "600", "fontSize": "13px", "color": text_color, "backgroundColor": COLORS['primary'] + "20", "borderBottom": f"2px solid {COLORS['success']}", "minWidth": "100px"}),
        html.Th("Industry Median", style={"padding": "12px 16px", "textAlign": "center", "fontWeight": "600", "fontSize": "13px", "color": text_color, "backgroundColor": header_bg, "borderBottom": f"2px solid {COLORS['success']}", "minWidth": "120px"}),
        html.Th("Difference", style={"padding": "12px 16px", "textAlign": "center", "fontWeight": "600", "fontSize": "13px", "color": text_color, "backgroundColor": header_bg, "borderBottom": f"2px solid {COLORS['success']}", "minWidth": "100px"}),
        html.Th("Interpretation", style={"padding": "12px 16px", "textAlign": "left", "fontWeight": "600", "fontSize": "13px", "color": text_color, "backgroundColor": header_bg, "borderBottom": f"2px solid {COLORS['success']}", "minWidth": "200px"}),
    ]

    # Build table rows
    rows = []
    for idx, metric in enumerate(metrics_config):
        user_val = user_values.get(metric['key'], 0) or 0
        median_val = industry_medians.get(metric['key'], 0) or 0
        diff = user_val - median_val

        # Determine if good or bad
        if metric['higher_is_better']:
            is_good = diff >= 0
        else:
            is_good = diff <= 0

        color = COLORS['success'] if is_good else COLORS['danger']
        interpretation = metric['good_text'] if is_good else metric['bad_text']

        # Format difference with sign
        if 'x' in metric['format']:
            diff_formatted = f"+{diff:.2f}x" if diff >= 0 else f"{diff:.2f}x"
        else:
            diff_formatted = f"+{diff:.1f}%" if diff >= 0 else f"{diff:.1f}%"

        row_bg_color = alt_row_bg if idx % 2 == 0 else row_bg

        rows.append(html.Tr([
            html.Td(metric['label'], style={
                "padding": "12px 16px", "fontWeight": "500", "fontSize": "13px", "color": text_color,
                "backgroundColor": row_bg_color, "borderBottom": f"1px solid {border_color}"
            }),
            html.Td(metric['format'].format(user_val), style={
                "padding": "12px 16px", "textAlign": "center", "fontSize": "13px", "fontWeight": "600",
                "color": text_color, "backgroundColor": COLORS['primary'] + "10", "borderBottom": f"1px solid {border_color}"
            }),
            html.Td(metric['format'].format(median_val), style={
                "padding": "12px 16px", "textAlign": "center", "fontSize": "13px",
                "color": COLORS['gray']['400'], "backgroundColor": row_bg_color, "borderBottom": f"1px solid {border_color}"
            }),
            html.Td([
                html.Span(diff_formatted, style={
                    "color": color,
                    "fontWeight": "600",
                    "backgroundColor": f"{color}15",
                    "padding": "4px 10px",
                    "borderRadius": "4px",
                    "fontSize": "12px"
                }),
                html.I(className=f"fas fa-arrow-{'up' if is_good else 'down'} ms-2", style={
                    "fontSize": "10px",
                    "color": color
                })
            ], style={
                "padding": "12px 16px", "textAlign": "center",
                "backgroundColor": row_bg_color, "borderBottom": f"1px solid {border_color}"
            }),
            html.Td([
                html.I(className=f"fas fa-{'check-circle' if is_good else 'exclamation-circle'} me-2", style={
                    "fontSize": "12px",
                    "color": color
                }),
                html.Span(interpretation, style={"color": color, "fontSize": "12px"})
            ], style={
                "padding": "12px 16px", "textAlign": "left",
                "backgroundColor": row_bg_color, "borderBottom": f"1px solid {border_color}"
            })
        ]))

    return html.Div([
        html.Table([
            html.Thead([html.Tr(header_cells)]),
            html.Tbody(rows)
        ], style={
            "width": "100%",
            "borderCollapse": "collapse",
            "borderRadius": "8px",
            "overflow": "hidden",
            "border": f"1px solid {border_color}"
        })
    ], style={"overflowX": "auto"})

# Callback to handle chart type button clicks
@app.callback(
    [Output('chart-type-store', 'data'),
     Output('chart-type-bar', 'style'),
     Output('chart-type-line', 'style'),
     Output('chart-type-pie', 'style')],
    [Input('chart-type-bar', 'n_clicks'),
     Input('chart-type-line', 'n_clicks'),
     Input('chart-type-pie', 'n_clicks')],
    [State('dark-mode-store', 'data')]
)
def update_chart_type(bar_clicks, line_clicks, pie_clicks, dark_mode):
    ctx = callback_context

    base_style = {
        "border": f"1px solid {COLORS['gray']['600'] if dark_mode else COLORS['gray']['300']}",
        "borderRadius": "20px",
        "padding": "6px 14px",
        "backgroundColor": "transparent",
        "cursor": "pointer",
        "display": "inline-flex",
        "alignItems": "center",
        "justifyContent": "center",
        "fontSize": "13px",
        "fontWeight": "500",
        "color": COLORS['gray']['400'] if dark_mode else COLORS['gray']['600'],
        "transition": "all 0.2s ease"
    }

    active_style = {
        **base_style,
        "backgroundColor": COLORS['primary'],
        "borderColor": COLORS['primary'],
        "color": "#ffffff"
    }

    # Default to bar chart
    if not ctx.triggered or ctx.triggered[0]['prop_id'] == '.':
        return 'bar', active_style, base_style, base_style

    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if triggered_id == 'chart-type-bar':
        return 'bar', active_style, base_style, base_style
    elif triggered_id == 'chart-type-line':
        return 'line', base_style, active_style, base_style
    elif triggered_id == 'chart-type-pie':
        return 'pie', base_style, base_style, active_style

    return 'bar', active_style, base_style, base_style

# Callback to handle view mode button clicks
@app.callback(
    [Output('view-mode-store', 'data'),
     Output('view-mode-graph', 'style'),
     Output('view-mode-table', 'style')],
    [Input('view-mode-graph', 'n_clicks'),
     Input('view-mode-table', 'n_clicks')],
    [State('dark-mode-store', 'data')]
)
def update_view_mode(graph_clicks, table_clicks, dark_mode):
    ctx = callback_context

    base_style = {
        "border": f"1px solid {COLORS['gray']['600'] if dark_mode else COLORS['gray']['300']}",
        "borderRadius": "20px",
        "padding": "6px 14px",
        "backgroundColor": "transparent",
        "cursor": "pointer",
        "display": "inline-flex",
        "alignItems": "center",
        "justifyContent": "center",
        "fontSize": "13px",
        "fontWeight": "500",
        "color": COLORS['gray']['400'] if dark_mode else COLORS['gray']['600'],
        "transition": "all 0.2s ease"
    }

    active_style = {
        **base_style,
        "backgroundColor": COLORS['primary'],
        "borderColor": COLORS['primary'],
        "color": "#ffffff"
    }

    # Default to graph view
    if not ctx.triggered or ctx.triggered[0]['prop_id'] == '.':
        return 'graph', active_style, base_style

    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if triggered_id == 'view-mode-graph':
        return 'graph', active_style, base_style
    elif triggered_id == 'view-mode-table':
        return 'table', base_style, active_style

    return 'graph', active_style, base_style

# Callback to render company comparison cards
@app.callback(
    Output('company-comparison-cards', 'children'),
    [Input('selected-competitors-store', 'data'),
     Input('dark-mode-store', 'data'),
     Input('user-company-store', 'data')]
)
def render_comparison_cards(selected_competitors, dark_mode, user_company):
    """Render individual company comparison cards with color-coded metrics"""

    # Get data
    df = get_competitor_data()

    if df is None:
        df = pd.DataFrame()

    # Add user company data if available
    user_company_name = None
    if user_company:
        user_company_name = user_company.get('company_name', 'Your Company')
        user_row = {
            'TICKER': user_company_name,
            'TOT_DEBT_TO_TOT_ASSET': user_company.get('TOT_DEBT_TO_TOT_ASSET', 0),
            'CASH_DVD_COVERAGE': user_company.get('CASH_DVD_COVERAGE', 0),
            'TOT_DEBT_TO_EBITDA': user_company.get('TOT_DEBT_TO_EBITDA', 0),
            'CUR_RATIO': user_company.get('CUR_RATIO', 0),
            'QUICK_RATIO': user_company.get('QUICK_RATIO', 0),
            'GROSS_MARGIN': user_company.get('GROSS_MARGIN', 0),
            'INTEREST_COVERAGE_RATIO': user_company.get('INTEREST_COVERAGE_RATIO', 0),
            'EBITDA_MARGIN': user_company.get('EBITDA_MARGIN', 0),
            'NET_DEBT_TO_SHRHLDR_EQTY': user_company.get('NET_DEBT_TO_SHRHLDR_EQTY', 0)
        }
        user_df = pd.DataFrame([user_row])
        df = pd.concat([user_df, df], ignore_index=True)

    if df.empty or not selected_competitors:
        return html.Div("Select companies to compare", style={
            "textAlign": "center",
            "padding": "40px",
            "color": COLORS['gray']['500']
        })

    # Filter for selected competitors
    df_filtered = df[df['TICKER'].isin(selected_competitors)]

    # Remove duplicates - keep only one row per ticker
    df_filtered = df_filtered.drop_duplicates(subset=['TICKER'], keep='first')

    if df_filtered.empty:
        return html.Div("No data available", style={
            "textAlign": "center",
            "padding": "40px",
            "color": COLORS['gray']['500']
        })

    # Metrics to compare with their ideal direction (higher_is_better)
    comparison_metrics = [
        {'key': 'EBITDA_MARGIN', 'label': 'EBITDA Margin', 'higher_is_better': True, 'suffix': '%'},
        {'key': 'GROSS_MARGIN', 'label': 'Gross Margin', 'higher_is_better': True, 'suffix': '%'},
        {'key': 'CUR_RATIO', 'label': 'Current Ratio', 'higher_is_better': True, 'suffix': ''},
        {'key': 'QUICK_RATIO', 'label': 'Quick Ratio', 'higher_is_better': True, 'suffix': ''},
        {'key': 'TOT_DEBT_TO_TOT_ASSET', 'label': 'Debt/Asset', 'higher_is_better': False, 'suffix': '%'},
        {'key': 'INTEREST_COVERAGE_RATIO', 'label': 'Interest Coverage', 'higher_is_better': True, 'suffix': 'x'},
    ]

    # Calculate percentiles for color coding
    def get_color_for_value(value, all_values, higher_is_better):
        """Determine color based on percentile ranking"""
        if pd.isna(value) or len(all_values) == 0:
            return COLORS['gray']['400']

        sorted_vals = sorted([v for v in all_values if not pd.isna(v)])
        if len(sorted_vals) == 0:
            return COLORS['gray']['400']

        # Calculate percentile
        rank = sum(1 for v in sorted_vals if v <= value) / len(sorted_vals)

        if higher_is_better:
            if rank >= 0.66:
                return '#10b981'  # Green - good
            elif rank >= 0.33:
                return COLORS['warning']  # Yellow - medium
            else:
                return '#ef4444'  # Red - bad
        else:
            if rank <= 0.33:
                return '#10b981'  # Green - good (lower is better)
            elif rank <= 0.66:
                return COLORS['warning']  # Yellow - medium
            else:
                return '#ef4444'  # Red - bad

    # Build cards for each company
    cards = []
    text_color = COLORS['gray']['100'] if dark_mode else COLORS['gray']['900']
    card_bg = COLORS['gray']['700'] if dark_mode else COLORS['gray']['50']

    for _, row in df_filtered.iterrows():
        company_name = row['TICKER']
        is_user_company = user_company_name and company_name == user_company_name

        # Company card header style
        header_bg = COLORS['primary'] if is_user_company else (COLORS['gray']['600'] if dark_mode else COLORS['gray']['200'])
        header_text = '#ffffff' if is_user_company else text_color

        metric_rows = []
        for metric in comparison_metrics:
            value = row.get(metric['key'], 0)
            all_values = df_filtered[metric['key']].tolist()
            color = get_color_for_value(value, all_values, metric['higher_is_better'])

            # Format value
            if pd.isna(value):
                formatted_value = "-"
            elif metric['suffix'] == '%':
                formatted_value = f"{value:.1f}%"
            elif metric['suffix'] == 'x':
                formatted_value = f"{value:.1f}x"
            else:
                formatted_value = f"{value:.2f}"

            metric_rows.append(
                html.Div([
                    html.Span(metric['label'], style={
                        "fontSize": "11px",
                        "color": COLORS['gray']['500'],
                        "flex": "1"
                    }),
                    html.Span(formatted_value, style={
                        "fontSize": "13px",
                        "fontWeight": "600",
                        "color": color,
                        "backgroundColor": f"{color}15",
                        "padding": "2px 8px",
                        "borderRadius": "4px"
                    })
                ], style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "center",
                    "padding": "6px 0",
                    "borderBottom": f"1px solid {COLORS['gray']['600'] if dark_mode else COLORS['gray']['200']}"
                })
            )

        # Remove border from last row
        if metric_rows:
            last_row_style = metric_rows[-1].style.copy() if hasattr(metric_rows[-1], 'style') else {}
            metric_rows[-1] = html.Div([
                html.Span(comparison_metrics[-1]['label'], style={
                    "fontSize": "11px",
                    "color": COLORS['gray']['500'],
                    "flex": "1"
                }),
                html.Span(
                    f"{row.get(comparison_metrics[-1]['key'], 0):.1f}x" if comparison_metrics[-1]['suffix'] == 'x' else
                    f"{row.get(comparison_metrics[-1]['key'], 0):.1f}%" if comparison_metrics[-1]['suffix'] == '%' else
                    f"{row.get(comparison_metrics[-1]['key'], 0):.2f}",
                    style={
                        "fontSize": "13px",
                        "fontWeight": "600",
                        "color": get_color_for_value(
                            row.get(comparison_metrics[-1]['key'], 0),
                            df_filtered[comparison_metrics[-1]['key']].tolist(),
                            comparison_metrics[-1]['higher_is_better']
                        ),
                        "backgroundColor": f"{get_color_for_value(row.get(comparison_metrics[-1]['key'], 0), df_filtered[comparison_metrics[-1]['key']].tolist(), comparison_metrics[-1]['higher_is_better'])}15",
                        "padding": "2px 8px",
                        "borderRadius": "4px"
                    }
                )
            ], style={
                "display": "flex",
                "justifyContent": "space-between",
                "alignItems": "center",
                "padding": "6px 0"
            })

        cards.append(
            html.Div([
                # Company Header
                html.Div([
                    html.Div([
                        html.I(className="fas fa-building me-2" if not is_user_company else "fas fa-star me-2", style={
                            "fontSize": "12px"
                        }),
                        html.Span(company_name, style={
                            "fontWeight": "600",
                            "fontSize": "13px"
                        })
                    ], style={"display": "flex", "alignItems": "center"}),
                    html.Span("Your Company" if is_user_company else "", style={
                        "fontSize": "10px",
                        "opacity": "0.8"
                    }) if is_user_company else None
                ], style={
                    "backgroundColor": header_bg,
                    "color": header_text,
                    "padding": "10px 12px",
                    "borderRadius": "8px 8px 0 0",
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "center"
                }),
                # Metrics
                html.Div(metric_rows, style={
                    "padding": "8px 12px",
                    "backgroundColor": card_bg,
                    "borderRadius": "0 0 8px 8px"
                })
            ], style={
                "border": f"1px solid {COLORS['gray']['600'] if dark_mode else COLORS['gray']['200']}",
                "borderRadius": "8px",
                "overflow": "hidden",
                "minWidth": "220px",
                "flex": "1"
            })
        )

    # Return cards in a horizontal scrollable row
    return html.Div(cards, style={
        "display": "flex",
        "gap": "16px",
        "overflowX": "auto",
        "paddingBottom": "8px"
    })

# Main callback to render chart or table
@app.callback(
    Output('competitor-chart-container', 'children'),
    [Input('competitor-metric-selector', 'value'),
     Input('chart-type-store', 'data'),
     Input('view-mode-store', 'data'),
     Input('selected-competitors-store', 'data'),
     Input('dark-mode-store', 'data'),
     Input('user-company-store', 'data')]
)
def render_competitor_chart(selected_metric, chart_type, view_mode, selected_competitors, dark_mode, user_company):
    """Render the chart or table based on filters"""

    # Get data
    df = get_competitor_data()

    if df is None:
        df = pd.DataFrame()

    # Add user company data if available
    if user_company:
        user_company_name = user_company.get('company_name', 'Your Company')
        user_row = {
            'TICKER': user_company_name,
            'IDENTIFIER_TYPE': 'USER',
            'IDENTIFIER_VALUE': 'User Input',
            'TOT_DEBT_TO_TOT_ASSET': user_company.get('TOT_DEBT_TO_TOT_ASSET', 0),
            'CASH_DVD_COVERAGE': user_company.get('CASH_DVD_COVERAGE', 0),
            'TOT_DEBT_TO_EBITDA': user_company.get('TOT_DEBT_TO_EBITDA', 0),
            'CUR_RATIO': user_company.get('CUR_RATIO', 0),
            'QUICK_RATIO': user_company.get('QUICK_RATIO', 0),
            'GROSS_MARGIN': user_company.get('GROSS_MARGIN', 0),
            'INTEREST_COVERAGE_RATIO': user_company.get('INTEREST_COVERAGE_RATIO', 0),
            'EBITDA_MARGIN': user_company.get('EBITDA_MARGIN', 0),
            'TOT_LIAB_AND_EQY': 0,
            'NET_DEBT_TO_SHRHLDR_EQTY': user_company.get('NET_DEBT_TO_SHRHLDR_EQTY', 0)
        }
        user_df = pd.DataFrame([user_row])
        df = pd.concat([user_df, df], ignore_index=True)

    if df.empty or not selected_competitors:
        return html.Div("No data available", style={"textAlign": "center", "padding": "40px"})

    # Filter for selected competitors
    df_filtered = df[df['TICKER'].isin(selected_competitors)]

    # Remove duplicates - keep only one row per ticker
    df_filtered = df_filtered.drop_duplicates(subset=['TICKER'], keep='first')

    if df_filtered.empty:
        return html.Div("No data for selected competitors", style={"textAlign": "center", "padding": "40px"})

    text_color = COLORS['gray']['100'] if dark_mode else COLORS['gray']['900']

    # Table View
    if view_mode == 'table':
        # Create table with all numeric metrics
        table_columns = ['TICKER'] + NUMERIC_METRIC_COLUMNS
        table_df = df_filtered[table_columns].copy()

        # Format numeric columns
        for col in NUMERIC_METRIC_COLUMNS:
            table_df[col] = table_df[col].apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "-")

        # Rename columns for display
        table_df.columns = ['Ticker'] + [METRIC_LABELS.get(col, col) for col in NUMERIC_METRIC_COLUMNS]

        header_style = {
            "backgroundColor": COLORS['gray']['700'] if dark_mode else COLORS['gray']['100'],
            "color": text_color,
            "fontWeight": "600",
            "padding": "12px",
            "textAlign": "left",
            "borderBottom": f"2px solid {COLORS['primary']}"
        }

        cell_style = {
            "padding": "12px",
            "borderBottom": f"1px solid {COLORS['gray']['700'] if dark_mode else COLORS['gray']['200']}",
            "color": text_color
        }

        return html.Div([
            html.Table([
                html.Thead([
                    html.Tr([html.Th(col, style=header_style) for col in table_df.columns])
                ]),
                html.Tbody([
                    html.Tr([
                        html.Td(table_df.iloc[i][col], style=cell_style)
                        for col in table_df.columns
                    ]) for i in range(len(table_df))
                ])
            ], style={
                "width": "100%",
                "borderCollapse": "collapse",
                "fontSize": "14px"
            })
        ], style={"overflowX": "auto"})

    # Graph View
    companies = df_filtered['TICKER'].tolist()
    values = df_filtered[selected_metric].tolist()
    metric_label = METRIC_LABELS.get(selected_metric, selected_metric)

    # Color palette for charts
    colors = [COLORS['primary'], COLORS['success'], COLORS['warning'], COLORS['danger'],
              COLORS['info'], COLORS['purple'], '#ec4899', '#14b8a6', '#f97316', '#84cc16']

    fig = go.Figure()

    if chart_type == 'bar':
        fig.add_trace(go.Bar(
            x=companies,
            y=values,
            marker_color=[colors[i % len(colors)] for i in range(len(companies))],
            text=[f"{v:.2f}" for v in values],
            textposition='outside'
        ))
        fig.update_layout(
            title=f"{metric_label} by Company",
            xaxis_title="Company",
            yaxis_title=metric_label
        )

    elif chart_type == 'line':
        fig.add_trace(go.Scatter(
            x=companies,
            y=values,
            mode='lines+markers+text',
            line=dict(color=COLORS['primary'], width=3),
            marker=dict(size=10, color=COLORS['primary']),
            text=[f"{v:.2f}" for v in values],
            textposition='top center'
        ))
        fig.update_layout(
            title=f"{metric_label} by Company",
            xaxis_title="Company",
            yaxis_title=metric_label
        )

    elif chart_type == 'pie':
        # Handle negative values for pie chart
        abs_values = [abs(v) for v in values]
        labels = [f"{c} ({v:.2f})" for c, v in zip(companies, values)]

        fig.add_trace(go.Pie(
            labels=labels,
            values=abs_values,
            marker=dict(colors=[colors[i % len(colors)] for i in range(len(companies))]),
            textinfo='percent+label',
            hole=0.3
        ))
        fig.update_layout(
            title=f"{metric_label} Distribution"
        )

    # Common layout settings
    fig.update_layout(
        height=400,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color=text_color),
        margin=dict(t=50, b=50, l=50, r=50),
        showlegend=False if chart_type != 'pie' else True
    )

    if chart_type != 'pie':
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(showgrid=True, gridcolor=COLORS['gray']['700'] if dark_mode else COLORS['gray']['200'])

    return dcc.Graph(figure=fig, config={'displayModeBar': False})

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
     Input('dark-mode-store', 'data'),
     Input('selected-competitors-store', 'data'),
     Input('user-company-store', 'data')]
)
def update_margin_bridge(timestamp, dark_mode, selected_competitors, user_company):
    """Margin bridge waterfall chart showing revenue to net income breakdown"""

    card_style = {
        "backgroundColor": COLORS['gray']['800'] if dark_mode else "#ffffff",
        "border": f"1px solid {COLORS['gray']['700'] if dark_mode else COLORS['gray']['200']}",
        "borderRadius": "12px",
        "padding": "24px",
        "marginBottom": "20px"
    }

    # Default values (will be overwritten with actual data)
    avg_revenue = 100000.0
    avg_cogs = 40000.0
    avg_gross_profit = 60000.0
    avg_sga = 20000.0
    avg_ebitda = 30000.0
    avg_da = 5000.0
    avg_ebit = 25000.0
    avg_interest = 1000.0
    avg_tax = 5000.0
    avg_net_income = 19000.0
    avg_gross_margin = 60.0
    avg_ebitda_margin = 30.0
    avg_ebit_margin = 25.0
    avg_net_margin = 19.0

    try:
        # Get annual financials data from HANA or CSV
        df = None
        if data_service and data_service.connected:
            df = data_service.get_annual_financials(selected_competitors)
        elif csv_data and csv_data.get('annual_financials') is not None:
            df = csv_data['annual_financials'].copy()
            if selected_competitors:
                df = df[df['TICKER'].isin(selected_competitors)]

        if df is not None and not df.empty:
            # Remove user company from calculations if present
            user_company_name = user_company.get('company_name') if user_company else None
            if user_company_name:
                df = df[df['TICKER'] != user_company_name]

            # Deduplicate - keep first row per ticker
            df = df.drop_duplicates(subset=['TICKER'], keep='first')

            if not df.empty:
                # Get actual financial values (averages across selected companies)
                avg_revenue = df['SALES_REV_TURN'].mean() if 'SALES_REV_TURN' in df.columns else avg_revenue
                avg_cogs = df['IS_COG_AND_SERVICES_SOLD'].mean() if 'IS_COG_AND_SERVICES_SOLD' in df.columns else avg_cogs
                avg_gross_profit = df['GROSS_PROFIT'].mean() if 'GROSS_PROFIT' in df.columns else avg_gross_profit
                avg_sga = df['IS_SGA_EXPENSE'].mean() if 'IS_SGA_EXPENSE' in df.columns else avg_sga
                avg_ebitda = df['EBITDA'].mean() if 'EBITDA' in df.columns else avg_ebitda
                avg_da = df['IS_DEPRECIATION_AND_AMORTIZATION'].mean() if 'IS_DEPRECIATION_AND_AMORTIZATION' in df.columns else avg_da
                avg_ebit = df['EBIT'].mean() if 'EBIT' in df.columns else avg_ebit
                avg_interest = df['IS_INT_EXPENSE'].mean() if 'IS_INT_EXPENSE' in df.columns else avg_interest
                avg_tax = df['IS_INC_TAX_EXP'].mean() if 'IS_INC_TAX_EXP' in df.columns else avg_tax
                avg_net_income = df['NET_INCOME'].mean() if 'NET_INCOME' in df.columns else avg_net_income

                # Get margin percentages
                avg_gross_margin = df['GROSS_MARGIN'].mean() if 'GROSS_MARGIN' in df.columns else (avg_gross_profit / avg_revenue * 100 if avg_revenue else 0)
                avg_ebitda_margin = df['EBITDA_MARGIN'].mean() if 'EBITDA_MARGIN' in df.columns else (avg_ebitda / avg_revenue * 100 if avg_revenue else 0)
                avg_ebit_margin = df['OPER_MARGIN'].mean() if 'OPER_MARGIN' in df.columns else (avg_ebit / avg_revenue * 100 if avg_revenue else 0)
                avg_net_margin = df['PROF_MARGIN'].mean() if 'PROF_MARGIN' in df.columns else (avg_net_income / avg_revenue * 100 if avg_revenue else 0)

                # Handle NaN values
                avg_da = avg_da if pd.notnull(avg_da) else (avg_ebitda - avg_ebit)
                avg_sga = avg_sga if pd.notnull(avg_sga) else (avg_gross_profit - avg_ebitda)

    except Exception as e:
        logger.error(f"Error calculating margin bridge data: {e}")

    # Calculate OpEx (difference between Gross Profit and EBITDA)
    opex = avg_gross_profit - avg_ebitda if pd.notnull(avg_gross_profit) and pd.notnull(avg_ebitda) else avg_sga
    # D&A (difference between EBITDA and EBIT)
    da = avg_ebitda - avg_ebit if pd.notnull(avg_ebitda) and pd.notnull(avg_ebit) else avg_da
    # Interest & Taxes (difference between EBIT and Net Income)
    interest_taxes = avg_ebit - avg_net_income if pd.notnull(avg_ebit) and pd.notnull(avg_net_income) else (avg_interest + avg_tax)

    # Margin bridge data (in millions)
    bridge_data = [
        {'step': 'Revenue', 'value': avg_revenue, 'type': 'total'},
        {'step': 'COGS', 'value': -avg_cogs if pd.notnull(avg_cogs) else -(avg_revenue - avg_gross_profit), 'type': 'relative'},
        {'step': 'Gross Profit', 'value': avg_gross_profit, 'type': 'total'},
        {'step': 'OpEx (SG&A)', 'value': -opex, 'type': 'relative'},
        {'step': 'EBITDA', 'value': avg_ebitda, 'type': 'total'},
        {'step': 'D&A', 'value': -da, 'type': 'relative'},
        {'step': 'EBIT', 'value': avg_ebit, 'type': 'total'},
        {'step': 'Interest & Tax', 'value': -interest_taxes, 'type': 'relative'},
        {'step': 'Net Income', 'value': avg_net_income, 'type': 'total'},
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

    # Margin metrics cards - using calculated averages from selected competitors
    margin_metrics = [
        {'label': 'Gross Margin', 'value': avg_gross_margin, 'target': avg_gross_margin * 1.05, 'icon': 'fa-chart-line'},
        {'label': 'EBITDA Margin', 'value': avg_ebitda_margin, 'target': avg_ebitda_margin * 1.1, 'icon': 'fa-coins'},
        {'label': 'EBIT Margin', 'value': avg_ebit_margin, 'target': avg_ebit_margin * 1.1, 'icon': 'fa-percentage'},
        {'label': 'Net Margin', 'value': avg_net_margin, 'target': avg_net_margin * 1.15, 'icon': 'fa-trophy'}
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

#==============================================================================
# ADVANCED CHARTS SECTION
#==============================================================================

@app.callback(
    Output('advanced-charts-container', 'children'),
    [Input('update-timestamp', 'data'),
     Input('dark-mode-store', 'data')]
)
def update_advanced_charts(timestamp, dark_mode):
    """Create advanced charts visualization section"""

    # Initialize advanced charts
    advanced_charts = AdvancedCharts(colors=COLORS)
    config = advanced_charts.create_responsive_config()

    # Create example charts
    waterfall = example_waterfall()
    sankey = example_sankey()
    heatmap = example_heatmap()
    treemap = example_treemap()
    funnel = example_funnel()

    card_style = {
        "backgroundColor": COLORS['gray']['800'] if dark_mode else "#ffffff",
        "border": f"1px solid {COLORS['gray']['700'] if dark_mode else COLORS['gray']['200']}",
        "borderRadius": "12px",
        "marginBottom": "24px"
    }

    header_style = {
        "backgroundColor": COLORS['gray']['700'] if dark_mode else COLORS['gray']['50'],
        "color": COLORS['gray']['100'] if dark_mode else COLORS['gray']['800'],
        "padding": "16px 24px",
        "borderBottom": f"1px solid {COLORS['gray']['600'] if dark_mode else COLORS['gray']['200']}",
        "borderRadius": "12px 12px 0 0"
    }

    description_style = {
        "color": COLORS['gray']['400'] if dark_mode else COLORS['gray']['600'],
        "marginBottom": "16px",
        "fontSize": "14px"
    }

    return html.Div([
        html.H2("Advanced Charts", style={
            "marginBottom": "16px",
            "color": COLORS['gray']['100'] if dark_mode else COLORS['gray']['900']
        }),
        html.P("Professional financial visualizations with responsive design", style={
            "marginBottom": "32px",
            "color": COLORS['gray']['400'] if dark_mode else COLORS['gray']['600']
        }),

        # Waterfall Chart
        dbc.Card([
            html.Div([
                html.H4([
                    html.I(className="fas fa-chart-waterfall", style={"marginRight": "12px"}),
                    "Waterfall Chart - Revenue Bridge Analysis"
                ], style={"margin": 0})
            ], style=header_style),
            dbc.CardBody([
                html.P("Perfect for showing how values change from one period to another. "
                      "Great for variance analysis and explaining revenue/profit changes.",
                      style=description_style),
                dcc.Graph(figure=waterfall, config=config, style={'height': '450px'})
            ])
        ], style=card_style),

        # Sankey Diagram
        dbc.Card([
            html.Div([
                html.H4([
                    html.I(className="fas fa-project-diagram", style={"marginRight": "12px"}),
                    "Sankey Diagram - Flow Analysis"
                ], style={"margin": 0})
            ], style=header_style),
            dbc.CardBody([
                html.P("Shows flow of revenue/costs through different channels. "
                      "Ideal for understanding distribution patterns.",
                      style=description_style),
                dcc.Graph(figure=sankey, config=config, style={'height': '550px'})
            ])
        ], style=card_style),

        # Heatmap
        dbc.Card([
            html.Div([
                html.H4([
                    html.I(className="fas fa-th", style={"marginRight": "12px"}),
                    "Heatmap - Performance Matrix"
                ], style={"margin": 0})
            ], style=header_style),
            dbc.CardBody([
                html.P("Visualizes performance scores across products and time periods. "
                      "Quick way to spot high/low performers.",
                      style=description_style),
                dcc.Graph(figure=heatmap, config=config, style={'height': '450px'})
            ])
        ], style=card_style),

        # Treemap
        dbc.Card([
            html.Div([
                html.H4([
                    html.I(className="fas fa-layer-group", style={"marginRight": "12px"}),
                    "Treemap - Hierarchical Breakdown"
                ], style={"margin": 0})
            ], style=header_style),
            dbc.CardBody([
                html.P("Shows proportional distribution in a space-efficient way. "
                      "Perfect for revenue/cost breakdowns.",
                      style=description_style),
                dcc.Graph(figure=treemap, config=config, style={'height': '550px'})
            ])
        ], style=card_style),

        # Funnel Chart
        dbc.Card([
            html.Div([
                html.H4([
                    html.I(className="fas fa-filter", style={"marginRight": "12px"}),
                    "Funnel Chart - Conversion Analysis"
                ], style={"margin": 0})
            ], style=header_style),
            dbc.CardBody([
                html.P("Tracks conversion rates through stages. "
                      "Ideal for sales pipelines and customer journeys.",
                      style=description_style),
                dcc.Graph(figure=funnel, config=config, style={'height': '450px'})
            ])
        ], style=card_style)
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
