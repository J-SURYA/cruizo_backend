import logging
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List


from app import schemas
from app.crud import user_crud
from app.models.enums import NotificationType
from app.services.notification_services import notification_service


logger = logging.getLogger(__name__)


async def send_system_notification(
    db: AsyncSession,
    receiver_id: str,
    subject: str,
    body: str,
    type: NotificationType = NotificationType.SYSTEM,
    attachment_urls: Optional[List[str]] = None,
) -> bool:
    """
    Send a notification on behalf of the system user.

    Args:
        db (AsyncSession): Database session
        receiver_id (str): Receiver user ID
        subject (str): Notification subject
        body (str): Notification body text
        type (NotificationType): Type of notification
        attachment_urls (Optional[List[str]]): Optional list of attachment URLs

    Returns:
        bool: True if notification sent, False otherwise
    """
    try:
        # System user must exist (seeded in database)
        system_user = await user_crud.get_by_username(db, "system")
        if not system_user:
            logger.critical(
                "Cannot send automated notification: 'system' user not found."
            )
            return False

        notif_data = schemas.NotificationCreate(
            receiver_id=receiver_id,
            subject=subject,
            body=body,
            type=type,
            attachment_urls=attachment_urls,
        )

        await notification_service.create_notification(
            db, notif_data, sender=system_user
        )
        return True

    except Exception as e:
        logger.error(f"Failed to send system notification to {receiver_id}: {e}")
        return False
