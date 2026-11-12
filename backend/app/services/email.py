import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

async def send_email(to: str, subject: str, body: str) -> None:
    """Dev: log to console. Prod: wire up aiosmtplib if SMTP_URL is set."""
    if not settings.SMTP_URL:
        logger.info(f"[EMAIL to={to}] {subject}\n{body}")
        return
    try:
        from email.message import EmailMessage
        import aiosmtplib
        from urllib.parse import urlparse

        url = urlparse(settings.SMTP_URL)
        msg = EmailMessage()
        msg["From"] = f"EduPlat NG <noreply@{url.hostname}>"
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)

        await aiosmtplib.send(
            msg,
            hostname=url.hostname,
            port=url.port or 587,
            username=url.username,
            password=url.password,
            start_tls=True,
        )
    except Exception as e:
        logger.error(f"Email send failed: {e}")