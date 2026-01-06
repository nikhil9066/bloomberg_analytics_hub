#!/usr/bin/env python3
"""
Test email configuration and send a test alert
"""

import os
from dotenv import load_dotenv
from datetime import datetime

# Load .env file
load_dotenv()

from utils.email_service import EmailService

# Check environment variables
print("=" * 70)
print("EMAIL CONFIGURATION CHECK")
print("=" * 70)
print()

sendgrid_api_key = os.getenv('SENDGRID_API_KEY', '')
from_email = os.getenv('SENDGRID_FROM_EMAIL', '')
notification_email = os.getenv('NOTIFICATION_EMAIL', '')

print(f"SENDGRID_API_KEY: {'✓ Set' if sendgrid_api_key else '✗ NOT SET'}")
if sendgrid_api_key:
    print(f"  Value: {sendgrid_api_key[:10]}..." if len(sendgrid_api_key) > 10 else f"  Value: {sendgrid_api_key}")

print(f"SENDGRID_FROM_EMAIL: {'✓ Set' if from_email else '✗ NOT SET'}")
if from_email:
    print(f"  Value: {from_email}")

print(f"NOTIFICATION_EMAIL: {'✓ Set' if notification_email else '✗ NOT SET'}")
if notification_email:
    print(f"  Value: {notification_email}")

print()
print("=" * 70)

# Initialize email service
email_service = EmailService()

print(f"Email Service Configured: {'✓ YES' if email_service.is_configured else '✗ NO'}")
print()

if email_service.is_configured:
    print("=" * 70)
    print("SENDING TEST EMAIL")
    print("=" * 70)
    print()

    # Send test failed login alert
    print("Sending failed login alert...")
    result = email_service.send_failed_login_alert(
        attempted_email="test@example.com",
        ip_address="127.0.0.1",
        timestamp=datetime.now()
    )

    if result:
        print("✓ Test email sent successfully!")
        print(f"  Check inbox: {notification_email}")
    else:
        print("✗ Failed to send test email")
        print("  Check the logs above for error details")
else:
    print("Email service is NOT configured.")
    print()
    print("To configure email alerts:")
    print("1. Set environment variables in .env file:")
    print("   SENDGRID_API_KEY=SG.your_key_here")
    print("   SENDGRID_FROM_EMAIL=your-verified-sender@example.com")
    print("   NOTIFICATION_EMAIL=admin@example.com")
    print()
    print("2. Or for Cloud Foundry, they should be in manifest.yml")

print()
print("=" * 70)
