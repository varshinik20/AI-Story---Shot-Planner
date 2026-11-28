from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
import uuid

import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pymongo import AsyncMongoClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import Settings
from app.core.exceptions import AuthConfigurationError, AuthDatabaseUnavailableError
from app.core.security import hash_password, verify_password
from app.db.mongodb import MongoAuthDatabase
from app.db.session import get_db_session
from app.main import create_application
from app.repositories.auth_repository import AUTHORIZED_ACCOUNT_ID, AuthRepository
from app.services.auth_init_service import AuthInitService

TEST_MONGO_URL = "mongodb://localhost:27017"
TEST_MONGO_DB = "story_planner_auth_test"
TEST_JWT_SECRET = "mongodb-auth-integration-test-secret-key"
TEST_USERNAME = "studio_director"
TEST_PASSWORD = "StrongDirectorPassword!2026"


def _make_auth_settings(
    *,
    pg_url: str,
    mongo_url: str = TEST_MONGO_URL,
    mongo_db: str = TEST_MONGO_DB,
    auth_username: str = TEST_USERNAME,
    auth_password: str = TEST_PASSWORD,
    jwt_secret: str = TEST_JWT_SECRET,
    rate_limit_attempts: int = 5,
) -> Settings:
    return Settings(
        DATABASE_URL=pg_url,
        APP_ENV="test",
        LOG_LEVEL="WARNING",
        MONGODB_URL=mongo_url,
        MONGODB_DATABASE=mongo_db,
        MONGODB_COLLECTION="authorized_credentials",
        MONGODB_CONNECT_TIMEOUT_MS=1500,
        AUTH_USERNAME=auth_username,
        AUTH_PASSWORD=auth_password,
        JWT_SECRET_KEY=jwt_secret,
        JWT_ALGORITHM="HS256",
        ACCESS_TOKEN_EXPIRE_MINUTES=60,
        AUTH_RATE_LIMIT_ATTEMPTS=rate_limit_attempts,
        AUTH_RATE_LIMIT_WINDOW_SECONDS=300,
    )


@pytest.fixture(scope="session")
def mongo_available() -> str:
    """Verify local MongoDB reachability once per pytest session."""
    import asyncio

    async def _probe() -> None:
        client = AsyncMongoClient(TEST_MONGO_URL, serverSelectionTimeoutMS=1500)
        try:
            await client.admin.command("ping")
        finally:
            await client.close()

    try:
        asyncio.run(_probe())
    except Exception as exc:
        pytest.fail(
            f"MongoDB test instance unavailable at {TEST_MONGO_URL} ({type(exc).__name__})."
        )
    return TEST_MONGO_URL


@pytest_asyncio.fixture
async def clean_mongo_db(mongo_available: str) -> AsyncGenerator[MongoAuthDatabase, None]:
    """Provide an isolated MongoDB auth test database dropped before & after each test."""
    db = MongoAuthDatabase(
        url=mongo_available,
        database_name=TEST_MONGO_DB,
        collection_name="authorized_credentials",
        connect_timeout_ms=1500,
    )
    await db.connect()
    assert db._client is not None
    await db._client.drop_database(TEST_MONGO_DB)
    try:
        yield db
    finally:
        if db._client is not None:
            await db._client.drop_database(TEST_MONGO_DB)
        await db.close()


@pytest_asyncio.fixture
async def auth_app_client(
    pg_engine: AsyncEngine,
    clean_mongo_db: MongoAuthDatabase,
    pg_available: str,
) -> AsyncGenerator[tuple[AsyncClient, AuthRepository, Settings], None]:
    """Unauthenticated HTTPX AsyncClient wired to real PostgreSQL + real MongoDB auth DB."""
    session_factory = async_sessionmaker(
        bind=pg_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    settings = _make_auth_settings(pg_url=pg_available)
    await AuthInitService(clean_mongo_db, settings).initialize()
    app = create_application(settings)
    app.state.mongo_auth_db = clean_mongo_db

    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
            finally:
                await session.close()

    from app.config import get_settings

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_settings] = lambda: settings

    repo = AuthRepository(clean_mongo_db)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client, repo, settings


