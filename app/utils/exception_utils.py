from fastapi import HTTPException, status


class DetailedHTTPException(HTTPException):
    """
    Base exception for all custom HTTP exceptions with extended detail support.
    """

    def __init__(self, status_code: int, detail: str, **kwargs):
        super().__init__(status_code=status_code, detail=detail, **kwargs)


class CredentialsException(DetailedHTTPException):
    """
    Raised when authentication fails or credentials are invalid.
    """

    def __init__(self, detail: str = "Could not validate credentials"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class ForbiddenException(DetailedHTTPException):
    """
    Raised when user lacks required permissions.
    """

    def __init__(self, detail: str = "Not enough permissions"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class NotFoundException(DetailedHTTPException):
    """
    Raised when requested resource does not exist.
    """

    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class DuplicateEntryException(DetailedHTTPException):
    """
    Raised when attempting to create a duplicate resource.
    """

    def __init__(self, detail: str = "This entry already exists"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class BadRequestException(DetailedHTTPException):
    """
    Raised when the request format or data is invalid.
    """

    def __init__(self, detail: str = "Bad request"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class SessionLimitException(DetailedHTTPException):
    """
    Raised when a user exceeds allowed active session limits.
    """

    def __init__(self, detail: str = "Maximum number of allowed sessions reached"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class RateLimitException(DetailedHTTPException):
    """
    Raised when a user exceeds rate limits.
    """

    def __init__(self, detail: str = "Too many requests, please try again later"):
        super().__init__(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)


class IntegrityException(DetailedHTTPException):
    """
    Raised when a database integrity constraint is violated.
    """

    def __init__(self, detail: str = "Integrity constraint violation"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class ServerErrorException(DetailedHTTPException):
    """
    Generic internal server error wrapper.
    """

    def __init__(self, detail: str = "An internal server error occurred"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail
        )
