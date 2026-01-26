from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from pydantic import EmailStr
from typing import List, Optional


from app.core.config import settings
from app.utils.logger_utils import get_logger


logger = get_logger(__name__)


conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
    MAIL_STARTTLS=settings.MAIL_STARTTLS,
    MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
    USE_CREDENTIALS=settings.USE_CREDENTIALS,
    VALIDATE_CERTS=settings.VALIDATE_CERTS,
    TEMPLATE_FOLDER=None,
)
fm = FastMail(conf)


async def send_email(
    subject: str,
    recipients: List[EmailStr],
    body: str,
    html: Optional[str] = None,
) -> None:
    """
    Send an email in plain text or HTML.

    Args:
        subject (str): Subject of the email.
        recipients (List[EmailStr]): Recipient list.
        body (str): Plain text fallback body.
        html (Optional[str]): HTML content (optional).

    Returns:
        None
    """

    subtype = MessageType.html if html else MessageType.plain
    content = html if html else body
    message = MessageSchema(
        subject=subject,
        recipients=recipients,
        body=content,
        subtype=subtype,
    )

    try:
        await fm.send_message(message)
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        raise
