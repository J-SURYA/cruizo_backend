from typing import Optional
from fastapi import APIRouter, Depends, Security, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession


from app.auth.dependencies import get_current_user
from app.core.dependencies import get_sql_session
from app.crud import chat_crud
from app.models.user_models import User
from app.schemas.chat_schemas import (
    AllMessagesResponse,
    ResetConversationResponse,
    ChatStreamRequest,
    ErrorResponse,
    SessionListResponse,
)
from app.utils.logger_utils import get_logger
from app.assistant.streaming import create_sse_stream
from app.services import chat_service


router = APIRouter()
logger = get_logger(__name__)


@router.post("/stream", responses={500: {"model": ErrorResponse}})
async def chat_stream(
    request: ChatStreamRequest,
    db: AsyncSession = Depends(get_sql_session),
    current_user: User = Security(get_current_user, scopes=["chats:read"]),
):
    """
    Chat in a session with streaming responses.

    Args:
        request: Chat request with message, session_id, and optional booking details
        db: Database session dependency
        current_user: Authenticated user with chats:read permission

    Returns:
        Server-sent events stream with chat responses
    """
    try:
        if request.session_id:
            valid = await chat_crud.get_session(db, request.session_id, current_user.id)
            if not valid:
                raise HTTPException(status_code=403, detail="Invalid session access")

        stream_generator = chat_service.process_query(
            user_id=current_user.id,
            query=request.message,
            session_id=request.session_id,
            booking_details=request.booking_details,
            config=None,
        )

        return await create_sse_stream(stream_generator)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Stream endpoint error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions", response_model=SessionListResponse)
async def get_user_sessions(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_sql_session),
    current_user: User = Security(get_current_user, scopes=["chats:read"]),
):
    """
    Get all sessions of a user.

    Args:
        limit: Maximum number of sessions to return
        db: Database session dependency
        current_user: Authenticated user with chats:read permission

    Returns:
        List of user sessions with metadata
    """
    try:
        sessions = await chat_service.get_user_sessions(db, current_user.id, limit)
        return SessionListResponse(sessions=sessions, total=len(sessions))

    except Exception as e:
        logger.error(f"Error getting user sessions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve sessions")


@router.post(
    "/messages/{session_id}",
    response_model=AllMessagesResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_session_messages(
    session_id: str,
    limit: Optional[int] = Query(None, ge=1, le=10000),
    db: AsyncSession = Depends(get_sql_session),
    current_user: User = Security(get_current_user, scopes=["chats:read"]),
):
    """
    Get all messages for a session.

    Args:
        session_id: Unique identifier of the chat session
        limit: Optional maximum number of messages to return
        db: Database session dependency
        current_user: Authenticated user with chats:read permission

    Returns:
        All messages in the session with conversation history
    """
    messages = await chat_service.get_session_messages(
        db=db, user_id=current_user.id, session_id=session_id, limit=limit
    )

    if not messages:
        raise HTTPException(
            status_code=404, detail="No conversations found for this session"
        )

    return messages


@router.delete(
    "/delete/{session_id}",
    response_model=ResetConversationResponse,
    responses={500: {"model": ErrorResponse}},
)
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_sql_session),
    current_user: User = Security(get_current_user, scopes=["chats:write"]),
):
    """
    Reset a session by deleting its thread and closing the session.

    Args:
        session_id: Unique identifier of the chat session
        db: Database session dependency
        current_user: Authenticated user with chats:write permission

    Returns:
        Confirmation response with reset status
    """
    success = await chat_service.delete_session(
        db=db, user_id=current_user.id, session_id=session_id
    )

    if not success:
        raise HTTPException(
            status_code=500, detail="Failed to reset conversation session"
        )

    return ResetConversationResponse(
        message="Conversation session reset successfully",
        thread_id=session_id,
        success=True,
    )
