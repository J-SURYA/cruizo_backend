from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, and_
import uuid


from app.models.chat_models import ChatSession, ChatThread
from app.utils.logger_utils import get_logger


logger = get_logger(__name__)


class ChatCRUD:
    """
    Class for managing chat sessions and threads.
    """
    async def get_session(
        self, db: AsyncSession, session_id: str, user_id: str
    ) -> Optional[ChatSession]:
        """
        Get a specific session by session_id and user_id.

        Args:
            db: Database session
            session_id: Session identifier
            user_id: User identifier

        Returns:
            ChatSession if found, None otherwise
        """
        try:
            query = select(ChatSession).where(
                and_(
                    ChatSession.session_id == session_id, ChatSession.user_id == user_id
                )
            )
            result = await db.execute(query)
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"Error getting chat session: {str(e)}")
            raise


    async def get_or_create_session(
        self, db: AsyncSession, user_id: str, session_id: str = None
    ) -> tuple[ChatSession, str]:
        """
        Get or create session and return (session, thread_id).

        Args:
            db: Database session
            user_id: User identifier
            session_id: Optional session identifier

        Returns:
            Tuple of (ChatSession, thread_id)
        """
        if session_id:
            query = select(ChatSession).where(
                and_(
                    ChatSession.session_id == session_id, ChatSession.user_id == user_id
                )
            )
            result = await db.execute(query)
            session = result.scalar_one_or_none()

            if session:
                thread_query = select(ChatThread.thread_id).where(
                    ChatThread.session_id == session.id
                )
                thread_result = await db.execute(thread_query)
                thread_id = thread_result.scalar_one_or_none()

                if thread_id:
                    return session, thread_id

        if not session_id:
            session_id = str(uuid.uuid4())

        session = ChatSession(
            session_id=session_id, user_id=user_id, title=session_id, is_active=True
        )
        db.add(session)
        await db.flush()

        thread = ChatThread(thread_id=session_id, session_id=session.id)
        db.add(thread)
        await db.commit()
        await db.refresh(session)

        return session, session_id


    async def get_session_thread(
        self, db: AsyncSession, session_id: str, user_id: str
    ) -> Optional[str]:
        """
        Get the single thread_id for a session.

        Args:
            db: Database session
            session_id: Session identifier
            user_id: User identifier

        Returns:
            Thread ID if found, None otherwise
        """
        try:
            stmt_session = select(ChatSession.id).where(
                and_(
                    ChatSession.session_id == session_id, ChatSession.user_id == user_id
                )
            )
            result_session = await db.execute(stmt_session)
            session_pk = result_session.scalar_one_or_none()

            if not session_pk:
                return None

            query = select(ChatThread.thread_id).where(
                ChatThread.session_id == session_pk
            )
            result = await db.execute(query)
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"Error getting session thread: {str(e)}")
            return None


    async def get_user_sessions(
        self, db: AsyncSession, user_id: str, limit: int = 20
    ) -> List[ChatSession]:
        """
        Get all sessions for a user.

        Args:
            db: Database session
            user_id: User identifier
            limit: Maximum number of sessions to return

        Returns:
            List of ChatSession objects
        """
        try:
            query = select(ChatSession).where(ChatSession.user_id == user_id)
            query = query.order_by(ChatSession.updated_at.desc()).limit(limit)
            result = await db.execute(query)
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Error getting user sessions: {str(e)}")
            raise


    async def delete_session(self, db: AsyncSession, session_id: str) -> bool:
        """
        Delete the single thread for a session.

        Args:
            db: Database session
            session_id: Session identifier to delete

        Returns:
            True if session was deleted, False otherwise
        """
        try:
            stmt_session = select(ChatSession.id).where(
                ChatSession.session_id == session_id
            )
            result_session = await db.execute(stmt_session)
            session_pk = result_session.scalar_one_or_none()

            if not session_pk:
                return False

            query = delete(ChatThread).where(ChatThread.session_id == session_pk)
            await db.execute(query)
            query = delete(ChatSession).where(ChatSession.session_id == session_id)
            await db.execute(query)

            await db.commit()
            return True

        except Exception as e:
            await db.rollback()
            logger.error(f"Error deleting session thread: {str(e)}")
            raise


chat_crud = ChatCRUD()
