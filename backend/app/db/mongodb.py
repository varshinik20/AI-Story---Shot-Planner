from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import certifi

from pymongo import AsyncMongoClient
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import ConfigurationError, PyMongoError

from app.core.exceptions import AuthDatabaseUnavailableError

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger("cinemind.auth.mongo")


class MongoAuthDatabase:
    """Manages the asynchronous PyMongo connection dedicated exclusively to authentication."""

    def __init__(
        self,
        *,
        url: str,
        database_name: str,
        collection_name: str = "authorized_credentials",
        connect_timeout_ms: int = 10000,
        socket_timeout_ms: int = 20000,
        max_pool_size: int = 100,
        min_pool_size: int = 0,
        max_idle_time_ms: int = 300000,
    ) -> None:
        self._url = url
        self._database_name = database_name
        self._collection_name = collection_name
        self._connect_timeout_ms = connect_timeout_ms
        self._socket_timeout_ms = socket_timeout_ms
        self._max_pool_size = max_pool_size
        self._min_pool_size = min_pool_size
        self._max_idle_time_ms = max_idle_time_ms
        self._client: AsyncMongoClient[dict[str, Any]] | None = None

    @classmethod
    def from_settings(cls, settings: Settings) -> MongoAuthDatabase:
        """Single construction point so the API and CLI scripts share identical client tuning."""
        return cls(
            url=settings.MONGODB_URL,
            database_name=settings.MONGODB_DATABASE,
            collection_name=settings.MONGODB_COLLECTION,
            connect_timeout_ms=settings.MONGODB_CONNECT_TIMEOUT_MS,
            socket_timeout_ms=settings.MONGODB_SOCKET_TIMEOUT_MS,
            max_pool_size=settings.MONGODB_MAX_POOL_SIZE,
            min_pool_size=settings.MONGODB_MIN_POOL_SIZE,
            max_idle_time_ms=settings.MONGODB_MAX_IDLE_TIME_MS,
        )

    def _uses_tls(self) -> bool:
        """SRV (Atlas) URIs enable TLS by default; plain URIs only when tls/ssl=true is set."""
        lowered = self._url.lower()
        return lowered.startswith("mongodb+srv://") or "tls=true" in lowered or "ssl=true" in lowered

    def _client_options(self) -> dict[str, Any]:
        options: dict[str, Any] = {
            "serverSelectionTimeoutMS": self._connect_timeout_ms,
            "connectTimeoutMS": self._connect_timeout_ms,
            "socketTimeoutMS": self._socket_timeout_ms,
            "maxPoolSize": self._max_pool_size,
            "minPoolSize": self._min_pool_size,
            "maxIdleTimeMS": self._max_idle_time_ms,
            "retryWrites": True,
            "retryReads": True,
            "w": "majority",
        }
        if self._uses_tls():
            # Pin to certifi's CA bundle so TLS to Atlas does not depend on the host OS trust store.
            options["tlsCAFile"] = certifi.where()
        return options

    @property
    def database_name(self) -> str:
        return self._database_name

    @property
    def collection_name(self) -> str:
        return self._collection_name

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    async def connect(self) -> None:
        """Create the AsyncMongoClient if needed and verify server reachability with a ping."""
        try:
            if self._client is None:
                self._client = AsyncMongoClient(self._url, **self._client_options())
            await self._client.admin.command("ping")
            logger.info(
                "Connected to MongoDB authentication database '%s'.",
                self._database_name,
            )
        except (PyMongoError, ConfigurationError, ValueError, OSError) as exc:
            logger.error(
                "Failed connecting to MongoDB authentication database '%s': %s: %s",
                self._database_name,
                type(exc).__name__,
                str(exc).splitlines()[0][:300] if str(exc) else "",
            )
            await self.close()
            raise AuthDatabaseUnavailableError() from exc

    async def ping(self) -> bool:
        """Verify MongoDB availability for health checks and auth operations."""
        if self._client is None:
            await self.connect()
        assert self._client is not None
        try:
            await self._client.admin.command("ping")
            return True
        except (PyMongoError, ConfigurationError, ValueError, OSError) as exc:
            logger.warning("MongoDB ping failed: %s", type(exc).__name__)
            raise AuthDatabaseUnavailableError() from exc

    def get_database(self) -> AsyncDatabase[dict[str, Any]]:
        if self._client is None:
            raise AuthDatabaseUnavailableError()
        return self._client[self._database_name]

    def get_credentials_collection(self) -> AsyncCollection[dict[str, Any]]:
        return self.get_database()[self._collection_name]

    def get_revoked_tokens_collection(self) -> AsyncCollection[dict[str, Any]]:
        return self.get_database()["revoked_tokens"]

    async def close(self) -> None:
        """Close the MongoDB client cleanly on application shutdown."""
        if self._client is not None:
            try:
                await self._client.close()
            finally:
                self._client = None
            logger.info("MongoDB authentication connection closed.")
