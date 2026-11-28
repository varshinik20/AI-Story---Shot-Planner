from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.endpoints.health import router as health_router
from app.api.v1.router import api_router
from app.config import Settings, get_settings
from app.core.error_handlers import register_exception_handlers
from app.core.logging import configure_logging
from app.core.rate_limit import LoginRateLimiter
from app.db.mongodb import MongoAuthDatabase
from app.db.session import dispose_engine, get_engine
from app.services.auth_init_service import AuthInitService

logger = logging.getLogger("cinemind.app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize PostgreSQL & MongoDB auth resources on startup and dispose cleanly on shutdown."""
    settings: Settings = app.state.settings
    logger.info(
        "Starting %s backend (env=%s)",
        settings.APP_NAME,
        settings.APP_ENV,
    )
    get_engine()
    if settings.MONGODB_STARTUP_VALIDATION_ENABLED:
        await AuthInitService(app.state.mongo_auth_db, settings).initialize()
    elif settings.APP_ENV.strip().lower() in {"production", "prod"}:
        raise RuntimeError(
            "MONGODB_STARTUP_VALIDATION_ENABLED=false is not permitted when APP_ENV is production."
        )
    else:
        logger.warning(
            "MongoDB startup validation is DISABLED (MONGODB_STARTUP_VALIDATION_ENABLED=false). "
            "Auth endpoints will return 503 until MongoDB is reachable."
        )
    try:
        yield
    finally:
        await app.state.mongo_auth_db.close()
        await dispose_engine()
        logger.info("%s backend shut down cleanly.", settings.APP_NAME)


def create_application(settings: Settings | None = None) -> FastAPI:
    """FastAPI application factory."""
    app_settings = settings or get_settings()
    configure_logging(app_settings.LOG_LEVEL)

    app = FastAPI(
        title=f"{app_settings.APP_NAME} API",
        description=(
            "CINEMIND (Contextual Intelligence for Narrative, Emotion, Meaning "
            "and Intelligent Direction) — Phase 1 Backend Foundation."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    app.state.mongo_auth_db = MongoAuthDatabase.from_settings(app_settings)
    app.state.login_rate_limiter = LoginRateLimiter(
        max_attempts=app_settings.AUTH_RATE_LIMIT_ATTEMPTS,
        window_seconds=app_settings.AUTH_RATE_LIMIT_WINDOW_SECONDS,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(api_router, prefix=app_settings.API_V1_PREFIX)

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {
            "application": app_settings.APP_NAME,
            "status": "running",
            "docs": "/docs",
            "redoc": "/redoc",
            "health": "/health",
            "api_v1": app_settings.API_V1_PREFIX,
        }

    return app


app = create_application()
