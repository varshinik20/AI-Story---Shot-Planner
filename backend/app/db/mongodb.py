import logging
from typing import Any

from pymongo import AsyncMongoClient
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import ConfigurationError, PyMongoError

from app.core.exceptions import AuthDatabaseUnavailableError

logger = logging.getLogger("cinemind.auth.mongo")


class MongoAuthDatabase:
    """Manages the asynchronous PyMongo connection dedicated exclusively to authentication."""

    def __init__(
        self,
        *,
        url: str,
        database_name: str,
        collection_name: str = "authorized_credentials",
        connect_timeout_ms: int = 5000,
    ) -> None:
        self._url = url
        self._database_name = database_name
        self._collection_name = collection_name
        self._connect_timeout_ms = connect_timeout_ms
        self._client: AsyncMongoClient[dict[str, Any]] | None = None

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
                self._client = AsyncMongoClient(
                    self._url,
                    serverSelectionTimeoutMS=self._connect_timeout_ms,
                    connectTimeoutMS=self._connect_timeout_ms,
                )
            await self._client.admin.command("ping")
            logger.info(
                "Connected to MongoDB authentication database '%s'.",
                self._database_name,
            )
        except (PyMongoError, ConfigurationError, ValueError, OSError) as exc:
            logger.error(
                "Failed connecting to MongoDB authentication database '%s': %s",
                self._database_name,
                type(exc).__name__,
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
