from dataclasses import dataclass
from datetime import datetime
import logging

from app.config import Settings
from app.core.exceptions import AuthenticationError, SessionUnauthorizedError
from app.core.security import (
    constant_time_equals,
    create_access_token,
    decode_access_token,
    generate_csrf_token,
    verify_password,
)
from app.repositories.auth_repository import AuthRepository

logger = logging.getLogger("cinemind.auth.service")


@dataclass(frozen=True)
class AuthenticatedLoginResult:
    username: str
    access_token: str
    csrf_token: str
    expires_at: datetime


@dataclass(frozen=True)
class AuthenticatedSession:
    username: str
    jti: str
    expires_at: datetime


class AuthService:
    """Handles credential verification, JWT verification, and session revocation."""

    def __init__(self, repository: AuthRepository, settings: Settings) -> None:
        self._repository = repository
        self._settings = settings

    async def authenticate(self, *, username: str, password: str) -> AuthenticatedLoginResult:
        """Verify username and password against the single active MongoDB credential."""
        submitted_user = username.strip()
        if not submitted_user or not password:
            raise AuthenticationError("Invalid username or password.")

        account = await self._repository.get_authorized_account()
        stored_hash = account.password_hash if account is not None else None
        password_ok = verify_password(password, stored_hash)

        if account is None or not account.is_active:
            logger.warning("Login failed: missing or inactive authorized account.")
            raise AuthenticationError("Invalid username or password.")

        username_ok = constant_time_equals(submitted_user, account.username)
        if not (username_ok and password_ok):
            logger.warning("Login failed: credential mismatch.")
            raise AuthenticationError("Invalid username or password.")

        token, claims = create_access_token(
            subject=account.username,
            secret_key=self._settings.JWT_SECRET_KEY,
            algorithm=self._settings.JWT_ALGORITHM,
            expires_minutes=self._settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        )
        csrf_token = generate_csrf_token()
        return AuthenticatedLoginResult(
            username=account.username,
            access_token=token,
            csrf_token=csrf_token,
            expires_at=claims.expires_at,
        )

    async def verify_session_token(self, token: str | None) -> AuthenticatedSession:
        """Decode the JWT cookie, ensure it is not revoked, and confirm account is active."""
        if not token or not token.strip():
            raise SessionUnauthorizedError("Authentication required.")

        claims = decode_access_token(
            token=token.strip(),
            secret_key=self._settings.JWT_SECRET_KEY,
            algorithm=self._settings.JWT_ALGORITHM,
        )

        if await self._repository.is_token_revoked(claims.jti):
            raise SessionUnauthorizedError(
                "Session has been logged out.",
                code="TOKEN_REVOKED",
            )

        account = await self._repository.get_authorized_account()
        if (
            account is None
            or not account.is_active
            or not constant_time_equals(claims.subject, account.username)
        ):
            raise SessionUnauthorizedError("Authorized session is no longer valid.")

        return AuthenticatedSession(
            username=account.username,
            jti=claims.jti,
            expires_at=claims.expires_at,
        )

    async def logout(self, token: str | None) -> None:
        """Revoke the JWT token ID in MongoDB if a valid token is present."""
        if not token or not token.strip():
            return
        try:
            claims = decode_access_token(
                token=token.strip(),
                secret_key=self._settings.JWT_SECRET_KEY,
                algorithm=self._settings.JWT_ALGORITHM,
            )
        except SessionUnauthorizedError:
            return
        await self._repository.revoke_token(jti=claims.jti, expires_at=claims.expires_at)
