from fastapi import Depends
from fastapi.security import SecurityScopes, OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession


from app.core.config import settings
from app.core.dependencies import get_sql_session
from app.utils.exception_utils import CredentialsException, ForbiddenException
from app.crud import auth_crud, user_crud
from app.auth import security
from app import models


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_STR}/auth/login", scopes={}
)


async def get_current_user(
    security_scopes: SecurityScopes,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_sql_session),
) -> models.User:
    """
    Retrieve the currently authenticated user based on the provided JWT access token.

    Args:
        security_scopes (SecurityScopes): Required scopes for route.
        token (str): JWT access token.
        db (AsyncSession): Database session.

    Returns:
        models.User: Authenticated user object.
    """

    # Decode and validate access token
    try:
        payload = security.decode_token(
            token=token, secret_key=settings.ACCESS_TOKEN_SECRET_KEY
        )
        if payload.type != "access":
            raise CredentialsException(detail="Invalid token type")
    except CredentialsException:
        raise
    except Exception:
        raise CredentialsException(detail="Could not validate credentials")

    jti = payload.jti
    user_id = payload.sub

    # Check if token is revoked (logout or security event)
    if await auth_crud.is_token_revoked(db, jti=jti):
        raise CredentialsException(detail="Token has been revoked")

    # Load user with associated role & permissions
    user = await user_crud.get_user_with_role_and_permissions(db, user_id=user_id)

    if not user:
        raise CredentialsException(detail="User not found")

    # Block inactive user accounts
    if user.status.name != "ACTIVE":
        raise ForbiddenException(detail="User account is inactive")

    # Enforce RBAC permissions
    if security_scopes.scopes:
        user_permissions = set()

        if user.role and user.role.permissions:
            for perm in user.role.permissions:
                user_permissions.add(f"{perm.name}:{perm.scope}")

        for scope in security_scopes.scopes:
            if scope not in user_permissions:
                raise ForbiddenException(detail="Not enough permissions")

    return user
