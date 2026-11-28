from datetime import datetime, timezone
import logging
from typing import Any

from pydantic import BaseModel, Field
from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.core.exceptions import AuthDatabaseUnavailableError
from app.db.mongodb import MongoAuthDatabase

logger = logging.getLogger("cinemind.auth.repository")

AUTHORIZED_ACCOUNT_ID = "authorized_account"


class AuthorizedCredentialRecord(BaseModel):
    """Internal MongoDB representation of the single authorized credential."""

    id: str = Field(default=AUTHORIZED_ACCOUNT_ID, alias="_id")
    username: str
    password_hash: str
    is_active: bool = True
    created_at: str
    updated_at: str

    model_config = {"populate_by_name": True}


class AuthRepository:
    """Encapsulates single-credential CRUD and token revocation in MongoDB."""

    def __init__(self, mongo_db: MongoAuthDatabase) -> None:
        self._mongo_db = mongo_db

    async def ensure_indexes(self) -> None:
        """Ensure token revocation indexes (unique jti + TTL cleanup)."""
        try:
            revoked = self._mongo_db.get_revoked_tokens_collection()
            await revoked.create_index([("jti", ASCENDING)], unique=True, name="uq_revoked_jti")
            await revoked.create_index(
                [("expires_at_dt", ASCENDING)],
                expireAfterSeconds=0,
                name="ttl_revoked_expires_at",
            )
        except PyMongoError as exc:
            logger.error("Failed creating MongoDB auth indexes: %s", type(exc).__name__)
            raise AuthDatabaseUnavailableError() from exc

    async def get_authorized_account(self) -> AuthorizedCredentialRecord | None:
        """Retrieve the single authorized credential document if present."""
        try:
            collection = self._mongo_db.get_credentials_collection()
            doc = await collection.find_one({"_id": AUTHORIZED_ACCOUNT_ID})
            if doc is None:
                return None
            return AuthorizedCredentialRecord.model_validate(doc)
        except PyMongoError as exc:
            logger.error("MongoDB read failed for authorized account: %s", type(exc).__name__)
            raise AuthDatabaseUnavailableError() from exc

    async def create_initial_authorized_account(
        self,
        *,
        username: str,
        password_hash: str,
        is_active: bool = True,
    ) -> tuple[AuthorizedCredentialRecord, bool]:
        """Insert the singleton authorized account only if no credential document exists."""
        collection = self._mongo_db.get_credentials_collection()
        try:
            existing_doc = await collection.find_one({"_id": AUTHORIZED_ACCOUNT_ID})
            if existing_doc is not None:
                return AuthorizedCredentialRecord.model_validate(existing_doc), False

            existing_count = await collection.count_documents({}, limit=1)
            if existing_count > 0:
                # Never allow a second credential document in the singleton collection.
                any_doc = await collection.find_one({})
                if any_doc is not None:
                    return AuthorizedCredentialRecord.model_validate(any_doc), False

            now_iso = datetime.now(timezone.utc).isoformat()
            payload: dict[str, Any] = {
                "_id": AUTHORIZED_ACCOUNT_ID,
                "username": username,
                "password_hash": password_hash,
                "is_active": is_active,
                "created_at": now_iso,
                "updated_at": now_iso,
            }
            try:
                await collection.insert_one(payload)
            except DuplicateKeyError:
                existing = await collection.find_one({"_id": AUTHORIZED_ACCOUNT_ID})
                assert existing is not None
                return AuthorizedCredentialRecord.model_validate(existing), False

            return AuthorizedCredentialRecord.model_validate(payload), True
        except PyMongoError as exc:
            logger.error("MongoDB initialize account failed: %s", type(exc).__name__)
            raise AuthDatabaseUnavailableError() from exc

    async def upsert_authorized_account(
        self,
        *,
        username: str,
        password_hash: str,
        is_active: bool = True,
    ) -> AuthorizedCredentialRecord:
        """Admin-only helper to initialize or update the single authorized account."""
        collection = self._mongo_db.get_credentials_collection()
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            existing = await collection.find_one({"_id": AUTHORIZED_ACCOUNT_ID})
            created_at = str(existing["created_at"]) if existing and "created_at" in existing else now_iso

            # Remove any stray documents so the singleton collection invariant is guaranteed.
            await collection.delete_many({"_id": {"$ne": AUTHORIZED_ACCOUNT_ID}})

            payload: dict[str, Any] = {
                "_id": AUTHORIZED_ACCOUNT_ID,
                "username": username,
                "password_hash": password_hash,
                "is_active": is_active,
                "created_at": created_at,
                "updated_at": now_iso,
            }
            await collection.replace_one({"_id": AUTHORIZED_ACCOUNT_ID}, payload, upsert=True)
            return AuthorizedCredentialRecord.model_validate(payload)
        except PyMongoError as exc:
            logger.error("MongoDB upsert authorized account failed: %s", type(exc).__name__)
            raise AuthDatabaseUnavailableError() from exc

    async def set_account_active(self, is_active: bool) -> AuthorizedCredentialRecord | None:
        """Enable or disable the singleton account (used by admin CLI)."""
        collection = self._mongo_db.get_credentials_collection()
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            await collection.update_one(
                {"_id": AUTHORIZED_ACCOUNT_ID},
                {"$set": {"is_active": is_active, "updated_at": now_iso}},
            )
            return await self.get_authorized_account()
        except PyMongoError as exc:
            logger.error("MongoDB account active update failed: %s", type(exc).__name__)
            raise AuthDatabaseUnavailableError() from exc

    async def revoke_token(self, *, jti: str, expires_at: datetime) -> None:
        """Persist a revoked JWT ID until its expiration time."""
        revoked = self._mongo_db.get_revoked_tokens_collection()
        try:
            await revoked.insert_one(
                {
                    "jti": jti,
                    "expires_at_dt": expires_at,
                    "revoked_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        except DuplicateKeyError:
            return
        except PyMongoError as exc:
            logger.error("MongoDB revoke token failed: %s", type(exc).__name__)
            raise AuthDatabaseUnavailableError() from exc

    async def is_token_revoked(self, jti: str) -> bool:
        """Return True if the JWT ID has been explicitly logged out/revoked."""
        revoked = self._mongo_db.get_revoked_tokens_collection()
        try:
            doc = await revoked.find_one({"jti": jti}, {"_id": 1})
            return doc is not None
        except PyMongoError as exc:
            logger.error("MongoDB token revocation lookup failed: %s", type(exc).__name__)
            raise AuthDatabaseUnavailableError() from exc
