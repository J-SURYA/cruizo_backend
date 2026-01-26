from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class Location(BaseModel):
    """
    Schema for a geographical location.
    """
    latitude: float
    longitude: float


class MessageSchema(BaseModel):
    """
    Schema for a chat message.
    """
    id: str
    role: str
    content: str
    timestamp: datetime


class AllMessagesResponse(BaseModel):
    """
    Schema for all messages in a session.
    """
    session_id: str
    thread_id: Optional[str]
    messages: List[Dict[str, Any]]
    total_messages: int
    returned_messages: int


class ResetConversationResponse(BaseModel):
    """
    Schema for resetting a conversation.
    """
    message: str
    thread_id: str
    success: bool = True


class BookingDetails(BaseModel):
    """
    Schema for booking-related details.
    """
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    delivery_location: Optional[Location] = None
    pickup_location: Optional[Location] = None


class ChatStreamRequest(BaseModel):
    """
    Schema for streaming chat messages.
    """
    message: str = Field(
        ..., description="User's message/query", min_length=1, max_length=5000
    )
    session_id: Optional[str] = Field(
        None,
        description="Session ID for tracking (Optional, will be auto-generated if not provided)",
    )
    booking_details: Optional[BookingDetails] = Field(
        None, description="Booking details for context (Optional)"
    )
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")


class ErrorResponse(BaseModel):
    """
    Schema for error messages.
    """
    detail: str
    error_code: Optional[str] = None
    thread_id: Optional[str] = None


class SessionSchema(BaseModel):
    """
    Schema for a chat session.
    """
    session_id: str
    title: str
    created_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None
    is_active: bool


class SessionListResponse(BaseModel):
    """
    Schema for a list of chat sessions.
    """
    sessions: List[SessionSchema]
    total: int
