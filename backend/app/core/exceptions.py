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


class LLMUnavailableError(CineMindException):
    """Raised when the configured LLM provider is missing credentials or unavailable."""

    def __init__(
        self,
        message: str = "AI service is currently unavailable or not configured.",
        code: str = "LLM_UNAVAILABLE",
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class LLMUpstreamError(CineMindException):
    """Raised when an upstream LLM call fails after retries or returns invalid output."""

    def __init__(
        self,
        message: str = "AI provider returned an invalid or failed response.",
        code: str = "LLM_UPSTREAM_ERROR",
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_502_BAD_GATEWAY,
        )


class AuthenticationError(CineMindException):
    """Raised on invalid credentials or disabled login attempts."""

    def __init__(
        self,
        message: str = "Invalid username or password.",
        code: str = "AUTHENTICATION_FAILED",
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class SessionUnauthorizedError(CineMindException):
    """Raised when an auth cookie or JWT session is missing, invalid, expired, or revoked."""

    def __init__(
        self,
        message: str = "Authentication required.",
        code: str = "UNAUTHORIZED",
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class CSRFValidationError(CineMindException):
    """Raised when a cookie-authenticated state-changing request fails CSRF validation."""

    def __init__(
        self,
        message: str = "CSRF verification failed.",
        code: str = "CSRF_VALIDATION_FAILED",
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class RateLimitExceededError(CineMindException):
    """Raised when login brute-force protection triggers."""

    def __init__(
        self,
        message: str = "Too many login attempts. Please try again later.",
        code: str = "RATE_LIMIT_EXCEEDED",
        retry_after_seconds: int = 60,
    ) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )


class AuthDatabaseUnavailableError(CineMindException):
    """Raised when the MongoDB authentication database cannot be reached."""

    def __init__(
        self,
        message: str = "Authentication service is temporarily unavailable.",
        code: str = "AUTH_DATABASE_UNAVAILABLE",
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class AuthConfigurationError(CineMindException):
    """Raised when required authentication configuration or secrets are missing."""

    def __init__(
        self,
        message: str = "Authentication configuration is incomplete.",
        code: str = "AUTH_CONFIGURATION_ERROR",
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