@pytest.mark.asyncio
async def test_mongodb_connection_initialization_singleton_and_hashing(
    clean_mongo_db: MongoAuthDatabase,
    pg_available: str,
) -> None:
    """Tests 1-5: MongoDB connect, collection init, first-time credential, duplicate prevention, Argon2id hashing."""
    assert await clean_mongo_db.ping() is True
    settings = _make_auth_settings(pg_url=pg_available)

    init_service = AuthInitService(clean_mongo_db, settings)
    await init_service.initialize()

    repo = AuthRepository(clean_mongo_db)
    account = await repo.get_authorized_account()
    assert account is not None
    assert account.id == AUTHORIZED_ACCOUNT_ID
    assert account.username == TEST_USERNAME
    assert account.is_active is True
    assert account.password_hash != TEST_PASSWORD
    assert account.password_hash.startswith("$argon2")
    assert verify_password(TEST_PASSWORD, account.password_hash) is True
    assert verify_password("WrongPassword!", account.password_hash) is False

    # Re-initializing on restart must NOT overwrite stored hash or create duplicates.
    settings_different_pw = _make_auth_settings(
        pg_url=pg_available,
        auth_password="AttemptedRestartOverwrite!999",
    )
    await AuthInitService(clean_mongo_db, settings_different_pw).initialize()

    after_restart = await repo.get_authorized_account()
    assert after_restart is not None
    assert after_restart.password_hash == account.password_hash
    count = await clean_mongo_db.get_credentials_collection().count_documents({})
    assert count == 1

    # Duplicate explicit initial creation must also return created=False cleanly.
    _, created_second = await repo.create_initial_authorized_account(
        username="rogue_second_user",
        password_hash=hash_password("AnotherPassword!123"),
    )
    assert created_second is False
    assert await clean_mongo_db.get_credentials_collection().count_documents({}) == 1


@pytest.mark.asyncio
async def test_missing_config_fails_clearly_without_creating_defaults(
    clean_mongo_db: MongoAuthDatabase,
    pg_available: str,
) -> None:
    """Missing AUTH_USERNAME/AUTH_PASSWORD or JWT_SECRET_KEY fails clearly without default creds."""
    missing_secret = _make_auth_settings(pg_url=pg_available, jwt_secret="")
    with pytest.raises(AuthConfigurationError):
        await AuthInitService(clean_mongo_db, missing_secret).initialize()

    missing_creds = _make_auth_settings(pg_url=pg_available, auth_username="", auth_password="")
    with pytest.raises(AuthConfigurationError):
        await AuthInitService(clean_mongo_db, missing_creds).initialize()

    assert await clean_mongo_db.get_credentials_collection().count_documents({}) == 0


