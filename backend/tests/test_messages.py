import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models.message import Message
from app.main import create_application


@pytest.mark.asyncio
async def test_create_and_retrieve_messages_in_chronological_order(
    client: AsyncClient,
) -> None:
    project = (
        await client.post("/api/v1/projects", json={"title": "The Boy Who Cried Wolf"})
    ).json()
    conv = (
        await client.post(
            f"/api/v1/projects/{project['id']}/conversations",
            json={"title": "Story Development"},
        )
    ).json()

    m1 = await client.post(
        f"/api/v1/conversations/{conv['id']}/messages",
        json={
            "role": "system",
            "content": "Session initialized.",
            "message_type": "text",
            "metadata": {"phase": "init"},
        },
    )
    assert m1.status_code == 201
    assert m1.json()["metadata"] == {"phase": "init"}

    m2 = await client.post(
        f"/api/v1/conversations/{conv['id']}/messages",
        json={
            "role": "user",
            "content": "I want to develop a story about trust.",
            "message_type": "text",
            "metadata": {},
        },
    )
    assert m2.status_code == 201

    m3 = await client.post(
        f"/api/v1/conversations/{conv['id']}/messages",
        json={
            "role": "assistant",
            "content": "Let us explore the central relationship first.",
            "message_type": "text",
        },
    )
    assert m3.status_code == 201

    list_res = await client.get(f"/api/v1/conversations/{conv['id']}/messages")
    assert list_res.status_code == 200
    body = list_res.json()
    assert body["total"] == 3
    assert [item["role"] for item in body["items"]] == ["system", "user", "assistant"]
    assert [item["content"] for item in body["items"]] == [
        "Session initialized.",
        "I want to develop a story about trust.",
        "Let us explore the central relationship first.",
    ]

    # Verify conversation updated_at was touched
    updated_conv = (await client.get(f"/api/v1/conversations/{conv['id']}")).json()
    assert updated_conv["updated_at"] >= conv["updated_at"]


@pytest.mark.asyncio
async def test_cascade_delete_project_and_conversation_cleans_messages(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    project = (
        await client.post("/api/v1/projects", json={"title": "Cascade Test Film"})
    ).json()
    conv = (
        await client.post(
            f"/api/v1/projects/{project['id']}/conversations",
            json={"title": "Main Thread"},
        )
    ).json()
    await client.post(
        f"/api/v1/conversations/{conv['id']}/messages",
        json={"role": "user", "content": "Message inside cascade test."},
    )

    del_project = await client.delete(f"/api/v1/projects/{project['id']}")
    assert del_project.status_code == 204

    remaining_msgs = (
        await db_session.execute(
            select(Message).where(Message.conversation_id == uuid.UUID(conv["id"]))
        )
    ).scalars().all()
    assert remaining_msgs == []


@pytest.mark.asyncio
async def test_invalid_message_role_and_empty_content_rejected(
    client: AsyncClient,
) -> None:
    conv_id = uuid.uuid4()
    bad_role = await client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"role": "narrator", "content": "Invalid role test."},
    )
    empty_content = await client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"role": "user", "content": "   "},
    )

    assert bad_role.status_code == 422
    assert bad_role.json()["error"]["code"] == "VALIDATION_ERROR"
    assert empty_content.status_code == 422
    assert empty_content.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_message_for_nonexistent_conversation_returns_404(
    client: AsyncClient,
) -> None:
    res = await client.post(
        f"/api/v1/conversations/{uuid.uuid4()}/messages",
        json={"role": "user", "content": "Hello?"},
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "CONVERSATION_NOT_FOUND"
