import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import CineMindException, RateLimitExceededError

logger = logging.getLogger("cinemind.errors")


def _error_payload(code: str, message: str) -> dict[str, dict[str, str]]:
    return {"error": {"code": code, "message": message}}


async def cinemind_exception_handler(
    request: Request, exc: CineMindException
) -> JSONResponse:
    logger.warning(
        "Application error on %s %s: code=%s status=%s message=%s",
        request.method,
        request.url.path,
        exc.code,
        exc.status_code,
        exc.message,
    )
    headers: dict[str, str] = {}
    if isinstance(exc, RateLimitExceededError):
        headers["Retry-After"] = str(exc.retry_after_seconds)
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(exc.code, exc.message),
        headers=headers or None,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    first_error = exc.errors()[0] if exc.errors() else None
    if first_error:
        loc = ".".join(str(part) for part in first_error.get("loc", []) if part != "body")
        msg = first_error.get("msg", "Request validation failed.")
        detail = f"{loc}: {msg}" if loc else msg
    else:
        detail = "Request validation failed."

    logger.info(
        "Validation failure on %s %s: %s",
        request.method,
        request.url.path,
        detail,
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_error_payload("VALIDATION_ERROR", detail),
    )


async def integrity_error_handler(
    request: Request, exc: IntegrityError
) -> JSONResponse:
    logger.warning(
        "Database integrity violation on %s %s: %s",
        request.method,
        request.url.path,
        str(exc.orig) if exc.orig else str(exc),
    )
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=_error_payload(
            "INTEGRITY_ERROR",
            "The operation conflicts with existing data or relational constraints.",
        ),
    )


async def sqlalchemy_error_handler(
    request: Request, exc: SQLAlchemyError
) -> JSONResponse:
    logger.exception(
        "Database error on %s %s",
        request.method,
        request.url.path,
        exc_info=exc,
    )
    if isinstance(exc, OperationalError):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=_error_payload(
                "DATABASE_UNAVAILABLE",
                "Database connection is temporarily unavailable.",
            ),
        )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_payload(
            "DATABASE_ERROR",
            "An unexpected database error occurred.",
        ),
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    code_map = {
        400: "BAD_REQUEST",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        503: "SERVICE_UNAVAILABLE",
    }
    code = code_map.get(exc.status_code, f"HTTP_{exc.status_code}")
    message = str(exc.detail) if exc.detail else "HTTP error occurred."
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(code, message),
    )


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.exception(
        "Unhandled server error on %s %s",
        request.method,
        request.url.path,
        exc_info=exc,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_payload(
            "INTERNAL_SERVER_ERROR",
            "An unexpected internal error occurred.",
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach centralized exception handlers to the FastAPI application."""
    app.add_exception_handler(CineMindException, cinemind_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