@pytest.mark.asyncio
async def test_login_logout_refresh_csrf_rate_limit_and_protected_routes(
    auth_app_client: tuple[AsyncClient, AuthRepository, Settings],
) -> None:
    """Tests 6-13: Login, invalid credentials, rate limit, JWT/cookie refresh, protected endpoints, CSRF, logout."""
    client, repo, settings = auth_app_client

    # Public routes remain accessible
    assert (await client.get("/health")).status_code == 200
    me_initial = await client.get("/api/v1/auth/me")
    assert me_initial.status_code == 200
    assert me_initial.json()["authenticated"] is False

    # Protected APIs reject unauthenticated callers with 401
    fake_id = str(uuid.uuid4())
    for method, path in [
        ("GET", "/api/v1/projects"),
        ("POST", "/api/v1/chat/message"),
        ("POST", "/api/v1/stories/develop"),
        ("POST", "/api/v1/intent/interview"),
        ("POST", "/api/v1/narrative/analyze"),
        ("POST", "/api/v1/scenes/generate"),
        ("POST", "/api/v1/shots/generate"),
        ("POST", "/api/v1/validation/run"),
        ("GET", f"/api/v1/planner/{fake_id}"),
        ("GET", f"/api/v1/usage/{fake_id}"),
    ]:
        res = await client.request(method, path)
        assert res.status_code == 401, f"Expected 401 for {method} {path}, got {res.status_code}"

    # Invalid username & wrong password -> generic 401
    bad_user = await client.post(
        "/api/v1/auth/login",
        json={"username": "nobody", "password": TEST_PASSWORD},
    )
    assert bad_user.status_code == 401
    assert bad_user.json()["error"]["message"] == "Invalid username or password."

    bad_pw = await client.post(
        "/api/v1/auth/login",
        json={"username": TEST_USERNAME, "password": "wrong-password"},
    )
    assert bad_pw.status_code == 401
    assert bad_pw.json()["error"]["message"] == "Invalid username or password."

    # Valid login sets HttpOnly JWT cookie & CSRF cookie without leaking password/hash
    ok_login = await client.post(
        "/api/v1/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    assert ok_login.status_code == 200
    login_body = ok_login.json()
    assert login_body["authenticated"] is True
    assert login_body["username"] == TEST_USERNAME
    assert "password" not in str(login_body).lower()
    csrf_token = login_body["csrf_token"]
    session_cookie_val = ok_login.cookies.get(settings.AUTH_COOKIE_NAME)
    assert session_cookie_val
    set_cookie_headers = ok_login.headers.get_list("set-cookie")
    session_header = next(h for h in set_cookie_headers if settings.AUTH_COOKIE_NAME in h)
    assert "httponly" in session_header.lower()
    assert "samesite=lax" in session_header.lower()

    # Refresh / session check passes with cookie
    me_authed = await client.get("/api/v1/auth/me")
    assert me_authed.status_code == 200
    assert me_authed.json()["authenticated"] is True
    assert me_authed.json()["username"] == TEST_USERNAME

    # Protected PostgreSQL reads work once authenticated
    list_res = await client.get("/api/v1/projects")
    assert list_res.status_code == 200

    # Cookie-authenticated state change without X-CSRF-Token returns 403
    no_csrf_res = await client.post(
        "/api/v1/projects",
        json={"title": "CSRF Guard Project", "description": "Testing CSRF enforcement"},
    )
    assert no_csrf_res.status_code == 403

    # With matching X-CSRF-Token, PostgreSQL project creation succeeds cleanly
    create_res = await client.post(
        "/api/v1/projects",
        headers={"X-CSRF-Token": csrf_token},
        json={"title": "Mongo Authed Project", "description": "PostgreSQL domain row intact"},
    )
    assert create_res.status_code == 201
    assert create_res.json()["title"] == "Mongo Authed Project"

    # Expired & invalid JWT rejection
    expired_token = jwt.encode(
        {
            "sub": TEST_USERNAME,
            "jti": str(uuid.uuid4()),
            "type": "access",
            "iat": int((datetime.now(timezone.utc) - timedelta(hours=2)).timestamp()),
            "exp": int((datetime.now(timezone.utc) - timedelta(minutes=5)).timestamp()),
        },
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    async with AsyncClient(
        transport=client._transport,
        base_url="http://testserver",
        cookies={settings.AUTH_COOKIE_NAME: expired_token},
    ) as expired_client:
        expired_res = await expired_client.get("/api/v1/projects")
    assert expired_res.status_code == 401

    async with AsyncClient(
        transport=client._transport,
        base_url="http://testserver",
        cookies={settings.AUTH_COOKIE_NAME: "not.a.valid.jwt"},
    ) as tampered_client:
        tampered_res = await tampered_client.get("/api/v1/projects")
    assert tampered_res.status_code == 401

    # Logout clears cookies and revokes JWT ID in MongoDB so replaying cookie is rejected!
    logout_res = await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf_token})
    assert logout_res.status_code == 200
    assert (await client.get("/api/v1/auth/me")).json()["authenticated"] is False
    async with AsyncClient(
        transport=client._transport,
        base_url="http://testserver",
        cookies={settings.AUTH_COOKIE_NAME: session_cookie_val},
    ) as replay_client:
        replay_res = await replay_client.get("/api/v1/projects")
    assert replay_res.status_code == 401

    # Rate limit after repeated failures returns 429
    for _ in range(settings.AUTH_RATE_LIMIT_ATTEMPTS):
        r = await client.post(
            "/api/v1/auth/login",
            json={"username": TEST_USERNAME, "password": "bad"},
        )
        assert r.status_code == 401
    blocked = await client.post(
        "/api/v1/auth/login",
        json={"username": TEST_USERNAME, "password": "bad"},
    )
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"

    # Inactive account rejection (even with valid credentials once rate limit resets)
    await repo.set_account_active(False)
    app_state_limiter = getattr(client._transport.app.state, "login_rate_limiter")  # type: ignore[attr-defined]
    await app_state_limiter.reset()
    inactive_res = await client.post(
        "/api/v1/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    assert inactive_res.status_code == 401


@pytest.mark.asyncio
async def test_mongodb_unavailable_returns_503_safely(pg_available: str) -> None:
    """Test 14: Unreachable MongoDB returns 503 safely without leaking connection URI or tracebacks."""
    bad_settings = _make_auth_settings(
        pg_url=pg_available,
        mongo_url="mongodb://user:supersecret@127.0.0.1:27999",
    )
    app = create_application(bad_settings)
    from app.config import get_settings

    app.dependency_overrides[get_settings] = lambda: bad_settings

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            res = await client.post(
                "/api/v1/auth/login",
                json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
            )
    finally:
        await app.state.mongo_auth_db.close()
    assert res.status_code == 503
    body_text = res.text
    assert "supersecret" not in body_text
    assert "27999" not in body_text
    assert res.json()["error"]["code"] == "AUTH_DATABASE_UNAVAILABLE"

    failing_db = MongoAuthDatabase(
        url="mongodb://127.0.0.1:27999",
        database_name=TEST_MONGO_DB,
        connect_timeout_ms=600,
    )
    with pytest.raises(AuthDatabaseUnavailableError):
        await failing_db.connect()
