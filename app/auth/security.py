from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from jose import JWTError, jwt, ExpiredSignatureError
from fastapi import HTTPException, status
from pydantic import ValidationError


from app.core.config import settings
from app.schemas import TokenPayload


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify that a plain text password matches its hashed version.

    Args:
        plain_password (str): User provided password.
        hashed_password (str): Stored hashed password.

    Returns:
        bool: True if password matches.
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a plaintext password using bcrypt.

    Args:
        password (str): User password.

    Returns:
        str: Hashed password.
    """
    return pwd_context.hash(password)


def create_access_token(subject: str | int, jti: str) -> str:
    """
    Create a short-lived JWT access token.

    Args:
        subject (str | int): User ID or identifier.
        jti (str): Unique token identifier.

    Returns:
        str: Encoded access token.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"exp": expire, "sub": str(subject), "jti": jti, "type": "access"}
    return jwt.encode(
        payload, settings.ACCESS_TOKEN_SECRET_KEY, algorithm=settings.ALGORITHM
    )


def create_refresh_token(subject: str | int, jti: str) -> str:
    """
    Create a long-lived JWT refresh token.

    Args:
        subject (str | int): User ID or identifier.
        jti (str): Unique token identifier.

    Returns:
        str: Encoded refresh token.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        hours=settings.REFRESH_TOKEN_EXPIRE_HOURS
    )
    payload = {"exp": expire, "sub": str(subject), "jti": jti, "type": "refresh"}
    return jwt.encode(
        payload, settings.REFRESH_TOKEN_SECRET_KEY, algorithm=settings.ALGORITHM
    )


def decode_token(token: str, secret_key: str) -> TokenPayload:
    """
    Decode a JWT and validate signature, expiration, and structure.

    Args:
        token (str): JWT token string.
        secret_key (str): Key used to decode token.

    Returns:
        TokenPayload: Parsed token payload data.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, secret_key, algorithms=[settings.ALGORITHM])
        token_data = TokenPayload(**payload)

        if token_data.exp is None:
            raise credentials_exception

    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    except (JWTError, ValidationError):
        raise credentials_exception

    return token_data
