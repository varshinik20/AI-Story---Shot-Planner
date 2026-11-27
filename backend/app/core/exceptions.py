from fastapi import status


class CineMindException(Exception):
    """Base application exception with structured error code and HTTP status."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    ) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(CineMindException):
    """Raised when a requested resource does not exist."""

    def __init__(self, message: str, code: str = "RESOURCE_NOT_FOUND") -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class ProjectNotFoundError(NotFoundError):
    """Raised when a project ID cannot be found."""

    def __init__(self, message: str = "The requested project does not exist.") -> None:
        super().__init__(message=message, code="PROJECT_NOT_FOUND")


class ConversationNotFoundError(NotFoundError):
    """Raised when a conversation ID cannot be found."""

    def __init__(self, message: str = "The requested conversation does not exist.") -> None:
        super().__init__(message=message, code="CONVERSATION_NOT_FOUND")


class BadRequestError(CineMindException):
    """Raised for invalid business-level request parameters."""

    def __init__(self, message: str, code: str = "INVALID_REQUEST") -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class ConflictError(CineMindException):
    """Raised on conflicting state or database integrity constraints."""

    def __init__(self, message: str, code: str = "CONFLICT") -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_409_CONFLICT,
        )


class DatabaseUnavailableError(CineMindException):
    """Raised when PostgreSQL cannot be reached."""

    def __init__(
        self,
        message: str = "Database service is currently unavailable.",
    ) -> None:
        super().__init__(
            message=message,
            code="DATABASE_UNAVAILABLE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
