import logging

from app.config import Settings
from app.core.exceptions import AuthConfigurationError
from app.core.security import hash_password
from app.db.mongodb import MongoAuthDatabase
from app.repositories.auth_repository import AuthRepository

logger = logging.getLogger("cinemind.auth.init")


class AuthInitService:
    """Initializes MongoDB connection, indexes, and the single authorized account on startup."""

    def __init__(self, mongo_db: MongoAuthDatabase, settings: Settings) -> None:
        self._mongo_db = mongo_db
        self._settings = settings

    async def initialize(self) -> None:
        """Verify MongoDB and initialize the single authorized account if missing."""
        if not self._settings.JWT_SECRET_KEY.strip():
            raise AuthConfigurationError(
                "JWT_SECRET_KEY must be configured in environment variables before starting authentication."
            )

        await self._mongo_db.connect()
        repo = AuthRepository(self._mongo_db)
        await repo.ensure_indexes()

        existing = await repo.get_authorized_account()
        if existing is not None:
            logger.info(
                "MongoDB authorized account already exists (username='%s'); preserving stored credential.",
                existing.username,
            )
            return

        configured_username = self._settings.AUTH_USERNAME.strip()
        configured_password = self._settings.AUTH_PASSWORD
        if not configured_username or not configured_password:
            raise AuthConfigurationError(
                "No authorized credential exists in MongoDB. Set AUTH_USERNAME and AUTH_PASSWORD "
                "or run scripts/manage_auth_credential.py before starting the backend."
            )

        password_hash = hash_password(configured_password)
        record, created = await repo.create_initial_authorized_account(
            username=configured_username,
            password_hash=password_hash,
            is_active=True,
        )
        if created:
            logger.info(
                "Initialized single authorized account '%s' in MongoDB collection '%s'.",
                record.username,
                self._mongo_db.collection_name,
            )
