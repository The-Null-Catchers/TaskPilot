import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger("taskpilot.email")


def send_email(recipient: str, subject: str, text: str) -> bool:
    if not settings.smtp_host:
        logger.warning("SMTP is not configured; email delivery was skipped")
        return False
    message = EmailMessage()
    message["From"] = settings.smtp_from_email
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(text)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as client:
        if settings.smtp_starttls:
            client.starttls()
        if settings.smtp_username and settings.smtp_password:
            client.login(settings.smtp_username, settings.smtp_password)
        client.send_message(message)
    return True


def send_account_email(recipient: str, subject: str, text: str) -> None:
    send_email(recipient, subject, text)
