from sqlalchemy.ext.asyncio import AsyncSession
import pandas as pd
from io import BytesIO
from fastapi.responses import StreamingResponse


from app import models, schemas
from app.crud import system_crud, rbac_crud
from app.utils.exception_utils import NotFoundException, BadRequestException


class NotificationService:
    """
    Service layer for handling notification-related operations and admin export functionality.
    """
    async def get_notification(
        self, db: AsyncSession, notification_id: int, user: models.User
    ) -> models.Notification:
        """
        Retrieve a notification and verify user access.
        
        Args:
            db: DB session
            notification_id: ID of the notification
            user: Current user
        
        Returns:
            Notification object if found and user has access
        
        Raises:
            NotFoundException: If notification not found or access denied
        """
        db_notification = await system_crud.get_notification_by_id(db, notification_id)
        if not db_notification:
            raise NotFoundException("Notification not found")

        if (
            db_notification.receiver_id != user.id
            and db_notification.sender_id != user.id
            and user.role.name != "ADMIN"
        ):
            raise NotFoundException("Notification not found")

        return db_notification


    async def get_received_notifications(
        self,
        db: AsyncSession,
        user: models.User,
        params: schemas.NotificationFilterParams,
        skip: int,
        limit: int,
    ) -> schemas.PaginatedNotifications:
        """
        Get paginated list of notifications received by the user.
        
        Args:
            db: DB session
            user: Current user
            params: Filter params
            skip: Pagination offset
            limit: Pagination limit
        
        Returns:
            PaginatedNotifications schema with total count and items
        """
        base_query = system_crud._get_notification_base_query().where(
            models.Notification.receiver_id == user.id
        )

        items, total = await system_crud.get_paginated_notifications(
            db, base_query, params, skip, limit
        )

        return schemas.PaginatedNotifications(total=total, items=items)


    async def get_sent_notifications(
        self,
        db: AsyncSession,
        user: models.User,
        params: schemas.NotificationFilterParams,
        skip: int,
        limit: int,
    ) -> schemas.PaginatedNotifications:
        """
        Get paginated notifications sent by the user.
        
        Args:
            db: DB session
            user: Current user
            params: Filter params
            skip: Pagination offset
            limit: Pagination limit
        
        Returns:
            PaginatedNotifications schema with total count and items
        """
        base_query = system_crud._get_notification_base_query().where(
            models.Notification.sender_id == user.id
        )

        items, total = await system_crud.get_paginated_notifications(
            db, base_query, params, skip, limit
        )

        return schemas.PaginatedNotifications(total=total, items=items)


    async def create_notification(
        self,
        db: AsyncSession,
        notification_in: schemas.NotificationCreate,
        sender: models.User,
    ) -> models.Notification:
        """
        Create a notification from sender to recipient.
        
        Args:
            db: DB session
            notification_in: Notification creation schema
            sender: Current user sending the notification
        
        Returns:
            Newly created Notification record
        
        Raises:
            BadRequestException: If status missing or receiver doesn't exist
        """
        status_unread = await rbac_crud.get_status_by_name(db, models.StatusEnum.UNREAD)
        if not status_unread:
            raise BadRequestException("System status 'UNREAD' not found.")

        receiver = await db.get(models.User, notification_in.receiver_id)
        if not receiver:
            raise BadRequestException(
                f"Receiver with id {notification_in.receiver_id} not found."
            )

        db_notification = models.Notification(
            **notification_in.model_dump(),
            sender_id=sender.id,
            status_id=status_unread.id,
        )

        return await system_crud.create_notification(db, db_notification)


    async def mark_as_read(
        self, db: AsyncSession, notification_id: int, user: models.User
    ) -> schemas.Msg:
        """
        Mark a notification as read by the receiver.
        
        Args:
            db: DB session
            notification_id: Notification ID
            user: Current user
        
        Returns:
            Success message schema
        
        Raises:
            NotFoundException: If notification missing
            BadRequestException: If notification doesn't belong to user
        """
        db_notification = await system_crud.get_notification_by_id(db, notification_id)
        if not db_notification:
            raise NotFoundException("Notification not found")

        if db_notification.receiver_id != user.id:
            raise BadRequestException(
                "You can only mark your own notifications as read."
            )

        status_read = await rbac_crud.get_status_by_name(db, models.StatusEnum.READ)
        if not status_read:
            raise BadRequestException("System status 'READ' not found.")

        if db_notification.status_id == status_read.id:
            return schemas.Msg(message="Notification already marked as read")

        await system_crud.mark_notification_as_read(db, db_notification, status_read)
        return schemas.Msg(message="Notification marked as read")


    async def export_notifications(
        self, db: AsyncSession, params: schemas.NotificationFilterParams
    ) -> StreamingResponse:
        """
        Admin export of all filtered notifications to Excel.
        
        Args:
            db: DB session
            params: Filter options
        
        Returns:
            Excel file streaming response
        """
        notifications = await system_crud.get_all_notifications_for_export(db, params)

        export_data = []
        for n in notifications:
            export_data.append(
                {
                    "ID": n.id,
                    "Date Sent": n.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "Type": n.type.value,
                    "Sender": n.sender.email if n.sender else "SYSTEM",
                    "Receiver": n.receiver.email,
                    "Subject": n.subject,
                    "Body": n.body,
                    "Status": n.status.name.value,
                    "Read At": (
                        n.read_at.strftime("%Y-%m-%d %H:%M:%S") if n.read_at else "N/A"
                    ),
                }
            )

        df = pd.DataFrame(export_data)
        buffer = BytesIO()

        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Notifications", index=False)

        buffer.seek(0)

        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment; filename=notifications_export.xlsx"
            },
        )


notification_service = NotificationService()
