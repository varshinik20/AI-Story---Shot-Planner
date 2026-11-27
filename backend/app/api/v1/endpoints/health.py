import logging

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.dependencies import AppSettings, DbSession
from app.schemas.common import HealthResponse

logger = logging.getLogger("cinemind.health")

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={
        200: {"model": HealthResponse, "description": "Application and PostgreSQL are healthy"},
        503: {"model": HealthResponse, "description": "PostgreSQL connection unavailable"},
    },
    summary="Check application and PostgreSQL health",
)
async def health_check(
    session: DbSession,
    settings: AppSettings,
) -> HealthResponse | JSONResponse:
    """Verify FastAPI responsiveness and live PostgreSQL database connectivity."""
    try:
        await session.execute(text("SELECT 1"))
        return HealthResponse(
            status="healthy",
            application=settings.APP_NAME,
            database="connected",
        )
    except Exception as exc:
        logger.error("Health check database probe failed: %s", type(exc).__name__)
        payload = HealthResponse(
            status="unhealthy",
            application=settings.APP_NAME,
            database="unavailable",
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=payload.model_dump(),
        )
