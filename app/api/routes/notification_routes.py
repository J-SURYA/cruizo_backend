from fastapi import APIRouter, Depends, Security
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app import models, schemas
from app.auth.dependencies import get_current_user
from app.core.dependencies import get_sql_session
from app.services import notification_service
from app.schemas.utility_schemas import PaginationParams, Msg

router = APIRouter()


@router.get(
    "/received",
    response_model=schemas.PaginatedNotifications,
)
async def get_received_notifications(
    pagination: PaginationParams = Depends(),
    filter_params: schemas.NotificationFilterParams = Depends(),
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(get_current_user, scopes=[]),
):
    """
    Retrieve notifications received by the authenticated user.

    Args:
        pagination: Pagination parameters (skip, limit)
        filter_params: Notification filtering criteria (type, status, etc.)
        db: Database session dependency
        current_user: Authenticated user receiving notifications

    Returns:
        Paginated list of notifications received by the user
    """
    return await notification_service.get_received_notifications(
        db, current_user, filter_params, pagination.skip, pagination.limit
    )


@router.get(
    "/sent",
    response_model=schemas.PaginatedNotifications,
)
async def get_sent_notifications(
    pagination: PaginationParams = Depends(),
    filter_params: schemas.NotificationFilterParams = Depends(),
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(get_current_user, scopes=[]),
):
    """
    Retrieve notifications sent by the authenticated user.

    Args:
        pagination: Pagination parameters (skip, limit)
        filter_params: Notification filtering criteria (type, status, etc.)
        db: Database session dependency
        current_user: Authenticated user who sent notifications

    Returns:
        Paginated list of notifications sent by the user
    """
    return await notification_service.get_sent_notifications(
        db, current_user, filter_params, pagination.skip, pagination.limit
    )


@router.get(
    "/export",
    response_class=StreamingResponse,
)
async def export_notifications(
    filter_params: schemas.NotificationFilterParams = Depends(),
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["exports:create"]),
):
    """
    Export all system notifications to Excel format for reporting.

    Args:
        filter_params: Notification filtering criteria for export
        db: Database session dependency

    Returns:
        Streaming response with Excel file containing notification data
    """
    return await notification_service.export_notifications(db, filter_params)


@router.get(
    "/{notification_id}",
    response_model=schemas.NotificationDetailedPublic,
)
async def get_notification_details(
    notification_id: int,
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(get_current_user, scopes=[]),
):
    """
    Retrieve detailed information for a specific notification.

    User must be either the sender or receiver of the notification.

    Args:
        notification_id: Unique identifier of the notification to retrieve
        db: Database session dependency
        current_user: Authenticated user requesting notification details

    Returns:
        Complete notification details including content and metadata
    """
    return await notification_service.get_notification(
        db, notification_id, current_user
    )


@router.patch(
    "/{notification_id}/read",
    response_model=Msg,
)
async def mark_notification_as_read(
    notification_id: int,
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(get_current_user, scopes=[]),
):
    """
    Mark a received notification as read.

    Args:
        notification_id: Unique identifier of the notification to mark as read
        db: Database session dependency
        current_user: Authenticated user marking the notification

    Returns:
        Success message confirming notification read status update
    """
    return await notification_service.mark_as_read(db, notification_id, current_user)


@router.post("", response_model=schemas.NotificationPublic)
async def send_notification(
    notification_in: schemas.NotificationCreate,
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(
        get_current_user, scopes=["notifications:send"]
    ),
):
    """
    Send a new notification to a user.

    This endpoint is typically used by administrators or system processes
    to send notifications to specific users.

    Args:
        notification_in: Notification content and recipient information
        db: Database session dependency
        current_user: Authenticated user sending the notification

    Returns:
        Newly created notification details
    """
    return await notification_service.create_notification(
        db, notification_in, current_user
    )
