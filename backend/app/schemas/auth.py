from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Single-credential login payload."""

    username: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=1, max_length=256)


class LoginResponse(BaseModel):
    """Safe login response (never returns password or password hash)."""

    authenticated: bool = True
    username: str
    csrf_token: str
    expires_at: str
    message: str = "Authentication successful."


class AuthSessionResponse(BaseModel):
    """Session verification response returned by GET /api/v1/auth/me."""

    authenticated: bool
    username: str | None = None
    csrf_token: str | None = None
    expires_at: str | None = None


class LogoutResponse(BaseModel):
    """Session termination confirmation response."""

    authenticated: bool = False
    message: str = "Logged out successfully."
