"""
auth/mailer.py — Email Utility
===============================
Handles sending OTP verification emails.
"""

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from config.settings import settings

conf = ConnectionConfig(
    MAIL_USERNAME = settings.MAIL_USERNAME,
    MAIL_PASSWORD = settings.MAIL_PASSWORD,
    MAIL_FROM = settings.MAIL_FROM,
    MAIL_PORT = settings.MAIL_PORT,
    MAIL_SERVER = settings.MAIL_SERVER,
    MAIL_STARTTLS = True,
    MAIL_SSL_TLS = False,
    USE_CREDENTIALS = True,
    VALIDATE_CERTS = True
)

class Mailer:
    @staticmethod
    async def send_otp(email: str, otp: str):
        html = f"""
        <div style="font-family: sans-serif; max-width: 500px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 10px;">
            <h2 style="color: #6366f1;">Verify your Taxyn Account</h2>
            <p>Your one-time password (OTP) for registration is:</p>
            <div style="background: #f8fafc; padding: 20px; text-align: center; font-size: 32px; font-weight: 800; letter-spacing: 5px; color: #1e293b; border-radius: 8px; margin: 20px 0;">
                {otp}
            </div>
            <p style="color: #64748b; font-size: 14px;">This code will expire in 10 minutes. If you didn't request this, please ignore this email.</p>
        </div>
        """
        
        message = MessageSchema(
            subject="Taxyn - Verification Code",
            recipients=[email],
            body=html,
            subtype=MessageType.html
        )

        fm = FastMail(conf)
        await fm.send_message(message)

    @staticmethod
    async def send_contact_message(
        sender_email: str,
        sender_name: str,
        subject: str,
        message_text: str,
        user_id: str = "",
    ):
        support_email = settings.SUPPORT_EMAIL or settings.MAIL_FROM
        safe_name = sender_name or "Taxyn User"
        safe_user_id = user_id or "anonymous"

        html = f"""
        <div style="font-family: sans-serif; max-width: 620px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 10px;">
            <h2 style="color: #4f46e5; margin: 0 0 10px;">Taxyn Contact Request</h2>
            <p style="margin: 0 0 6px;"><strong>From:</strong> {safe_name} ({sender_email})</p>
            <p style="margin: 0 0 6px;"><strong>User ID:</strong> {safe_user_id}</p>
            <p style="margin: 0 0 12px;"><strong>Subject:</strong> {subject}</p>
            <div style="background: #f8fafc; border-radius: 8px; padding: 14px; white-space: pre-wrap; color: #0f172a;">
                {message_text}
            </div>
        </div>
        """

        msg = MessageSchema(
            subject=f"Taxyn Contact: {subject}",
            recipients=[support_email],
            body=html,
            subtype=MessageType.html,
            reply_to=[sender_email],
        )
        fm = FastMail(conf)
        await fm.send_message(msg)
