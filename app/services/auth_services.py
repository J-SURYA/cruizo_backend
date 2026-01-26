from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone
import uuid


from app import models, schemas
from app.crud import rbac_crud, user_crud, auth_crud
from app.utils.exception_utils import (
    DuplicateEntryException,
    CredentialsException,
    SessionLimitException,
    NotFoundException,
    ForbiddenException,
)
from app.auth import security
from app.core.config import settings
from app.utils.id_utils import generate_prefixed_id


class AuthService:
    """
    Handles user authentication, registration, token generation, session management, and refresh token flows.
    """
    async def register_with_login(
        self, db: AsyncSession, user_in: schemas.UserCreate
    ) -> schemas.Token:
        """
        Register a new customer user and log them in by issuing tokens.

        Args:
            db: DB session
            user_in: UserCreate request payload

        Returns:
            Token schema containing access & refresh tokens
        """
        if await user_crud.get_by_username(db, user_in.username):
            raise DuplicateEntryException("Username already registered")
        if await user_crud.get_by_email(db, user_in.email):
            raise DuplicateEntryException("Email already registered")

        role = await rbac_crud.get_role_by_name(db, models.enums.RoleName.CUSTOMER)
        if not role:
            raise NotFoundException(
                f"Role '{models.enums.RoleName.CUSTOMER}' not found"
            )

        status = await rbac_crud.get_status_by_name(db, models.enums.StatusEnum.ACTIVE)
        if not status:
            raise NotFoundException(
                f"Default '{models.enums.StatusEnum.ACTIVE}' status not found"
            )

        user_id = await generate_prefixed_id(db, prefix="U")
        hashed_password = security.get_password_hash(user_in.password)

        user_in_db = schemas.UserCreate(
            **user_in.model_dump(exclude={"password"}), password=hashed_password
        )

        await user_crud.create_user(
            db,
            user_in=user_in_db,
            user_id=user_id,
            role_id=role.id,
            status_id=status.id,
            referral_code=user_in.referral_code,
        )

        jti = str(uuid.uuid4())
        refresh_token_expires_at = datetime.now(timezone.utc) + timedelta(
            hours=settings.REFRESH_TOKEN_EXPIRE_HOURS
        )

        access_token = security.create_access_token(subject=user_id, jti=jti)
        refresh_token = security.create_refresh_token(subject=user_id, jti=jti)

        await auth_crud.create_session(
            db,
            jti=jti,
            user_id=user_id,
            refresh_token=refresh_token,
            expires_at=refresh_token_expires_at,
        )

        return schemas.Token(
            access_token=access_token, refresh_token=refresh_token, role="CUSTOMER"
        )


    async def login(
        self, db: AsyncSession, form_data: OAuth2PasswordRequestForm
    ) -> schemas.Token:
        """
        Authenticate user, create session, issue access and refresh tokens.

        Args:
            db: DB session
            form_data: Login credentials payload

        Returns:
            Token schema containing access & refresh tokens
        """
        user = await user_crud.get_by_username(db, form_data.username)

        if not user:
            user = await user_crud.get_by_email(db, form_data.username)

        if not user or not security.verify_password(form_data.password, user.password):
            raise CredentialsException("Incorrect username or password")

        if user.status.name != "ACTIVE":
            raise ForbiddenException(
                "Your account is deactivated, Contact your domain admin for activation!"
            )

        active_sessions = await auth_crud.get_session_count_by_user(db, user.id)
        if active_sessions >= settings.MAX_SESSIONS_PER_USER:
            raise SessionLimitException()

        jti = str(uuid.uuid4())
        refresh_token_expires_at = datetime.now(timezone.utc) + timedelta(
            hours=settings.REFRESH_TOKEN_EXPIRE_HOURS
        )

        access_token = security.create_access_token(subject=user.id, jti=jti)
        refresh_token = security.create_refresh_token(subject=user.id, jti=jti)

        await auth_crud.create_session(
            db,
            jti=jti,
            user_id=user.id,
            refresh_token=refresh_token,
            expires_at=refresh_token_expires_at,
        )

        return schemas.Token(
            access_token=access_token, refresh_token=refresh_token, role=user.role.name
        )


    async def logout(self, db: AsyncSession, refresh_token_str: str) -> None:
        """
        Log out user by revoking refresh token session.

        Args:
            db: DB session
            refresh_token_str: Refresh token string

        Returns:
            None
        """
        try:
            payload = security.decode_token(
                token=refresh_token_str, secret_key=settings.REFRESH_TOKEN_SECRET_KEY
            )
            if payload.type != "refresh":
                raise CredentialsException("Invalid token type")
        except Exception:
            raise CredentialsException("Invalid refresh token")

        success = await auth_crud.revoke_session(db, jti=payload.jti)
        if not success:
            raise CredentialsException("Invalid or already revoked token")


    async def refresh(self, db: AsyncSession, refresh_token_str: str) -> schemas.Token:
        """
        Refresh access token using a valid refresh token.

        Args:
            db: DB session
            refresh_token_str: Refresh token

        Returns:
            Token schema with new access token and same refresh token
        """
        try:
            payload = security.decode_token(
                token=refresh_token_str, secret_key=settings.REFRESH_TOKEN_SECRET_KEY
            )
            if payload.type != "refresh":
                raise CredentialsException("Invalid token type")
        except Exception:
            raise CredentialsException("Invalid refresh token")

        if await auth_crud.is_token_revoked(db, payload.jti):
            raise CredentialsException("Refresh token has been revoked")

        db_session = await auth_crud.get_session_by_jti(db, payload.jti)
        if not db_session:
            raise CredentialsException("Invalid or expired session")

        if db_session.expires_at < datetime.now(timezone.utc):
            raise CredentialsException("Refresh token expired")

        user = await user_crud.get_by_id(db, db_session.user_id)
        if not user or user.status.name != "ACTIVE":
            raise CredentialsException("User not found or inactive")

        new_access_token = security.create_access_token(
            subject=user.id, jti=payload.jti
        )

        return schemas.Token(
            access_token=new_access_token,
            refresh_token=refresh_token_str,
            role=user.role.name,
        )


auth_service = AuthService()
