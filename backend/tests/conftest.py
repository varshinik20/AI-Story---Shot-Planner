import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Ensure Settings can initialize during test collection even before .env is copied.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/cinemind_db",
)

from app.config import Settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.models import Conversation, Message, Project  # noqa: F401, E402
from app.db.session import get_db_session  # noqa: E402
from app.main import create_application  # noqa: E402


def get_test_database_url() -> str:
    return os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/cinemind_test_db",
    )


@pytest.fixture(scope="session")
def pg_available() -> str:
    """Verify PostgreSQL test database reachability once per test session."""
    import asyncio

    test_url = get_test_database_url()
    main_url = os.environ.get("DATABASE_URL", "")
    if test_url == main_url:
        pytest.fail(
            "TEST_DATABASE_URL must point to a separate database from DATABASE_URL."
        )

    async def _probe() -> None:
        engine = create_async_engine(
            test_url,
            echo=False,
            connect_args={"timeout": 2},
        )
        try:
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
        finally:
            await engine.dispose()

    try:
        asyncio.run(_probe())
    except Exception as exc:
        pytest.skip(
            f"PostgreSQL test database unavailable ({type(exc).__name__}). "
            "Ensure PostgreSQL is running and TEST_DATABASE_URL is configured."
        )

    return test_url


@pytest_asyncio.fixture
async def pg_engine(pg_available: str) -> AsyncGenerator[AsyncEngine, None]:
    """Provide a clean test PostgreSQL schema for each integration test."""
    engine = create_async_engine(
        pg_available,
        echo=False,
        pool_pre_ping=True,
        connect_args={"timeout": 5},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    try:
        yield engine
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(pg_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Provide an async SQLAlchemy session bound to the test PostgreSQL database."""
    session_factory = async_sessionmaker(
        bind=pg_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(pg_engine: AsyncEngine) -> AsyncGenerator[AsyncClient, None]:
    """HTTPX AsyncClient wired to FastAPI with the test PostgreSQL session override."""
    session_factory = async_sessionmaker(
        bind=pg_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    test_settings = Settings(
        DATABASE_URL=get_test_database_url(),
        APP_ENV="test",
        LOG_LEVEL="WARNING",
    )
    app = create_application(test_settings)

    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db_session] = override_get_db_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as async_client:
        yield async_client
