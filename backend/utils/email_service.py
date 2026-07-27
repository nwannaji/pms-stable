"""
Email service using SMTP (Galaxy Backbone relay / Office365 / GovMail)
Handles all email notifications for the PMS
"""

import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional

logger = logging.getLogger(__name__)

# SMTP configuration from environment
SMTP_HOST = os.getenv("SMTP_HOST", "mail.govmail.gbb.com.ng")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", SMTP_USERNAME)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

class EmailService:
    """Email service for sending notifications"""

    @staticmethod
    def send_email(
        to: List[str],
        subject: str,
        html: str,
        reply_to: Optional[str] = None
    ):
        """Send email via SMTP — tries STARTTLS first (best for submission ports),
           then falls back to SMTP_SSL, then plain SMTP.
           Tries the configured port first, then standard fallbacks.
        """
        import ssl

        logger.info(f"[EMAIL] Sending to {to} via {SMTP_HOST}:{SMTP_PORT} (user={SMTP_USERNAME})")

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = FROM_EMAIL
        msg["To"] = ", ".join(to)
        if reply_to:
            msg["Reply-To"] = reply_to
        msg.attach(MIMEText(html, "html"))

        # Permissive SSL context — internal relays often use self-signed certs
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        last_error = None

        def try_starttls(port):
            with smtplib.SMTP(SMTP_HOST, port, timeout=30) as server:
                server.ehlo()
                server.starttls(context=ctx)
                server.ehlo()
                if SMTP_USERNAME:
                    server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.sendmail(FROM_EMAIL, to, msg.as_string())

        def try_ssl(port):
            with smtplib.SMTP_SSL(SMTP_HOST, port, context=ctx, timeout=30) as server:
                if SMTP_USERNAME:
                    server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.sendmail(FROM_EMAIL, to, msg.as_string())

        def try_plain(port):
            with smtplib.SMTP(SMTP_HOST, port, timeout=30) as server:
                server.ehlo()
                if SMTP_USERNAME:
                    server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.sendmail(FROM_EMAIL, to, msg.as_string())

        # Connection strategy: try STARTTLS first (most submission ports use this),
        # then SMTP_SSL, then plain. Try configured port first, then standard fallbacks.
        # (465=SSL, 587=STARTTLS, 25=plain relay, 1707=Galaxy Backbone submission)
        attempts = [
            (SMTP_PORT, "STARTTLS",   try_starttls),
            (SMTP_PORT, "SMTP_SSL",  try_ssl),
            (SMTP_PORT, "plain",      try_plain),
            (587,       "STARTTLS",   try_starttls),
            (465,       "SMTP_SSL",   try_ssl),
            (25,        "plain",      try_plain),
        ]

        # Deduplicate while preserving order
        seen = set()
        unique_attempts = []
        for port, method, fn in attempts:
            key = (port, method)
            if key not in seen:
                seen.add(key)
                unique_attempts.append((port, method, fn))

        for port, method, fn in unique_attempts:
            try:
                logger.info(f"[EMAIL] Trying {method} on port {port}...")
                fn(port)
                logger.info(f"[EMAIL] Sent OK via {method}:{port} to {to}")
                return {"success": True, "to": to}
            except Exception as e:
                last_error = e
                logger.warning(f"[EMAIL] {method}:{port} failed: {e}")

        logger.error(f"[EMAIL] All attempts failed — Host={SMTP_HOST} LastError={last_error}")
        raise last_error

    @staticmethod
    def send_onboarding_email(user_email: str, user_name: str, onboarding_token: str):
        """Send onboarding email with password setup link"""
        onboarding_link = f"{FRONTEND_URL}/onboard?token={onboarding_token}"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.6;
                    color: #37352f;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 40px 20px;
                    background-color: #ffffff;
                }}
                .container {{
                    background: #ffffff;
                    border: 1px solid #e9e9e7;
                    border-radius: 8px;
                    overflow: hidden;
                }}
                .header {{
                    padding: 40px 40px 32px;
                    border-bottom: 1px solid #e9e9e7;
                }}
                .header h1 {{
                    color: #37352f;
                    margin: 0;
                    font-size: 20px;
                    font-weight: 600;
                    letter-spacing: -0.01em;
                }}
                .content {{
                    padding: 32px 40px;
                }}
                .content p {{
                    margin: 0 0 16px;
                    color: #37352f;
                    font-size: 14px;
                    line-height: 1.6;
                }}
                .button {{
                    display: inline-block;
                    padding: 10px 20px;
                    background: #37352f;
                    color: white;
                    text-decoration: none;
                    border-radius: 6px;
                    margin: 16px 0;
                    font-weight: 500;
                    font-size: 14px;
                    transition: background 0.2s;
                }}
                .button:hover {{
                    background: #2f2e2a;
                }}
                .link-box {{
                    background: #f7f6f3;
                    padding: 16px;
                    border-radius: 6px;
                    margin: 16px 0;
                    word-break: break-all;
                    font-size: 13px;
                    color: #787774;
                }}
                .footer {{
                    padding: 32px 40px;
                    background: #f7f6f3;
                    text-align: center;
                    color: #787774;
                    font-size: 13px;
                    line-height: 1.5;
                }}
                .footer p {{
                    margin: 8px 0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Welcome to Nigcomsat PMS</h1>
                </div>
                <div class="content">
                    <p>Hello {user_name},</p>
                    <p>Your account has been created in the Nigcomsat Performance Management System. To complete your registration and set up your password, please click the button below:</p>
                    <center>
                        <a href="{onboarding_link}" class="button">Set Up Your Password</a>
                    </center>
                    <p>Or copy and paste this link in your browser:</p>
                    <div class="link-box">{onboarding_link}</div>
                    <p><strong>Important:</strong> This link is valid for one-time use only. Once you set your password, you'll be able to log in to your account.</p>
                    <p>If you didn't expect this email, please contact your system administrator.</p>
                </div>
                <div class="footer">
                    <p>This is an automated message from Nigcomsat Performance Management System</p>
                    <p>&copy; 2024 Nigcomsat. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return EmailService.send_email(
            to=[user_email],
            subject="Welcome to Nigcomsat PMS - Set Up Your Password",
            html=html
        )

    @staticmethod
    def send_password_reset_email(user_email: str, user_name: str, reset_token: str):
        """Send password reset email"""
        reset_link = f"{FRONTEND_URL}/reset-password?token={reset_token}"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.6;
                    color: #37352f;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 40px 20px;
                    background-color: #ffffff;
                }}
                .container {{
                    background: #ffffff;
                    border: 1px solid #e9e9e7;
                    border-radius: 8px;
                    overflow: hidden;
                }}
                .header {{
                    padding: 40px 40px 32px;
                    border-bottom: 1px solid #e9e9e7;
                }}
                .header h1 {{
                    color: #37352f;
                    margin: 0;
                    font-size: 20px;
                    font-weight: 600;
                    letter-spacing: -0.01em;
                }}
                .content {{
                    padding: 32px 40px;
                }}
                .content p {{
                    margin: 0 0 16px;
                    color: #37352f;
                    font-size: 14px;
                    line-height: 1.6;
                }}
                .button {{
                    display: inline-block;
                    padding: 10px 20px;
                    background: #37352f;
                    color: white;
                    text-decoration: none;
                    border-radius: 6px;
                    margin: 16px 0;
                    font-weight: 500;
                    font-size: 14px;
                    transition: background 0.2s;
                }}
                .button:hover {{
                    background: #2f2e2a;
                }}
                .link-box {{
                    background: #f7f6f3;
                    padding: 16px;
                    border-radius: 6px;
                    margin: 16px 0;
                    word-break: break-all;
                    font-size: 13px;
                    color: #787774;
                }}
                .notice-box {{
                    background: #f7f6f3;
                    border-left: 3px solid #37352f;
                    padding: 16px;
                    margin: 16px 0;
                    border-radius: 4px;
                }}
                .notice-box ul {{
                    margin: 8px 0;
                    padding-left: 20px;
                }}
                .footer {{
                    padding: 32px 40px;
                    background: #f7f6f3;
                    text-align: center;
                    color: #787774;
                    font-size: 13px;
                    line-height: 1.5;
                }}
                .footer p {{
                    margin: 8px 0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Password Reset Request</h1>
                </div>
                <div class="content">
                    <p>Hello {user_name},</p>
                    <p>We received a request to reset your password for your Nigcomsat PMS account. Click the button below to reset your password:</p>
                    <center>
                        <a href="{reset_link}" class="button">Reset Your Password</a>
                    </center>
                    <p>Or copy and paste this link in your browser:</p>
                    <div class="link-box">{reset_link}</div>
                    <div class="notice-box">
                        <strong>Security Notice:</strong>
                        <ul style="margin: 10px 0;">
                            <li>This link is valid for one-time use only</li>
                            <li>If you didn't request this reset, please ignore this email</li>
                            <li>Your password will remain unchanged unless you use this link</li>
                        </ul>
                    </div>
                    <p>If you have any concerns, please contact your system administrator immediately.</p>
                </div>
                <div class="footer">
                    <p>This is an automated message from Nigcomsat Performance Management System</p>
                    <p>&copy; 2024 Nigcomsat. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return EmailService.send_email(
            to=[user_email],
            subject="Reset Your Nigcomsat PMS Password",
            html=html
        )

    @staticmethod
    def send_initiative_approved_email(
        assignee_email: str,
        assignee_name: str,
        approver_name: str,
        initiative_title: str,
        initiative_id: str,
        due_date: str
    ):
        """Send initiative approval notification to assignee"""
        initiative_link = f"{FRONTEND_URL}/dashboard/initiatives?id={initiative_id}"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.6;
                    color: #37352f;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 40px 20px;
                    background-color: #ffffff;
                }}
                .container {{
                    background: #ffffff;
                    border: 1px solid #e9e9e7;
                    border-radius: 8px;
                    overflow: hidden;
                }}
                .header {{
                    padding: 40px 40px 32px;
                    border-bottom: 1px solid #e9e9e7;
                }}
                .header h1 {{
                    color: #37352f;
                    margin: 0;
                    font-size: 20px;
                    font-weight: 600;
                    letter-spacing: -0.01em;
                }}
                .content {{
                    padding: 32px 40px;
                }}
                .content p {{
                    margin: 0 0 16px;
                    color: #37352f;
                    font-size: 14px;
                    line-height: 1.6;
                }}
                .success-box {{
                    background: #f7f6f3;
                    padding: 20px;
                    border-radius: 6px;
                    margin: 20px 0;
                    border-left: 3px solid #4caf50;
                }}
                .success-box p {{
                    margin: 8px 0;
                    font-size: 14px;
                    color: #37352f;
                }}
                .button {{
                    display: inline-block;
                    padding: 10px 20px;
                    background: #37352f;
                    color: white;
                    text-decoration: none;
                    border-radius: 6px;
                    margin: 16px 0;
                    font-weight: 500;
                    font-size: 14px;
                    transition: background 0.2s;
                }}
                .button:hover {{
                    background: #2f2e2a;
                }}
                .footer {{
                    padding: 32px 40px;
                    background: #f7f6f3;
                    text-align: center;
                    color: #787774;
                    font-size: 13px;
                    line-height: 1.5;
                }}
                .footer p {{
                    margin: 8px 0;
                }}
                .link-box {{
                    background: #f7f6f3;
                    padding: 16px;
                    border-radius: 6px;
                    margin: 16px 0;
                    word-break: break-all;
                    font-size: 13px;
                    color: #787774;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Initiative Approved</h1>
                </div>
                <div class="content">
                    <p>Hello {assignee_name},</p>
                    <p>Great news! <strong>{approver_name}</strong> has approved your initiative.</p>
                    <div class="success-box">
                        <p><strong>Initiative:</strong> {initiative_title}</p>
                        <p><strong>Approved by:</strong> {approver_name}</p>
                        <p><strong>Due Date:</strong> {due_date}</p>
                        <p><strong>Status:</strong> APPROVED</p>
                    </div>
                    <p>You can now start working on this initiative. Please ensure timely completion.</p>
                    <center>
                        <a href="{initiative_link}" class="button">View Initiative</a>
                    </center>
                    <p>Or copy and paste this link in your browser:</p>
                    <div class="link-box">{initiative_link}</div>
                </div>
                <div class="footer">
                    <p>This is an automated notification from Nigcomsat Performance Management System</p>
                    <p>&copy; 2024 Nigcomsat. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return EmailService.send_email(
            to=[assignee_email],
            subject=f"Initiative Approved: {initiative_title}",
            html=html
        )

    @staticmethod
    def send_initiative_rejected_email(
        creator_email: str,
        creator_name: str,
        supervisor_name: str,
        initiative_title: str,
        initiative_id: str,
        rejection_reason: str
    ):
        """Send initiative rejection notification to creator"""
        initiative_link = f"{FRONTEND_URL}/dashboard/initiatives?id={initiative_id}"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.6;
                    color: #37352f;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 40px 20px;
                    background-color: #ffffff;
                }}
                .container {{
                    background: #ffffff;
                    border: 1px solid #e9e9e7;
                    border-radius: 8px;
                    overflow: hidden;
                }}
                .header {{
                    padding: 40px 40px 32px;
                    border-bottom: 1px solid #e9e9e7;
                }}
                .header h1 {{
                    color: #37352f;
                    margin: 0;
                    font-size: 20px;
                    font-weight: 600;
                    letter-spacing: -0.01em;
                }}
                .content {{
                    padding: 32px 40px;
                }}
                .content p {{
                    margin: 0 0 16px;
                    color: #37352f;
                    font-size: 14px;
                    line-height: 1.6;
                }}
                .error-box {{
                    background: #f7f6f3;
                    padding: 20px;
                    border-radius: 6px;
                    margin: 20px 0;
                    border-left: 3px solid #e53935;
                }}
                .error-box p {{
                    margin: 8px 0;
                    font-size: 14px;
                    color: #37352f;
                }}
                .button {{
                    display: inline-block;
                    padding: 10px 20px;
                    background: #37352f;
                    color: white;
                    text-decoration: none;
                    border-radius: 6px;
                    margin: 16px 0;
                    font-weight: 500;
                    font-size: 14px;
                    transition: background 0.2s;
                }}
                .button:hover {{
                    background: #2f2e2a;
                }}
                .footer {{
                    padding: 32px 40px;
                    background: #f7f6f3;
                    text-align: center;
                    color: #787774;
                    font-size: 13px;
                    line-height: 1.5;
                }}
                .footer p {{
                    margin: 8px 0;
                }}
                .link-box {{
                    background: #f7f6f3;
                    padding: 16px;
                    border-radius: 6px;
                    margin: 16px 0;
                    word-break: break-all;
                    font-size: 13px;
                    color: #787774;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Initiative Not Approved</h1>
                </div>
                <div class="content">
                    <p>Hello {creator_name},</p>
                    <p>Your supervisor <strong>{supervisor_name}</strong> has not approved your initiative.</p>
                    <div class="error-box">
                        <p><strong>Initiative:</strong> {initiative_title}</p>
                        <p><strong>Reviewed by:</strong> {supervisor_name}</p>
                        <p><strong>Reason:</strong> {rejection_reason}</p>
                    </div>
                    <p>Please review the feedback and make necessary adjustments. You can edit and resubmit your initiative for approval.</p>
                    <center>
                        <a href="{initiative_link}" class="button">View Initiative</a>
                    </center>
                    <p>Or copy and paste this link in your browser:</p>
                    <div class="link-box">{initiative_link}</div>
                </div>
                <div class="footer">
                    <p>This is an automated notification from Nigcomsat Performance Management System</p>
                    <p>&copy; 2024 Nigcomsat. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return EmailService.send_email(
            to=[creator_email],
            subject=f"Initiative Not Approved: {initiative_title}",
            html=html
        )

    @staticmethod
    def send_initiative_assignment_email(
        user_email: str,
        user_name: str,
        initiative_title: str,
        initiative_id: str,
        due_date: str,
        created_by_name: str
    ):
        """Send initiative assignment notification"""
        initiative_link = f"{FRONTEND_URL}/dashboard/initiatives?id={initiative_id}"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.6;
                    color: #37352f;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 40px 20px;
                    background-color: #ffffff;
                }}
                .container {{
                    background: #ffffff;
                    border: 1px solid #e9e9e7;
                    border-radius: 8px;
                    overflow: hidden;
                }}
                .header {{
                    padding: 40px 40px 32px;
                    border-bottom: 1px solid #e9e9e7;
                }}
                .header h1 {{
                    color: #37352f;
                    margin: 0;
                    font-size: 20px;
                    font-weight: 600;
                    letter-spacing: -0.01em;
                }}
                .content {{
                    padding: 32px 40px;
                }}
                .content p {{
                    margin: 0 0 16px;
                    color: #37352f;
                    font-size: 14px;
                    line-height: 1.6;
                }}
                .task-card {{
                    background: #f7f6f3;
                    border-left: 3px solid #37352f;
                    padding: 20px;
                    margin: 20px 0;
                    border-radius: 4px;
                }}
                .task-card h3 {{
                    margin: 0 0 12px;
                    color: #37352f;
                    font-size: 16px;
                    font-weight: 600;
                }}
                .task-card p {{
                    margin: 8px 0;
                    font-size: 14px;
                    color: #37352f;
                }}
                .button {{
                    display: inline-block;
                    padding: 10px 20px;
                    background: #37352f;
                    color: white;
                    text-decoration: none;
                    border-radius: 6px;
                    margin: 16px 0;
                    font-weight: 500;
                    font-size: 14px;
                    transition: background 0.2s;
                }}
                .button:hover {{
                    background: #2f2e2a;
                }}
                .footer {{
                    padding: 32px 40px;
                    background: #f7f6f3;
                    text-align: center;
                    color: #787774;
                    font-size: 13px;
                    line-height: 1.5;
                }}
                .link-box {{
                    background: #f7f6f3;
                    padding: 16px;
                    border-radius: 6px;
                    margin: 16px 0;
                    word-break: break-all;
                    font-size: 13px;
                    color: #787774;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>New Initiative Assigned</h1>
                </div>
                <div class="content">
                    <p>Hello {user_name},</p>
                    <p>You have been assigned a new initiative by <strong>{created_by_name}</strong>.</p>
                    <div class="task-card">
                        <h3>{initiative_title}</h3>
                        <p><strong>Due Date:</strong> {due_date}</p>
                        <p><strong>Assigned by:</strong> {created_by_name}</p>
                    </div>
                    <center>
                        <a href="{initiative_link}" class="button">View Initiative</a>
                    </center>
                    <p>Or copy and paste this link in your browser:</p>
                    <div class="link-box">{initiative_link}</div>
                </div>
                <div class="footer">
                    <p>This is an automated notification from Nigcomsat Performance Management System</p>
                    <p>&copy; 2024 Nigcomsat. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return EmailService.send_email(
            to=[user_email],
            subject=f"New Initiative Assigned: {initiative_title}",
            html=html
        )

    @staticmethod
    def send_task_assignment_email(user_email: str, user_name: str, task_title: str, task_id: str, due_date: str, created_by_name: str):
        """Send task assignment notification"""
        task_link = f"{FRONTEND_URL}/dashboard/tasks"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.6;
                    color: #37352f;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 40px 20px;
                    background-color: #ffffff;
                }}
                .container {{
                    background: #ffffff;
                    border: 1px solid #e9e9e7;
                    border-radius: 8px;
                    overflow: hidden;
                }}
                .header {{
                    padding: 40px 40px 32px;
                    border-bottom: 1px solid #e9e9e7;
                }}
                .header h1 {{
                    color: #37352f;
                    margin: 0;
                    font-size: 20px;
                    font-weight: 600;
                    letter-spacing: -0.01em;
                }}
                .content {{
                    padding: 32px 40px;
                }}
                .content p {{
                    margin: 0 0 16px;
                    color: #37352f;
                    font-size: 14px;
                    line-height: 1.6;
                }}
                .task-card {{
                    background: #f7f6f3;
                    border-left: 3px solid #37352f;
                    padding: 20px;
                    margin: 20px 0;
                    border-radius: 4px;
                }}
                .task-card h3 {{
                    margin: 0 0 12px;
                    color: #37352f;
                    font-size: 16px;
                    font-weight: 600;
                }}
                .task-card p {{
                    margin: 8px 0;
                    font-size: 14px;
                    color: #37352f;
                }}
                .button {{
                    display: inline-block;
                    padding: 10px 20px;
                    background: #37352f;
                    color: white;
                    text-decoration: none;
                    border-radius: 6px;
                    margin: 16px 0;
                    font-weight: 500;
                    font-size: 14px;
                    transition: background 0.2s;
                }}
                .button:hover {{
                    background: #2f2e2a;
                }}
                .footer {{
                    padding: 32px 40px;
                    background: #f7f6f3;
                    text-align: center;
                    color: #787774;
                    font-size: 13px;
                    line-height: 1.5;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>New Task Assigned</h1>
                </div>
                <div class="content">
                    <p>Hello {user_name},</p>
                    <p>You have been assigned a new task by {created_by_name}.</p>
                    <div class="task-card">
                        <h3>{task_title}</h3>
                        <p><strong>Due Date:</strong> {due_date}</p>
                        <p><strong>Assigned by:</strong> {created_by_name}</p>
                    </div>
                    <center>
                        <a href="{task_link}" class="button">View Task Details</a>
                    </center>
                    <p>Please review the task details and ensure timely completion.</p>
                </div>
                <div class="footer">
                    <p>This is an automated notification from Nigcomsat Performance Management System</p>
                </div>
            </div>
        </body>
        </html>
        """

        return EmailService.send_email(
            to=[user_email],
            subject=f"New Task Assigned: {task_title}",
            html=html
        )

    @staticmethod
    def send_task_submitted_email(creator_email: str, creator_name: str, task_title: str, submitted_by_name: str):
        """Send task submission notification to creator"""
        task_link = f"{FRONTEND_URL}/dashboard/tasks"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.6;
                    color: #37352f;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 40px 20px;
                    background-color: #ffffff;
                }}
                .container {{
                    background: #ffffff;
                    border: 1px solid #e9e9e7;
                    border-radius: 8px;
                    overflow: hidden;
                }}
                .header {{
                    padding: 40px 40px 32px;
                    border-bottom: 1px solid #e9e9e7;
                }}
                .header h1 {{
                    color: #37352f;
                    margin: 0;
                    font-size: 20px;
                    font-weight: 600;
                    letter-spacing: -0.01em;
                }}
                .content {{
                    padding: 32px 40px;
                }}
                .content p {{
                    margin: 0 0 16px;
                    color: #37352f;
                    font-size: 14px;
                    line-height: 1.6;
                }}
                .button {{
                    display: inline-block;
                    padding: 10px 20px;
                    background: #37352f;
                    color: white;
                    text-decoration: none;
                    border-radius: 6px;
                    margin: 16px 0;
                    font-weight: 500;
                    font-size: 14px;
                    transition: background 0.2s;
                }}
                .button:hover {{
                    background: #2f2e2a;
                }}
                .footer {{
                    padding: 32px 40px;
                    background: #f7f6f3;
                    text-align: center;
                    color: #787774;
                    font-size: 13px;
                    line-height: 1.5;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Task Submitted for Review</h1>
                </div>
                <div class="content">
                    <p>Hello {creator_name},</p>
                    <p><strong>{submitted_by_name}</strong> has submitted the task <strong>"{task_title}"</strong> for your review.</p>
                    <center>
                        <a href="{task_link}" class="button">Review Task</a>
                    </center>
                    <p>Please review the submission and provide feedback.</p>
                </div>
                <div class="footer">
                    <p>This is an automated notification from Nigcomsat Performance Management System</p>
                </div>
            </div>
        </body>
        </html>
        """

        return EmailService.send_email(
            to=[creator_email],
            subject=f"Task Submitted: {task_title}",
            html=html
        )

    @staticmethod
    def send_task_reviewed_email(assignee_email: str, assignee_name: str, task_title: str, score: int, feedback: str, approved: bool):
        """Send task review notification to assignee"""
        task_link = f"{FRONTEND_URL}/dashboard/tasks"
        status = "Approved" if approved else "Needs Revision"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.6;
                    color: #37352f;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 40px 20px;
                    background-color: #ffffff;
                }}
                .container {{
                    background: #ffffff;
                    border: 1px solid #e9e9e7;
                    border-radius: 8px;
                    overflow: hidden;
                }}
                .header {{
                    padding: 40px 40px 32px;
                    border-bottom: 1px solid #e9e9e7;
                }}
                .header h1 {{
                    color: #37352f;
                    margin: 0;
                    font-size: 20px;
                    font-weight: 600;
                    letter-spacing: -0.01em;
                }}
                .content {{
                    padding: 32px 40px;
                }}
                .content p {{
                    margin: 0 0 16px;
                    color: #37352f;
                    font-size: 14px;
                    line-height: 1.6;
                }}
                .score-box {{
                    background: #f7f6f3;
                    border-left: 3px solid #37352f;
                    padding: 20px;
                    margin: 20px 0;
                    border-radius: 4px;
                }}
                .score-box p {{
                    margin: 8px 0;
                    font-size: 14px;
                    color: #37352f;
                }}
                .button {{
                    display: inline-block;
                    padding: 10px 20px;
                    background: #37352f;
                    color: white;
                    text-decoration: none;
                    border-radius: 6px;
                    margin: 16px 0;
                    font-weight: 500;
                    font-size: 14px;
                    transition: background 0.2s;
                }}
                .button:hover {{
                    background: #2f2e2a;
                }}
                .footer {{
                    padding: 32px 40px;
                    background: #f7f6f3;
                    text-align: center;
                    color: #787774;
                    font-size: 13px;
                    line-height: 1.5;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Task Reviewed: {status}</h1>
                </div>
                <div class="content">
                    <p>Hello {assignee_name},</p>
                    <p>Your task <strong>"{task_title}"</strong> has been reviewed.</p>
                    <div class="score-box">
                        <p><strong>Status:</strong> {status}</p>
                        <p><strong>Score:</strong> {score}/10</p>
                        {f'<p><strong>Feedback:</strong> {feedback}</p>' if feedback else ''}
                    </div>
                    <center>
                        <a href="{task_link}" class="button">View Task Details</a>
                    </center>
                </div>
                <div class="footer">
                    <p>This is an automated notification from Nigcomsat Performance Management System</p>
                </div>
            </div>
        </body>
        </html>
        """

        return EmailService.send_email(
            to=[assignee_email],
            subject=f"Task Reviewed: {task_title} - {status}",
            html=html
        )

    # ============================================
    # INITIATIVE EMAIL TEMPLATES (8 CRITICAL)
    # ============================================

    @staticmethod
    def send_initiative_approval_request_email(
        supervisor_email: str,
        supervisor_name: str,
        creator_name: str,
        initiative_title: str,
        initiative_id: str,
        due_date: str
    ):
        """Send initiative approval request to supervisor"""
        initiative_link = f"{FRONTEND_URL}/dashboard/initiatives?id={initiative_id}"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.6;
                    color: #37352f;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 40px 20px;
                    background-color: #ffffff;
                }}
                .container {{
                    background: #ffffff;
                    border: 1px solid #e9e9e7;
                    border-radius: 8px;
                    overflow: hidden;
                }}
                .header {{
                    padding: 40px 40px 32px;
                    border-bottom: 1px solid #e9e9e7;
                }}
                .header h1 {{
                    color: #37352f;
                    margin: 0;
                    font-size: 20px;
                    font-weight: 600;
                    letter-spacing: -0.01em;
                }}
                .content {{
                    padding: 32px 40px;
                }}
                .content p {{
                    margin: 0 0 16px;
                    color: #37352f;
                    font-size: 14px;
                    line-height: 1.6;
                }}
                .details-box {{
                    background: #f7f6f3;
                    padding: 20px;
                    border-radius: 6px;
                    margin: 20px 0;
                    border-left: 3px solid #37352f;
                }}
                .details-box p {{
                    margin: 8px 0;
                    font-size: 14px;
                    color: #37352f;
                }}
                .button {{
                    display: inline-block;
                    padding: 10px 20px;
                    background: #37352f;
                    color: white;
                    text-decoration: none;
                    border-radius: 6px;
                    margin: 16px 0;
                    font-weight: 500;
                    font-size: 14px;
                    transition: background 0.2s;
                }}
                .button:hover {{
                    background: #2f2e2a;
                }}
                .footer {{
                    padding: 32px 40px;
                    background: #f7f6f3;
                    text-align: center;
                    color: #787774;
                    font-size: 13px;
                    line-height: 1.5;
                }}
                .footer p {{
                    margin: 8px 0;
                }}
                .link-box {{
                    background: #f7f6f3;
                    padding: 16px;
                    border-radius: 6px;
                    margin: 16px 0;
                    word-break: break-all;
                    font-size: 13px;
                    color: #787774;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Initiative Approval Required</h1>
                </div>
                <div class="content">
                    <p>Hello {supervisor_name},</p>
                    <p><strong>{creator_name}</strong> has created a new initiative that requires your approval:</p>
                    <div class="details-box">
                        <p><strong>Initiative:</strong> {initiative_title}</p>
                        <p><strong>Created by:</strong> {creator_name}</p>
                        <p><strong>Due Date:</strong> {due_date}</p>
                    </div>
                    <p>Please review and approve or reject this initiative at your earliest convenience.</p>
                    <center>
                        <a href="{initiative_link}" class="button">Review Initiative</a>
                    </center>
                    <p>Or copy and paste this link in your browser:</p>
                    <div class="link-box">{initiative_link}</div>
                </div>
                <div class="footer">
                    <p>This is an automated notification from Nigcomsat Performance Management System</p>
                    <p>&copy; 2024 Nigcomsat. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return EmailService.send_email(
            to=[supervisor_email],
            subject=f"Initiative Approval Required: {initiative_title}",
            html=html
        )

    @staticmethod
    def send_initiative_overdue_email(
        user_email: str,
        user_name: str,
        initiative_title: str,
        initiative_id: str,
        due_date: str,
        is_supervisor: bool = False
    ):
        """Send initiative overdue notification"""
        initiative_link = f"{FRONTEND_URL}/dashboard/initiatives?id={initiative_id}"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.6;
                    color: #37352f;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 40px 20px;
                    background-color: #ffffff;
                }}
                .container {{
                    background: #ffffff;
                    border: 1px solid #e9e9e7;
                    border-radius: 8px;
                    overflow: hidden;
                }}
                .header {{
                    padding: 40px 40px 32px;
                    border-bottom: 1px solid #e9e9e7;
                }}
                .header h1 {{
                    color: #37352f;
                    margin: 0;
                    font-size: 20px;
                    font-weight: 600;
                    letter-spacing: -0.01em;
                }}
                .content {{
                    padding: 32px 40px;
                }}
                .content p {{
                    margin: 0 0 16px;
                    color: #37352f;
                    font-size: 14px;
                    line-height: 1.6;
                }}
                .warning-box {{
                    background: #f7f6f3;
                    padding: 20px;
                    border-radius: 6px;
                    margin: 20px 0;
                    border-left: 3px solid #37352f;
                }}
                .warning-box p {{
                    margin: 8px 0;
                    font-size: 14px;
                    color: #37352f;
                }}
                .button {{
                    display: inline-block;
                    padding: 10px 20px;
                    background: #37352f;
                    color: white;
                    text-decoration: none;
                    border-radius: 6px;
                    margin: 16px 0;
                    font-weight: 500;
                    font-size: 14px;
                    transition: background 0.2s;
                }}
                .button:hover {{
                    background: #2f2e2a;
                }}
                .footer {{
                    padding: 32px 40px;
                    background: #f7f6f3;
                    text-align: center;
                    color: #787774;
                    font-size: 13px;
                    line-height: 1.5;
                }}
                .footer p {{
                    margin: 8px 0;
                }}
                .link-box {{
                    background: #f7f6f3;
                    padding: 16px;
                    border-radius: 6px;
                    margin: 16px 0;
                    word-break: break-all;
                    font-size: 13px;
                    color: #787774;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Initiative Overdue</h1>
                </div>
                <div class="content">
                    <p>Hello {user_name},</p>
                    <p>The following initiative is now <strong>overdue</strong>:</p>
                    <div class="warning-box">
                        <p><strong>Initiative:</strong> {initiative_title}</p>
                        <p><strong>Original Due Date:</strong> {due_date}</p>
                        <p><strong>Status:</strong> OVERDUE</p>
                    </div>
                    <p>{"As a supervisor, please follow up with the assignee to address this overdue initiative." if is_supervisor else "Please submit this initiative or request an extension as soon as possible."}</p>
                    <center>
                        <a href="{initiative_link}" class="button">View Initiative</a>
                    </center>
                    <p>Or copy and paste this link in your browser:</p>
                    <div class="link-box">{initiative_link}</div>
                </div>
                <div class="footer">
                    <p>This is an automated notification from Nigcomsat Performance Management System</p>
                    <p>&copy; 2024 Nigcomsat. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return EmailService.send_email(
            to=[user_email],
            subject=f"Initiative Overdue: {initiative_title}",
            html=html
        )

    @staticmethod
    def send_extension_request_email(
        supervisor_email: str,
        supervisor_name: str,
        requester_name: str,
        initiative_title: str,
        initiative_id: str,
        new_due_date: str,
        reason: str
    ):
        """Send extension request notification to supervisor"""
        initiative_link = f"{FRONTEND_URL}/dashboard/initiatives?id={initiative_id}"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.6;
                    color: #37352f;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 40px 20px;
                    background-color: #ffffff;
                }}
                .container {{
                    background: #ffffff;
                    border: 1px solid #e9e9e7;
                    border-radius: 8px;
                    overflow: hidden;
                }}
                .header {{
                    padding: 40px 40px 32px;
                    border-bottom: 1px solid #e9e9e7;
                }}
                .header h1 {{
                    color: #37352f;
                    margin: 0;
                    font-size: 20px;
                    font-weight: 600;
                    letter-spacing: -0.01em;
                }}
                .content {{
                    padding: 32px 40px;
                }}
                .content p {{
                    margin: 0 0 16px;
                    color: #37352f;
                    font-size: 14px;
                    line-height: 1.6;
                }}
                .info-box {{
                    background: #f7f6f3;
                    padding: 20px;
                    border-radius: 6px;
                    margin: 20px 0;
                    border-left: 3px solid #37352f;
                }}
                .info-box p {{
                    margin: 8px 0;
                    font-size: 14px;
                    color: #37352f;
                }}
                .button {{
                    display: inline-block;
                    padding: 10px 20px;
                    background: #37352f;
                    color: white;
                    text-decoration: none;
                    border-radius: 6px;
                    margin: 16px 0;
                    font-weight: 500;
                    font-size: 14px;
                    transition: background 0.2s;
                }}
                .button:hover {{
                    background: #2f2e2a;
                }}
                .footer {{
                    padding: 32px 40px;
                    background: #f7f6f3;
                    text-align: center;
                    color: #787774;
                    font-size: 13px;
                    line-height: 1.5;
                }}
                .footer p {{
                    margin: 8px 0;
                }}
                .link-box {{
                    background: #f7f6f3;
                    padding: 16px;
                    border-radius: 6px;
                    margin: 16px 0;
                    word-break: break-all;
                    font-size: 13px;
                    color: #787774;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Extension Request</h1>
                </div>
                <div class="content">
                    <p>Hello {supervisor_name},</p>
                    <p><strong>{requester_name}</strong> has requested an extension for the following initiative:</p>
                    <div class="info-box">
                        <p><strong>Initiative:</strong> {initiative_title}</p>
                        <p><strong>Requested by:</strong> {requester_name}</p>
                        <p><strong>New Due Date:</strong> {new_due_date}</p>
                        <p><strong>Reason:</strong> {reason}</p>
                    </div>
                    <p>Please review and approve or deny this extension request.</p>
                    <center>
                        <a href="{initiative_link}" class="button">Review Request</a>
                    </center>
                    <p>Or copy and paste this link in your browser:</p>
                    <div class="link-box">{initiative_link}</div>
                </div>
                <div class="footer">
                    <p>This is an automated notification from Nigcomsat Performance Management System</p>
                    <p>&copy; 2024 Nigcomsat. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return EmailService.send_email(
            to=[supervisor_email],
            subject=f"Extension Request: {initiative_title}",
            html=html
        )

    @staticmethod
    def send_extension_approved_email(
        user_email: str,
        user_name: str,
        initiative_title: str,
        initiative_id: str,
        new_due_date: str
    ):
        """Send extension approved notification"""
        initiative_link = f"{FRONTEND_URL}/dashboard/initiatives?id={initiative_id}"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.6;
                    color: #37352f;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 40px 20px;
                    background-color: #ffffff;
                }}
                .container {{
                    background: #ffffff;
                    border: 1px solid #e9e9e7;
                    border-radius: 8px;
                    overflow: hidden;
                }}
                .header {{
                    padding: 40px 40px 32px;
                    border-bottom: 1px solid #e9e9e7;
                }}
                .header h1 {{
                    color: #37352f;
                    margin: 0;
                    font-size: 20px;
                    font-weight: 600;
                    letter-spacing: -0.01em;
                }}
                .content {{
                    padding: 32px 40px;
                }}
                .content p {{
                    margin: 0 0 16px;
                    color: #37352f;
                    font-size: 14px;
                    line-height: 1.6;
                }}
                .success-box {{
                    background: #f7f6f3;
                    padding: 20px;
                    border-radius: 6px;
                    margin: 20px 0;
                    border-left: 3px solid #37352f;
                }}
                .success-box p {{
                    margin: 8px 0;
                    font-size: 14px;
                    color: #37352f;
                }}
                .button {{
                    display: inline-block;
                    padding: 10px 20px;
                    background: #37352f;
                    color: white;
                    text-decoration: none;
                    border-radius: 6px;
                    margin: 16px 0;
                    font-weight: 500;
                    font-size: 14px;
                    transition: background 0.2s;
                }}
                .button:hover {{
                    background: #2f2e2a;
                }}
                .footer {{
                    padding: 32px 40px;
                    background: #f7f6f3;
                    text-align: center;
                    color: #787774;
                    font-size: 13px;
                    line-height: 1.5;
                }}
                .footer p {{
                    margin: 8px 0;
                }}
                .link-box {{
                    background: #f7f6f3;
                    padding: 16px;
                    border-radius: 6px;
                    margin: 16px 0;
                    word-break: break-all;
                    font-size: 13px;
                    color: #787774;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Extension Approved</h1>
                </div>
                <div class="content">
                    <p>Hello {user_name},</p>
                    <p>Good news! Your extension request has been <strong>approved</strong>.</p>
                    <div class="success-box">
                        <p><strong>Initiative:</strong> {initiative_title}</p>
                        <p><strong>New Due Date:</strong> {new_due_date}</p>
                    </div>
                    <p>You now have additional time to complete this initiative. Please ensure to submit it by the new deadline.</p>
                    <center>
                        <a href="{initiative_link}" class="button">View Initiative</a>
                    </center>
                    <p>Or copy and paste this link in your browser:</p>
                    <div class="link-box">{initiative_link}</div>
                </div>
                <div class="footer">
                    <p>This is an automated notification from Nigcomsat Performance Management System</p>
                    <p>&copy; 2024 Nigcomsat. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return EmailService.send_email(
            to=[user_email],
            subject=f"Extension Approved: {initiative_title}",
            html=html
        )

    @staticmethod
    def send_extension_denied_email(
        user_email: str,
        user_name: str,
        initiative_title: str,
        initiative_id: str,
        denial_reason: str
    ):
        """Send extension denied notification"""
        initiative_link = f"{FRONTEND_URL}/dashboard/initiatives?id={initiative_id}"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.6;
                    color: #37352f;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 40px 20px;
                    background-color: #ffffff;
                }}
                .container {{
                    background: #ffffff;
                    border: 1px solid #e9e9e7;
                    border-radius: 8px;
                    overflow: hidden;
                }}
                .header {{
                    padding: 40px 40px 32px;
                    border-bottom: 1px solid #e9e9e7;
                }}
                .header h1 {{
                    color: #37352f;
                    margin: 0;
                    font-size: 20px;
                    font-weight: 600;
                    letter-spacing: -0.01em;
                }}
                .content {{
                    padding: 32px 40px;
                }}
                .content p {{
                    margin: 0 0 16px;
                    color: #37352f;
                    font-size: 14px;
                    line-height: 1.6;
                }}
                .error-box {{
                    background: #f7f6f3;
                    padding: 20px;
                    border-radius: 6px;
                    margin: 20px 0;
                    border-left: 3px solid #37352f;
                }}
                .error-box p {{
                    margin: 8px 0;
                    font-size: 14px;
                    color: #37352f;
                }}
                .button {{
                    display: inline-block;
                    padding: 10px 20px;
                    background: #37352f;
                    color: white;
                    text-decoration: none;
                    border-radius: 6px;
                    margin: 16px 0;
                    font-weight: 500;
                    font-size: 14px;
                    transition: background 0.2s;
                }}
                .button:hover {{
                    background: #2f2e2a;
                }}
                .footer {{
                    padding: 32px 40px;
                    background: #f7f6f3;
                    text-align: center;
                    color: #787774;
                    font-size: 13px;
                    line-height: 1.5;
                }}
                .footer p {{
                    margin: 8px 0;
                }}
                .link-box {{
                    background: #f7f6f3;
                    padding: 16px;
                    border-radius: 6px;
                    margin: 16px 0;
                    word-break: break-all;
                    font-size: 13px;
                    color: #787774;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Extension Request Denied</h1>
                </div>
                <div class="content">
                    <p>Hello {user_name},</p>
                    <p>Your extension request has been <strong>denied</strong>.</p>
                    <div class="error-box">
                        <p><strong>Initiative:</strong> {initiative_title}</p>
                        <p><strong>Reason:</strong> {denial_reason}</p>
                    </div>
                    <p>Please complete and submit the initiative by the original deadline, or discuss with your supervisor for alternative arrangements.</p>
                    <center>
                        <a href="{initiative_link}" class="button">View Initiative</a>
                    </center>
                    <p>Or copy and paste this link in your browser:</p>
                    <div class="link-box">{initiative_link}</div>
                </div>
                <div class="footer">
                    <p>This is an automated notification from Nigcomsat Performance Management System</p>
                    <p>&copy; 2024 Nigcomsat. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return EmailService.send_email(
            to=[user_email],
            subject=f"Extension Request Denied: {initiative_title}",
            html=html
        )

    @staticmethod
    def send_goal_approval_request_email(
        supervisor_email: str,
        supervisor_name: str,
        creator_name: str,
        goal_title: str,
        goal_id: str,
        goal_type: str,
        quarter: str = None,
        year: int = None
    ):
        """Send goal approval request to supervisor"""
        goal_link = f"{FRONTEND_URL}/dashboard/goals?id={goal_id}"
        period = f"{quarter} {year}" if quarter and year else f"{year}" if year else "N/A"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.6;
                    color: #37352f;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 40px 20px;
                    background-color: #ffffff;
                }}
                .container {{
                    background: #ffffff;
                    border: 1px solid #e9e9e7;
                    border-radius: 8px;
                    overflow: hidden;
                }}
                .header {{
                    padding: 40px 40px 32px;
                    border-bottom: 1px solid #e9e9e7;
                }}
                .header h1 {{
                    color: #37352f;
                    margin: 0;
                    font-size: 20px;
                    font-weight: 600;
                    letter-spacing: -0.01em;
                }}
                .content {{
                    padding: 32px 40px;
                }}
                .content p {{
                    margin: 0 0 16px;
                    color: #37352f;
                    font-size: 14px;
                    line-height: 1.6;
                }}
                .details-box {{
                    background: #f7f6f3;
                    padding: 20px;
                    border-radius: 6px;
                    margin: 20px 0;
                    border-left: 3px solid #37352f;
                }}
                .details-box p {{
                    margin: 8px 0;
                    font-size: 14px;
                    color: #37352f;
                }}
                .button {{
                    display: inline-block;
                    padding: 10px 20px;
                    background: #37352f;
                    color: white;
                    text-decoration: none;
                    border-radius: 6px;
                    margin: 16px 0;
                    font-weight: 500;
                    font-size: 14px;
                    transition: background 0.2s;
                }}
                .button:hover {{
                    background: #2f2e2a;
                }}
                .footer {{
                    padding: 32px 40px;
                    background: #f7f6f3;
                    text-align: center;
                    color: #787774;
                    font-size: 13px;
                    line-height: 1.5;
                }}
                .footer p {{
                    margin: 8px 0;
                }}
                .link-box {{
                    background: #f7f6f3;
                    padding: 16px;
                    border-radius: 6px;
                    margin: 16px 0;
                    word-break: break-all;
                    font-size: 13px;
                    color: #787774;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Goal Approval Required</h1>
                </div>
                <div class="content">
                    <p>Hello {supervisor_name},</p>
                    <p><strong>{creator_name}</strong> has created a new goal that requires your approval:</p>
                    <div class="details-box">
                        <p><strong>Goal:</strong> {goal_title}</p>
                        <p><strong>Type:</strong> {goal_type}</p>
                        <p><strong>Period:</strong> {period}</p>
                        <p><strong>Created by:</strong> {creator_name}</p>
                    </div>
                    <p>Please review and approve or reject this goal at your earliest convenience.</p>
                    <center>
                        <a href="{goal_link}" class="button">Review Goal</a>
                    </center>
                    <p>Or copy and paste this link in your browser:</p>
                    <div class="link-box">{goal_link}</div>
                </div>
                <div class="footer">
                    <p>This is an automated notification from Nigcomsat Performance Management System</p>
                    <p>&copy; 2024 Nigcomsat. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return EmailService.send_email(
            to=[supervisor_email],
            subject=f"Goal Approval Required: {goal_title}",
            html=html
        )

    @staticmethod
    def send_goal_approved_email(
        user_email: str,
        user_name: str,
        goal_title: str,
        goal_id: str,
        approved_by_name: str
    ):
        """Send goal approved notification"""
        goal_link = f"{FRONTEND_URL}/dashboard/goals?id={goal_id}"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.6;
                    color: #37352f;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 40px 20px;
                    background-color: #ffffff;
                }}
                .container {{
                    background: #ffffff;
                    border: 1px solid #e9e9e7;
                    border-radius: 8px;
                    overflow: hidden;
                }}
                .header {{
                    padding: 40px 40px 32px;
                    border-bottom: 1px solid #e9e9e7;
                }}
                .header h1 {{
                    color: #37352f;
                    margin: 0;
                    font-size: 20px;
                    font-weight: 600;
                    letter-spacing: -0.01em;
                }}
                .content {{
                    padding: 32px 40px;
                }}
                .content p {{
                    margin: 0 0 16px;
                    color: #37352f;
                    font-size: 14px;
                    line-height: 1.6;
                }}
                .success-box {{
                    background: #f7f6f3;
                    padding: 20px;
                    border-radius: 6px;
                    margin: 20px 0;
                    border-left: 3px solid #37352f;
                }}
                .success-box p {{
                    margin: 8px 0;
                    font-size: 14px;
                    color: #37352f;
                }}
                .button {{
                    display: inline-block;
                    padding: 10px 20px;
                    background: #37352f;
                    color: white;
                    text-decoration: none;
                    border-radius: 6px;
                    margin: 16px 0;
                    font-weight: 500;
                    font-size: 14px;
                    transition: background 0.2s;
                }}
                .button:hover {{
                    background: #2f2e2a;
                }}
                .footer {{
                    padding: 32px 40px;
                    background: #f7f6f3;
                    text-align: center;
                    color: #787774;
                    font-size: 13px;
                    line-height: 1.5;
                }}
                .footer p {{
                    margin: 8px 0;
                }}
                .link-box {{
                    background: #f7f6f3;
                    padding: 16px;
                    border-radius: 6px;
                    margin: 16px 0;
                    word-break: break-all;
                    font-size: 13px;
                    color: #787774;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Goal Approved</h1>
                </div>
                <div class="content">
                    <p>Hello {user_name},</p>
                    <p>Great news! Your goal has been <strong>approved</strong>.</p>
                    <div class="success-box">
                        <p><strong>Goal:</strong> {goal_title}</p>
                        <p><strong>Approved by:</strong> {approved_by_name}</p>
                        <p><strong>Status:</strong> ACTIVE</p>
                    </div>
                    <p>You can now start working on achieving this goal. Good luck!</p>
                    <center>
                        <a href="{goal_link}" class="button">View Goal</a>
                    </center>
                    <p>Or copy and paste this link in your browser:</p>
                    <div class="link-box">{goal_link}</div>
                </div>
                <div class="footer">
                    <p>This is an automated notification from Nigcomsat Performance Management System</p>
                    <p>&copy; 2024 Nigcomsat. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return EmailService.send_email(
            to=[user_email],
            subject=f"Goal Approved: {goal_title}",
            html=html
        )

    @staticmethod
    def send_goal_rejected_email(
        user_email: str,
        user_name: str,
        goal_title: str,
        goal_id: str,
        rejected_by_name: str,
        rejection_reason: str
    ):
        """Send goal rejected notification"""
        goal_link = f"{FRONTEND_URL}/dashboard/goals?id={goal_id}"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.6;
                    color: #37352f;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 40px 20px;
                    background-color: #ffffff;
                }}
                .container {{
                    background: #ffffff;
                    border: 1px solid #e9e9e7;
                    border-radius: 8px;
                    overflow: hidden;
                }}
                .header {{
                    padding: 40px 40px 32px;
                    border-bottom: 1px solid #e9e9e7;
                }}
                .header h1 {{
                    color: #37352f;
                    margin: 0;
                    font-size: 20px;
                    font-weight: 600;
                    letter-spacing: -0.01em;
                }}
                .content {{
                    padding: 32px 40px;
                }}
                .content p {{
                    margin: 0 0 16px;
                    color: #37352f;
                    font-size: 14px;
                    line-height: 1.6;
                }}
                .error-box {{
                    background: #f7f6f3;
                    padding: 20px;
                    border-radius: 6px;
                    margin: 20px 0;
                    border-left: 3px solid #37352f;
                }}
                .error-box p {{
                    margin: 8px 0;
                    font-size: 14px;
                    color: #37352f;
                }}
                .button {{
                    display: inline-block;
                    padding: 10px 20px;
                    background: #37352f;
                    color: white;
                    text-decoration: none;
                    border-radius: 6px;
                    margin: 16px 0;
                    font-weight: 500;
                    font-size: 14px;
                    transition: background 0.2s;
                }}
                .button:hover {{
                    background: #2f2e2a;
                }}
                .footer {{
                    padding: 32px 40px;
                    background: #f7f6f3;
                    text-align: center;
                    color: #787774;
                    font-size: 13px;
                    line-height: 1.5;
                }}
                .footer p {{
                    margin: 8px 0;
                }}
                .link-box {{
                    background: #f7f6f3;
                    padding: 16px;
                    border-radius: 6px;
                    margin: 16px 0;
                    word-break: break-all;
                    font-size: 13px;
                    color: #787774;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Goal Not Approved</h1>
                </div>
                <div class="content">
                    <p>Hello {user_name},</p>
                    <p>Your goal has not been approved.</p>
                    <div class="error-box">
                        <p><strong>Goal:</strong> {goal_title}</p>
                        <p><strong>Reviewed by:</strong> {rejected_by_name}</p>
                        <p><strong>Reason:</strong> {rejection_reason}</p>
                    </div>
                    <p>Please review the feedback above and make necessary adjustments. You can edit and resubmit your goal for approval.</p>
                    <center>
                        <a href="{goal_link}" class="button">Edit Goal</a>
                    </center>
                    <p>Or copy and paste this link in your browser:</p>
                    <div class="link-box">{goal_link}</div>
                </div>
                <div class="footer">
                    <p>This is an automated notification from Nigcomsat Performance Management System</p>
                    <p>&copy; 2024 Nigcomsat. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return EmailService.send_email(
            to=[user_email],
            subject=f"Goal Not Approved: {goal_title}",
            html=html
        )
