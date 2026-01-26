from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession


from app import schemas
from app.core.dependencies import get_sql_session
from app.core.config import settings
from app.services import auth_service
from app.utils.exception_utils import CredentialsException


router = APIRouter()


@router.post("/register", response_model=schemas.TokenResponse)
async def register(
    user_in: schemas.UserCreate,
    db: AsyncSession = Depends(get_sql_session),
    response: Response = None,
):
    """
    Register a new user in the system.

    Args:
        user_in: User registration data containing email, password, and optional role
        db: Database session dependency
        response: HTTP response object for setting cookies

    Returns:
        TokenResponse containing access token and user role
    """
    result = await auth_service.register_with_login(db, user_in)

    response.set_cookie(
        key="refresh_token",
        value=result.refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_HOURS * 60 * 60,
    )
    return schemas.TokenResponse(access_token=result.access_token, role=result.role)


@router.post("/login", response_model=schemas.TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_sql_session),
    response: Response = None,
):
    """
    Authenticate user and issue access and refresh tokens.

    Args:
        form_data: OAuth2 form data containing username and password
        db: Database session dependency
        response: HTTP response object for setting cookies

    Returns:
        TokenResponse containing access token and user role
    """
    result = await auth_service.login(db, form_data)

    response.set_cookie(
        key="refresh_token",
        value=result.refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_HOURS * 60 * 60,
    )
    return schemas.TokenResponse(access_token=result.access_token, role=result.role)


@router.post("/logout", response_model=schemas.Msg)
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_sql_session),
    response: Response = None,
):
    """
    Logout user by revoking their refresh token.

    Args:
        request: HTTP request object containing cookies
        db: Database session dependency
        response: HTTP response object for clearing cookies

    Returns:
        Success message confirming logout
    """
    refresh_token = request.cookies.get("refresh_token")

    if not refresh_token:
        raise CredentialsException("No refresh token found")

    await auth_service.logout(db, refresh_token)

    response.delete_cookie(key="refresh_token", secure=False, samesite="lax")

    return schemas.Msg(message="Logged out successfully")


@router.post("/refresh", response_model=schemas.TokenResponse)
async def refresh(
    request: Request,
    db: AsyncSession = Depends(get_sql_session),
    response: Response = None,
):
    """
    Generate new access token using valid refresh token.

    Args:
        request: HTTP request object containing cookies
        db: Database session dependency
        response: HTTP response object for setting cookies

    Returns:
        TokenResponse containing new access token and user role
    """
    refresh_token = request.cookies.get("refresh_token")

    if not refresh_token:
        raise CredentialsException("No refresh token found")

    result = await auth_service.refresh(db, refresh_token)

    response.set_cookie(
        key="refresh_token",
        value=result.refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_HOURS * 60 * 60,
    )

    return schemas.TokenResponse(access_token=result.access_token, role=result.role)
