"""Unit tests for migrating manually inserted plaintext credentials (no MongoDB required)."""

from types import SimpleNamespace
from typing import Any

import pytest
from bson import ObjectId

from app.core.exceptions import AuthConfigurationError
from app.core.security import verify_password
from app.services.auth_init_service import AuthInitService


class FakeRepo:
    def __init__(self, legacy: dict[str, Any] | None) -> None:
        self.legacy = legacy
        self.upserts: list[dict[str, Any]] = []

    async def find_non_canonical_credential(self) -> dict[str, Any] | None:
        return self.legacy

    async def upsert_authorized_account(self, **kwargs: Any) -> SimpleNamespace:
        self.upserts.append(kwargs)
        return SimpleNamespace(username=kwargs["username"])


def _service() -> AuthInitService:
    return AuthInitService(SimpleNamespace(collection_name="authentication"), SimpleNamespace())  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_plaintext_document_is_hashed_and_migrated() -> None:
    repo = FakeRepo({"_id": ObjectId(), "username": "director", "password": "s3cret!"})
    assert await _service()._migrate_legacy_plaintext_credential(repo) is True  # type: ignore[arg-type]
    (call,) = repo.upserts
    assert call["username"] == "director"
    assert call["password_hash"] != "s3cret!"
    assert verify_password("s3cret!", call["password_hash"])


@pytest.mark.asyncio
async def test_no_legacy_document_is_noop() -> None:
    repo = FakeRepo(None)
    assert await _service()._migrate_legacy_plaintext_credential(repo) is False  # type: ignore[arg-type]
    assert repo.upserts == []


@pytest.mark.asyncio
async def test_unsupported_schema_raises_clear_error() -> None:
    repo = FakeRepo({"_id": ObjectId(), "email": "x@example.com"})
    with pytest.raises(AuthConfigurationError):
        await _service()._migrate_legacy_plaintext_credential(repo)  # type: ignore[arg-type]
    assert repo.upserts == []
