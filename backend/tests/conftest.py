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
from app.core.security import create_access_token, generate_csrf_token, hash_password  # noqa: E402
from app.db import models as _all_models  # noqa: F401, E402
from app.db.base import Base  # noqa: E402
from app.db.models import Conversation, Message, Project  # noqa: F401, E402
from app.db.session import get_db_session  # noqa: E402
from app.dependencies import get_auth_repository  # noqa: E402
from app.main import create_application  # noqa: E402
from app.repositories.auth_repository import AuthorizedCredentialRecord  # noqa: E402


class _InMemoryTestAuthRepository:
    """Fast deterministic AuthRepository stub so non-auth integration tests pass real JWT/CSRF checks."""

    def __init__(self, username: str, password_hash: str) -> None:
        self.record = AuthorizedCredentialRecord(
            _id="authorized_account",
            username=username,
            password_hash=password_hash,
            is_active=True,
            created_at="2026-11-28T00:00:00+00:00",
            updated_at="2026-11-28T00:00:00+00:00",
        )
        self.revoked_jtis: set[str] = set()

    async def get_authorized_account(self) -> AuthorizedCredentialRecord | None:
        return self.record

    async def is_token_revoked(self, jti: str) -> bool:
        return jti in self.revoked_jtis

    async def revoke_token(self, *, jti: str, expires_at: object) -> None:
        self.revoked_jtis.add(jti)


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
    """HTTPX AsyncClient wired to FastAPI with test PostgreSQL + authenticated session/CSRF."""
    session_factory = async_sessionmaker(
        bind=pg_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    test_secret = "pytest-local-jwt-secret-key-for-integration-tests"
    test_username = "test_director"
    test_settings = Settings(
        DATABASE_URL=get_test_database_url(),
        APP_ENV="test",
        LOG_LEVEL="WARNING",
        JWT_SECRET_KEY=test_secret,
        AUTH_USERNAME=test_username,
        AUTH_PASSWORD="TestPassword123!",
    )
    app = create_application(test_settings)
    auth_repo = _InMemoryTestAuthRepository(
        username=test_username,
        password_hash=hash_password("TestPassword123!"),
    )

    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    def override_get_auth_repository() -> _InMemoryTestAuthRepository:
        return auth_repo

    from app.config import get_settings

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_auth_repository] = override_get_auth_repository
    app.dependency_overrides[get_settings] = lambda: test_settings

    token, _ = create_access_token(
        subject=test_username,
        secret_key=test_secret,
        algorithm=test_settings.JWT_ALGORITHM,
        expires_minutes=test_settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    )
    csrf_token = generate_csrf_token()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        cookies={
            test_settings.AUTH_COOKIE_NAME: token,
            test_settings.CSRF_COOKIE_NAME: csrf_token,
        },
        headers={"X-CSRF-Token": csrf_token},
    ) as async_client:
        yield async_client
