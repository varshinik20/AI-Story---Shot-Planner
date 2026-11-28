from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.exceptions import (
    AuthDatabaseUnavailableError,
    CSRFValidationError,
)
from app.core.rate_limit import LoginRateLimiter
from app.core.security import constant_time_equals
from app.db.mongodb import MongoAuthDatabase
from app.db.session import get_db_session
from app.repositories.auth_repository import AuthRepository
from app.services.auth_service import AuthenticatedSession, AuthService
from app.services.conversation_service import ConversationService
from app.services.message_service import MessageService
from app.services.project_service import ProjectService

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


async def get_mongo_auth_db(request: Request) -> MongoAuthDatabase:
    """Return app-scoped MongoAuthDatabase, connecting lazily if needed."""
    mongo_db: MongoAuthDatabase | None = getattr(request.app.state, "mongo_auth_db", None)
    if mongo_db is None:
        raise AuthDatabaseUnavailableError()
    if not mongo_db.is_connected:
        await mongo_db.connect()
    return mongo_db


MongoAuthDbDep = Annotated[MongoAuthDatabase, Depends(get_mongo_auth_db)]


def get_auth_repository(mongo_db: MongoAuthDbDep) -> AuthRepository:
    """Provide an AuthRepository backed by the MongoDB auth database."""
    return AuthRepository(mongo_db)


AuthRepoDep = Annotated[AuthRepository, Depends(get_auth_repository)]


def get_auth_service(repo: AuthRepoDep, settings: AppSettings) -> AuthService:
    """Provide a request-scoped AuthService."""
    return AuthService(repo, settings)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def get_login_rate_limiter(request: Request) -> LoginRateLimiter:
    """Return app-scoped sliding-window rate limiter for login attempts."""
    limiter: LoginRateLimiter | None = getattr(request.app.state, "login_rate_limiter", None)
    if limiter is None:
        limiter = LoginRateLimiter()
        request.app.state.login_rate_limiter = limiter
    return limiter


LoginRateLimiterDep = Annotated[LoginRateLimiter, Depends(get_login_rate_limiter)]


async def require_authenticated_user(
    request: Request,
    settings: AppSettings,
    auth_service: AuthServiceDep,
) -> AuthenticatedSession:
    """Verify signed HttpOnly JWT session cookie and enforce double-submit CSRF on mutations."""
    token = request.cookies.get(settings.AUTH_COOKIE_NAME)
    session = await auth_service.verify_session_token(token)

    if request.method.upper() in _MUTATING_METHODS:
        csrf_cookie = request.cookies.get(settings.CSRF_COOKIE_NAME, "")
        csrf_header = request.headers.get("X-CSRF-Token", "")
        if not csrf_cookie or not csrf_header or not constant_time_equals(csrf_cookie, csrf_header):
            raise CSRFValidationError()

    return session


AuthenticatedUser = Annotated[AuthenticatedSession, Depends(require_authenticated_user)]


def get_project_service(session: DbSession) -> ProjectService:
    """Provide a request-scoped ProjectService."""
    return ProjectService(session)


def get_conversation_service(session: DbSession) -> ConversationService:
    """Provide a request-scoped ConversationService."""
    return ConversationService(session)


def get_message_service(session: DbSession) -> MessageService:
    """Provide a request-scoped MessageService."""
    return MessageService(session)
