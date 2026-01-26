from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from datetime import datetime


from app.models.enums import NotificationType
from .utility_schemas import StatusPublic


class NotificationBase(BaseModel):
    """
    Schema for notification content and configuration.
    """
    subject: str = Field(..., max_length=255, description="Notification subject line")
    body: str = Field(..., description="Notification message content")
    type: NotificationType = Field(..., description="Type of notification")
    attachment_urls: Optional[List[str]] = Field(
        None, description="List of attachment URLs"
    )


class NotificationCreate(NotificationBase):
    """
    Schema for creating and sending a new notification.
    """
    receiver_id: str = Field(
        ..., max_length=255, description="ID of the user receiving the notification"
    )


class NotificationPublic(NotificationBase):
    """
    Schema for notification information in list views.
    """
    id: int = Field(..., description="Notification unique identifier")
    sender_id: Optional[str] = Field(
        None, description="ID of the user who sent the notification"
    )
    receiver_id: str = Field(
        ..., description="ID of the user receiving the notification"
    )
    status: StatusPublic = Field(
        ..., description="Current delivery status of the notification"
    )
    read_at: Optional[datetime] = Field(
        None, description="Timestamp when notification was read by receiver"
    )
    created_at: datetime = Field(..., description="Notification creation timestamp")
    model_config = ConfigDict(from_attributes=True)


class UserSimplePublic(BaseModel):
    """
    Schema for simple user information.
    """
    id: str = Field(..., description="User unique identifier")
    email: str = Field(..., description="User's email address")
    model_config = ConfigDict(from_attributes=True)


class NotificationDetailedPublic(NotificationPublic):
    """
    Schema for detailed notification information including sender and receiver details.
    """
    sender: Optional[UserSimplePublic] = Field(
        None, description="User who sent the notification"
    )
    receiver: UserSimplePublic = Field(
        ..., description="User who received the notification"
    )
    model_config = ConfigDict(from_attributes=True)


class PaginatedNotifications(BaseModel):
    """
    Schema for paginated response of notifications.
    """
    total: int = Field(
        ..., description="Total number of notifications matching filters"
    )
    items: List[NotificationPublic] = Field(
        ..., description="List of notification records"
    )


class NotificationFilterParams:
    """
    Schema for filtering notification queries.
    """
    def __init__(
        self,
        search: Optional[str] = None,
        type: Optional[NotificationType] = None,
        status_id: Optional[int] = None,
    ):
        self.search = search
        self.type = type
        self.status_id = status_id
