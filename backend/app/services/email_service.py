import smtplib
import socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import BASE_DIR
import os

# Read SMTP settings from environment
SMTP_HOST = os.getenv('SMTP_HOST', '')
SMTP_PORT = int(os.getenv('SMTP_PORT', '0'))
SMTP_USERNAME = os.getenv('SMTP_USERNAME', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
SMTP_FROM_EMAIL = os.getenv('SMTP_FROM_EMAIL', SMTP_USERNAME or 'no-reply@example.com')


class EmailService:
    @staticmethod
    def send_verification_email(to_email: str, otp: str):
        subject = "Verify your AI Mock Interview account"
        body = f"Your verification OTP is: {otp}\n\nThis OTP expires in 5 minutes.\n\nDo not share this OTP with anyone."
        EmailService._send_email(to_email, subject, body)

    @staticmethod
    def send_password_reset_email(to_email: str, otp: str):
        subject = "Reset your AI Mock Interview password"
        body = f"Your password reset OTP is: {otp}\n\nThis OTP expires in 5 minutes.\n\nDo not share this OTP with anyone."
        EmailService._send_email(to_email, subject, body)

    @staticmethod
    def _send_email(to_email: str, subject: str, body: str):
        # If SMTP not configured, raise to allow caller to handle
        if not SMTP_HOST or SMTP_PORT == 0 or not SMTP_USERNAME or not SMTP_PASSWORD:
            # For development convenience, raise an error so caller can catch and mock.
            raise RuntimeError("SMTP server is not configured. Set SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD in environment.")

        msg = MIMEMultipart()
        msg['From'] = SMTP_FROM_EMAIL
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        # Use SMTP SSL for common ports (465) else try STARTTLS (587)
        try:
            if SMTP_PORT == 465:
                server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10)
            else:
                server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
                server.ehlo()
                server.starttls()

            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM_EMAIL, [to_email], msg.as_string())
            server.quit()
        except (smtplib.SMTPException, socket.error) as exc:
            raise RuntimeError(f"Failed to send email: {exc}")
