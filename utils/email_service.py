"""
Email notification service for security alerts
Sends emails for failed login attempts and security events
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import os


class EmailService:
    """Service for sending security notification emails"""

    def __init__(self):
        """Initialize email service with SMTP configuration"""
        self.logger = logging.getLogger(__name__)

        # Email configuration from environment variables
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.sender_email = os.getenv('SENDER_EMAIL', '')
        self.sender_password = os.getenv('SENDER_PASSWORD', '')
        self.admin_email = os.getenv('ADMIN_EMAIL', '')

        # Check if email is configured
        self.is_configured = bool(self.sender_email and self.sender_password and self.admin_email)

        if not self.is_configured:
            self.logger.warning("Email service not fully configured. Notifications will be logged only.")

    def send_failed_login_alert(self, attempted_email, ip_address=None, timestamp=None):
        """
        Send email alert for failed login attempt

        Args:
            attempted_email (str): Email address that attempted to login
            ip_address (str): IP address of the attempt
            timestamp (datetime): Time of the attempt

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        if not timestamp:
            timestamp = datetime.now()

        subject = f"🚨 Security Alert: Failed Login Attempt"

        # Create email body
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 2px solid #ef4444; border-radius: 10px;">
                <h2 style="color: #ef4444;">🚨 Security Alert: Failed Login Attempt</h2>

                <p>A failed login attempt was detected on your Bloomberg Analytics Hub account.</p>

                <div style="background-color: #fee2e2; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3 style="margin-top: 0; color: #dc2626;">Attempt Details:</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 5px; font-weight: bold;">Email Attempted:</td>
                            <td style="padding: 5px;">{attempted_email}</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px; font-weight: bold;">Time:</td>
                            <td style="padding: 5px;">{timestamp.strftime('%Y-%m-%d %H:%M:%S')}</td>
                        </tr>
                        {f'<tr><td style="padding: 5px; font-weight: bold;">IP Address:</td><td style="padding: 5px;">{ip_address}</td></tr>' if ip_address else ''}
                    </table>
                </div>

                <div style="background-color: #fef3c7; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3 style="margin-top: 0; color: #d97706;">⚠️ What This Means:</h3>
                    <p>Someone attempted to access your account using the email address <strong>{attempted_email}</strong> with an incorrect password.</p>
                </div>

                <div style="background-color: #dbeafe; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3 style="margin-top: 0; color: #1e40af;">🛡️ Recommended Actions:</h3>
                    <ul>
                        <li>If this was you, please verify your password</li>
                        <li>If this wasn't you, your account credentials may be compromised</li>
                        <li>Consider changing your password immediately</li>
                        <li>Review your account activity</li>
                        <li>Enable two-factor authentication if available</li>
                    </ul>
                </div>

                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
                    <p style="font-size: 12px; color: #6b7280;">
                        This is an automated security notification from Bloomberg Analytics Hub.<br>
                        If you have questions, please contact your system administrator.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

        return self._send_email(self.admin_email, subject, body, is_html=True)

    def send_new_user_attempt_alert(self, attempted_email, ip_address=None, timestamp=None):
        """
        Send email alert when someone tries to login with non-existent email

        Args:
            attempted_email (str): Email address that doesn't exist in system
            ip_address (str): IP address of the attempt
            timestamp (datetime): Time of the attempt

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        if not timestamp:
            timestamp = datetime.now()

        subject = f"🔔 Login Attempt with Unregistered Email: {attempted_email}"

        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 2px solid #f59e0b; border-radius: 10px;">
                <h2 style="color: #f59e0b;">🔔 Unregistered User Login Attempt</h2>

                <p>Someone attempted to login to Bloomberg Analytics Hub using an email address that is not registered in the system.</p>

                <div style="background-color: #fef3c7; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3 style="margin-top: 0; color: #d97706;">Attempt Details:</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 5px; font-weight: bold;">Email Attempted:</td>
                            <td style="padding: 5px;">{attempted_email}</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px; font-weight: bold;">Time:</td>
                            <td style="padding: 5px;">{timestamp.strftime('%Y-%m-%d %H:%M:%S')}</td>
                        </tr>
                        {f'<tr><td style="padding: 5px; font-weight: bold;">IP Address:</td><td style="padding: 5px;">{ip_address}</td></tr>' if ip_address else ''}
                        <tr>
                            <td style="padding: 5px; font-weight: bold;">Status:</td>
                            <td style="padding: 5px; color: #dc2626; font-weight: bold;">EMAIL NOT REGISTERED</td>
                        </tr>
                    </table>
                </div>

                <div style="background-color: #e0e7ff; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3 style="margin-top: 0; color: #4338ca;">💡 What This Means:</h3>
                    <p>This could indicate:</p>
                    <ul>
                        <li>A legitimate user trying to access with wrong email</li>
                        <li>Someone exploring the system</li>
                        <li>Potential unauthorized access attempt</li>
                        <li>A user who needs to be registered</li>
                    </ul>
                </div>

                <div style="background-color: #dbeafe; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3 style="margin-top: 0; color: #1e40af;">📋 Recommended Actions:</h3>
                    <ul>
                        <li>Verify if this is a legitimate user who needs access</li>
                        <li>Contact the person at <strong>{attempted_email}</strong> if appropriate</li>
                        <li>Create an account using the admin tool if this is a valid user</li>
                        <li>Monitor for repeated attempts</li>
                        <li>Review security logs</li>
                    </ul>
                </div>

                <div style="background-color: #f3f4f6; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3 style="margin-top: 0;">🔧 To Create This User:</h3>
                    <p>Run the admin tool:</p>
                    <pre style="background-color: #1f2937; color: #10b981; padding: 10px; border-radius: 5px; overflow-x: auto;">python3 admin_user_manager.py</pre>
                    <p>Then select option 1 to create a new user with email: <strong>{attempted_email}</strong></p>
                </div>

                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
                    <p style="font-size: 12px; color: #6b7280;">
                        This is an automated security notification from Bloomberg Analytics Hub.<br>
                        System Administrator: {self.admin_email}
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

        return self._send_email(self.admin_email, subject, body, is_html=True)

    def _send_email(self, to_email, subject, body, is_html=False):
        """
        Internal method to send email via SMTP

        Args:
            to_email (str): Recipient email address
            subject (str): Email subject
            body (str): Email body
            is_html (bool): Whether body is HTML

        Returns:
            bool: True if sent successfully, False otherwise
        """
        if not self.is_configured:
            self.logger.warning(f"Email not configured. Would send: {subject} to {to_email}")
            self.logger.info(f"Email content: {body[:200]}...")
            return False

        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.sender_email
            msg['To'] = to_email
            msg['Subject'] = subject

            # Attach body
            if is_html:
                msg.attach(MIMEText(body, 'html'))
            else:
                msg.attach(MIMEText(body, 'plain'))

            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)

            self.logger.info(f"Email sent successfully to {to_email}: {subject}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to send email: {str(e)}")
            return False

    def test_email_configuration(self):
        """
        Test email configuration by sending a test message

        Returns:
            bool: True if test successful, False otherwise
        """
        if not self.is_configured:
            self.logger.error("Email service not configured")
            return False

        subject = "Test Email - Bloomberg Analytics Hub"
        body = """
        <html>
        <body>
            <h2>Email Configuration Test</h2>
            <p>This is a test email from Bloomberg Analytics Hub.</p>
            <p>If you received this, your email configuration is working correctly!</p>
        </body>
        </html>
        """

        return self._send_email(self.admin_email, subject, body, is_html=True)
