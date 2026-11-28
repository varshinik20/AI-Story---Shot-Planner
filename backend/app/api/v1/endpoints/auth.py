from fastapi import APIRouter, Request, Response, status

from app.config import Settings
from app.core.exceptions import AuthenticationError
from app.core.rate_limit import extract_client_ip
from app.core.security import generate_csrf_token
from app.dependencies import (
    AppSettings,
    AuthServiceDep,
    LoginRateLimiterDep,
)
from app.schemas.auth import (
    AuthSessionResponse,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
)
from app.schemas.common import ErrorResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _is_secure_cookie(settings: Settings, request: Request) -> bool:
    return settings.APP_ENV.strip().lower() == "production" or request.url.scheme == "https"


def _clear_auth_cookies(response: Response, settings: Settings, secure: bool) -> None:
    response.delete_cookie(
        key=settings.AUTH_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=secure,
    )
    response.delete_cookie(
        key=settings.CSRF_COOKIE_NAME,
        path="/",
        httponly=False,
        samesite="lax",
        secure=secure,
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid credentials"},
        429: {"model": ErrorResponse, "description": "Too many login attempts"},
        503: {"model": ErrorResponse, "description": "MongoDB auth service unavailable"},
    },
    summary="Sign in with the single authorized credential",
)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    settings: AppSettings,
    auth_service: AuthServiceDep,
    rate_limiter: LoginRateLimiterDep,
) -> LoginResponse:
    client_ip = extract_client_ip(request)
    await rate_limiter.check_allowed(client_ip)

    try:
        result = await auth_service.authenticate(
            username=payload.username,
            password=payload.password,
        )
    except AuthenticationError:
        await rate_limiter.record_failure(client_ip)
        raise

    await rate_limiter.reset(client_ip)
    secure = _is_secure_cookie(settings, request)
    max_age = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=result.access_token,
        max_age=max_age,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=result.csrf_token,
        max_age=max_age,
        httponly=False,
        secure=secure,
        samesite="lax",
        path="/",
    )

    return LoginResponse(
        authenticated=True,
        username=result.username,
        csrf_token=result.csrf_token,
        expires_at=result.expires_at.isoformat(),
    )


@router.get(
    "/me",
    response_model=AuthSessionResponse,
    responses={
        503: {"model": ErrorResponse, "description": "MongoDB auth service unavailable"},
    },
    summary="Verify whether the current browser session cookie is authenticated",
)
async def get_current_session(
    request: Request,
    response: Response,
    settings: AppSettings,
    auth_service: AuthServiceDep,
) -> AuthSessionResponse:
    token = request.cookies.get(settings.AUTH_COOKIE_NAME)
    if not token:
        return AuthSessionResponse(authenticated=False)

    secure = _is_secure_cookie(settings, request)
    try:
        session = await auth_service.verify_session_token(token)
    except Exception as exc:
        # Propagate 503 MongoDB outages or 500 config errors instead of spoofing unauthenticated state.
        from app.core.exceptions import SessionUnauthorizedError

        if not isinstance(exc, SessionUnauthorizedError):
            raise
        _clear_auth_cookies(response, settings, secure)
        return AuthSessionResponse(authenticated=False)

    csrf_token = request.cookies.get(settings.CSRF_COOKIE_NAME)
    if not csrf_token:
        csrf_token = generate_csrf_token()
        response.set_cookie(
            key=settings.CSRF_COOKIE_NAME,
            value=csrf_token,
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            httponly=False,
            secure=secure,
            samesite="lax",
            path="/",
        )

    return AuthSessionResponse(
        authenticated=True,
        username=session.username,
        csrf_token=csrf_token,
        expires_at=session.expires_at.isoformat(),
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Sign out, revoke current JWT session, and clear auth cookies",
)
async def logout(
    request: Request,
    response: Response,
    settings: AppSettings,
    auth_service: AuthServiceDep,
) -> LogoutResponse:
    token = request.cookies.get(settings.AUTH_COOKIE_NAME)
    await auth_service.logout(token)
    secure = _is_secure_cookie(settings, request)
    _clear_auth_cookies(response, settings, secure)
    return LogoutResponse()
