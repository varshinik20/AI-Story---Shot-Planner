from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hmac
import secrets
from typing import Any
import uuid

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

from app.core.exceptions import AuthConfigurationError, SessionUnauthorizedError

_PASSWORD_HASHER = PasswordHasher()
# Valid dummy Argon2id hash generated lazily once per process for constant-time fallback checks
_DUMMY_HASH = _PASSWORD_HASHER.hash("storyforge-dummy-timing-guard-value")


@dataclass(frozen=True)
class AccessTokenClaims:
    subject: str
    jti: str
    issued_at: datetime
    expires_at: datetime


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using Argon2id."""
    if not plain_password:
        raise ValueError("Password cannot be empty.")
    return _PASSWORD_HASHER.hash(plain_password)


def verify_password(plain_password: str, password_hash: str | None) -> bool:
    """Verify a plaintext password against a stored Argon2id hash safely."""
    if not plain_password:
        return False
    target_hash = password_hash or _DUMMY_HASH
    try:
        matched = _PASSWORD_HASHER.verify(target_hash, plain_password)
        return bool(matched and password_hash is not None)
    except (VerifyMismatchError, InvalidHashError, VerificationError):
        return False


def constant_time_equals(a: str, b: str) -> bool:
    """Compare two strings using a constant-time digest helper."""
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def generate_csrf_token() -> str:
    """Create a cryptographically random token for double-submit CSRF validation."""
    return secrets.token_urlsafe(32)


def create_access_token(
    *,
    subject: str,
    secret_key: str,
    algorithm: str = "HS256",
    expires_minutes: int = 60,
) -> tuple[str, AccessTokenClaims]:
    """Sign an HS* JWT access token containing subject, jti, iat, and exp."""
    cleaned_secret = secret_key.strip()
    if not cleaned_secret:
        raise AuthConfigurationError("JWT_SECRET_KEY must be configured.")

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=expires_minutes)
    jti = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "sub": subject,
        "jti": jti,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, cleaned_secret, algorithm=algorithm)
    return token, AccessTokenClaims(
        subject=subject,
        jti=jti,
        issued_at=now,
        expires_at=expires_at,
    )


def decode_access_token(
    *,
    token: str,
    secret_key: str,
    algorithm: str = "HS256",
) -> AccessTokenClaims:
    """Validate and decode an incoming JWT access token."""
    cleaned_secret = secret_key.strip()
    if not cleaned_secret:
        raise AuthConfigurationError("JWT_SECRET_KEY must be configured.")

    try:
        payload = jwt.decode(
            token,
            cleaned_secret,
            algorithms=[algorithm],
            options={"require": ["sub", "jti", "exp", "iat"]},
        )
    except ExpiredSignatureError as exc:
        raise SessionUnauthorizedError("Session expired. Please sign in again.", code="TOKEN_EXPIRED") from exc
    except InvalidTokenError as exc:
        raise SessionUnauthorizedError("Invalid authentication session.", code="INVALID_TOKEN") from exc

    if payload.get("type") != "access":
        raise SessionUnauthorizedError("Invalid authentication token type.", code="INVALID_TOKEN")

    sub = str(payload.get("sub", "")).strip()
    jti = str(payload.get("jti", "")).strip()
    if not sub or not jti:
        raise SessionUnauthorizedError("Invalid authentication session claims.", code="INVALID_TOKEN")

    issued_at = datetime.fromtimestamp(int(payload["iat"]), tz=timezone.utc)
    expires_at = datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc)
    return AccessTokenClaims(
        subject=sub,
        jti=jti,
        issued_at=issued_at,
        expires_at=expires_at,
    )
