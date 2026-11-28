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

        if await self._migrate_legacy_plaintext_credential(repo):
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

    async def _migrate_legacy_plaintext_credential(self, repo: AuthRepository) -> bool:
        """Convert a manually inserted {username, password} document into the canonical hashed record.

        The plaintext password is hashed with Argon2id and the original document is deleted, so no
        plaintext secret remains in MongoDB. The operation is idempotent across concurrent workers:
        the canonical upsert is keyed on a fixed _id and stray documents are removed.
        """
        legacy = await repo.find_non_canonical_credential()
        if legacy is None:
            return False

        username = legacy.get("username")
        plaintext = legacy.get("password")
        if (
            isinstance(username, str)
            and username.strip()
            and isinstance(plaintext, str)
            and plaintext
            and "password_hash" not in legacy
        ):
            record = await repo.upsert_authorized_account(
                username=username.strip(),
                password_hash=hash_password(plaintext),
                is_active=bool(legacy.get("is_active", True)),
            )
            logger.warning(
                "Migrated plaintext credential document for '%s' in collection '%s' to an "
                "Argon2id-hashed record; the plaintext document was removed.",
                record.username,
                self._mongo_db.collection_name,
            )
            return True

        raise AuthConfigurationError(
            f"Collection '{self._mongo_db.collection_name}' contains a credential document with an "
            "unsupported schema (expected 'username' and 'password', or a record created by "
            "scripts/manage_auth_credential.py). Fix or remove it before starting the backend."
        )
