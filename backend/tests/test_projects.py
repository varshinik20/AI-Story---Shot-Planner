import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_application


@pytest.mark.asyncio
async def test_create_and_get_project(client: AsyncClient) -> None:
    payload = {
        "title": "The Boy Who Cried Wolf",
        "description": "A cinematic adaptation of a classic story.",
    }
    create_res = await client.post("/api/v1/projects", json=payload)
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["title"] == payload["title"]
    assert created["description"] == payload["description"]
    assert created["status"] == "active"
    assert "id" in created
    assert "created_at" in created
    assert "updated_at" in created

    get_res = await client.get(f"/api/v1/projects/{created['id']}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == created["id"]
    assert get_res.json()["title"] == payload["title"]


@pytest.mark.asyncio
async def test_list_projects_pagination_and_ordering(client: AsyncClient) -> None:
    p1 = (await client.post("/api/v1/projects", json={"title": "First Film"})).json()
    p2 = (await client.post("/api/v1/projects", json={"title": "Second Film"})).json()
    p3 = (await client.post("/api/v1/projects", json={"title": "Third Film"})).json()

    # Touch First Film so it becomes most recently updated
    patch_res = await client.patch(
        f"/api/v1/projects/{p1['id']}",
        json={"description": "Updated description"},
    )
    assert patch_res.status_code == 200

    list_res = await client.get("/api/v1/projects?limit=2&offset=0")
    assert list_res.status_code == 200
    body = list_res.json()
    assert body["total"] == 3
    assert body["limit"] == 2
    assert body["offset"] == 0
    assert len(body["items"]) == 2
    assert body["items"][0]["id"] == p1["id"]
    assert body["items"][1]["id"] == p3["id"]

    page2 = (await client.get("/api/v1/projects?limit=2&offset=2")).json()
    assert len(page2["items"]) == 1
    assert page2["items"][0]["id"] == p2["id"]


@pytest.mark.asyncio
async def test_update_project_partial_fields(client: AsyncClient) -> None:
    created = (
        await client.post(
            "/api/v1/projects",
            json={"title": "Original Title", "description": "Keep this description"},
        )
    ).json()

    patch_res = await client.patch(
        f"/api/v1/projects/{created['id']}",
        json={"title": "Revised Title", "status": "archived"},
    )
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["title"] == "Revised Title"
    assert updated["status"] == "archived"
    assert updated["description"] == "Keep this description"
    assert updated["updated_at"] >= created["updated_at"]


@pytest.mark.asyncio
async def test_delete_project_and_missing_project(client: AsyncClient) -> None:
    created = (
        await client.post("/api/v1/projects", json={"title": "Temporary Film"})
    ).json()

    del_res = await client.delete(f"/api/v1/projects/{created['id']}")
    assert del_res.status_code == 204

    get_res = await client.get(f"/api/v1/projects/{created['id']}")
    assert get_res.status_code == 404
    assert get_res.json()["error"]["code"] == "PROJECT_NOT_FOUND"

    missing_res = await client.get(f"/api/v1/projects/{uuid.uuid4()}")
    assert missing_res.status_code == 404
    assert missing_res.json()["error"]["code"] == "PROJECT_NOT_FOUND"


@pytest.mark.asyncio
async def test_invalid_project_input_rejected(
    client: AsyncClient,
) -> None:
    empty_title_res = await client.post(
        "/api/v1/projects",
        json={"title": "   ", "description": "Blank title"},
    )
    missing_title_res = await client.post(
        "/api/v1/projects",
        json={"description": "Missing title"},
    )

    assert empty_title_res.status_code == 422
    assert empty_title_res.json()["error"]["code"] == "VALIDATION_ERROR"
    assert missing_title_res.status_code == 422
    assert missing_title_res.json()["error"]["code"] == "VALIDATION_ERROR"
