from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from datetime import datetime, timezone
from typing import Optional


from app import models


class AuthCRUD:
    """
    Class for managing user authentication sessions and revoked tokens.
    """
    async def create_session(
        self,
        db: AsyncSession,
        jti: str,
        user_id: str,
        refresh_token: str,
        expires_at: datetime,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> models.UserSession:
        """
        Create a new user session with the provided JWT identifier.

        Args:
            db: Database session
            jti: JWT unique identifier
            user_id: User ID associated with the session
            refresh_token: Refresh token string
            expires_at: Session expiration timestamp
            device_info: Optional device information string
            ip_address: Optional IP address of the client

        Returns:
            Newly created UserSession object
        """
        db_session = models.UserSession(
            jti=jti,
            user_id=user_id,
            refresh_token=refresh_token,
            expires_at=expires_at,
            device_info=device_info or "Unknown",
            ip_address=ip_address or "Unknown",
        )
        db.add(db_session)
        await db.commit()
        await db.refresh(db_session)
        return db_session


    async def get_session_by_jti(
        self, db: AsyncSession, jti: str
    ) -> Optional[models.UserSession]:
        """
        Retrieve a user session by its JWT identifier (JTI).

        Args:
            db: Database session
            jti: JWT unique identifier to search for

        Returns:
            UserSession object if found, None otherwise
        """
        result = await db.execute(
            select(models.UserSession).where(models.UserSession.jti == jti)
        )
        return result.scalar_one_or_none()


    async def get_session_by_refresh_token(
        self, db: AsyncSession, refresh_token: str
    ) -> Optional[models.UserSession]:
        """
        Retrieve a user session by the refresh token string.

        Args:
            db: Database session
            refresh_token: Refresh token string to search for

        Returns:
            UserSession object if found, None otherwise
        """
        result = await db.execute(
            select(models.UserSession).where(
                models.UserSession.refresh_token == refresh_token
            )
        )
        return result.scalar_one_or_none()


    async def get_session_count_by_user(self, db: AsyncSession, user_id: str) -> int:
        """
        Count the number of active sessions for a specific user.

        Args:
            db: Database session
            user_id: User ID to count sessions for

        Returns:
            Number of active sessions for the user
        """
        result = await db.execute(
            select(func.count(models.UserSession.jti)).where(
                models.UserSession.user_id == user_id
            )
        )
        return result.scalar() or 0


    async def add_to_revoked_list(self, db: AsyncSession, jti: str, expires_at: datetime):
        """
        Add a JWT identifier to the revoked tokens list.

        Args:
            db: Database session
            jti: JWT unique identifier to revoke
            expires_at: Token expiration timestamp for cleanup
        """
        db_revoked = models.RevokedToken(jti=jti, expires_at=expires_at)
        db.add(db_revoked)
        await db.commit()


    async def is_token_revoked(self, db: AsyncSession, jti: str) -> bool:
        """
        Check if a JWT identifier is in the revoked tokens list.

        Args:
            db: Database session
            jti: JWT unique identifier to check

        Returns:
            True if token is revoked, False otherwise
        """
        result = await db.execute(
            select(models.RevokedToken).where(models.RevokedToken.jti == jti)
        )
        return result.scalar_one_or_none() is not None


    async def revoke_session(self, db: AsyncSession, jti: str) -> bool:
        """
        Revoke a session by removing it from active sessions and adding to revoked list.

        Args:
            db: Database session
            jti: JWT unique identifier of the session to revoke

        Returns:
            True if session was found and revoked, False otherwise
        """
        db_session = await self.get_session_by_jti(db, jti)
        if not db_session:
            return False

        await self.add_to_revoked_list(db, jti=jti, expires_at=db_session.expires_at)
        await db.delete(db_session)
        await db.commit()
        return True


    async def revoke_all_user_sessions(self, db: AsyncSession, user_id: str):
        """
        Revoke and delete all active sessions for a specific user.

        Args:
            db: Database session
            user_id: User ID whose sessions should be revoked
        """
        result = await db.execute(
            select(models.UserSession).where(models.UserSession.user_id == user_id)
        )
        sessions = result.scalars().all()

        for s in sessions:
            await self.add_to_revoked_list(db, jti=s.jti, expires_at=s.expires_at)
            await db.delete(s)

        await db.commit()


    async def prune_expired_revoked_tokens(self, db: AsyncSession):
        """
        Clean up expired tokens from the revoked tokens list.

        Args:
            db: Database session
        """
        now = datetime.now(timezone.utc)
        await db.execute(
            delete(models.RevokedToken).where(models.RevokedToken.expires_at <= now)
        )
        await db.commit()


auth_crud = AuthCRUD()