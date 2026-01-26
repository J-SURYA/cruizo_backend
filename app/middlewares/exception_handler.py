from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError


from app.utils.exception_utils import DetailedHTTPException
from app.utils.logger_utils import get_logger


logger = get_logger(__name__)


async def custom_http_exception_handler(request: Request, exc: DetailedHTTPException):
    """
    Handles custom HTTP exceptions with structured response and logging.

    Args:
        request: Incoming HTTP request
        exc: Detailed HTTP exception instance
    """
    logger.warning(
        f"HTTPException: {exc.status_code} {exc.detail} for {request.method} {request.url}"
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=getattr(exc, "headers", None),
    )


async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Handles unexpected server exceptions with generic error response and logging.

    Args:
        request: Incoming HTTP request
        exc: Exception instance
    """
    logger.error(
        f"UnhandledException: {exc} for {request.method} {request.url}", exc_info=True
    )
    return JSONResponse(
        status_code=500, content={"detail": "An internal server error occurred."}
    )


async def integrity_exception_handler(request: Request, exc: IntegrityError):
    """
    Handles database integrity errors (e.g., unique constraint violations).

    Args:
        request: Incoming HTTP request
        exc: IntegrityError instance
    """
    logger.warning(f"IntegrityError: {exc} for {request.method} {request.url}")
    return JSONResponse(
        status_code=400,
        content={"detail": "This entry already exists or violates a constraint."},
    )
