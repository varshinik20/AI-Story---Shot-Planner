from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError

from app.config import Settings
from app.db.session import get_db_session
from app.main import create_application


@pytest.mark.asyncio
async def test_health_endpoint_with_live_postgres(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "application": "CINEMIND",
        "database": "connected",
    }


@pytest.mark.asyncio
async def test_health_endpoint_when_database_unavailable() -> None:
    app = create_application(
        Settings(
            DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/cinemind_test_db",
            APP_ENV="test",
            LOG_LEVEL="WARNING",
        )
    )

    class FailingSession:
        async def execute(self, *_args: object, **_kwargs: object) -> None:
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    async def override_failing_session() -> AsyncGenerator[FailingSession, None]:
        yield FailingSession()

    app.dependency_overrides[get_db_session] = override_failing_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as async_client:
        response = await async_client.get("/health")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unhealthy",
        "application": "CINEMIND",
        "database": "unavailable",
    }


@pytest.mark.asyncio
async def test_swagger_docs_and_openapi_available() -> None:
    app = create_application(
        Settings(
            DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/cinemind_test_db",
            APP_ENV="test",
            LOG_LEVEL="WARNING",
        )
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as async_client:
        docs_res = await async_client.get("/docs")
        openapi_res = await async_client.get("/openapi.json")

    assert docs_res.status_code == 200
    assert openapi_res.status_code == 200
    schema = openapi_res.json()
    assert "/health" in schema["paths"]
    assert "/api/v1/projects" in schema["paths"]
    assert "/api/v1/projects/{project_id}/conversations" in schema["paths"]
    assert "/api/v1/conversations/{conversation_id}/messages" in schema["paths"]
