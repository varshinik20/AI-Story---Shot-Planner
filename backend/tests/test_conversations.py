import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_list_get_update_delete_conversation(client: AsyncClient) -> None:
    project = (
        await client.post("/api/v1/projects", json={"title": "The Shadow Within"})
    ).json()

    create_res = await client.post(
        f"/api/v1/projects/{project['id']}/conversations",
        json={"title": "Story Development"},
    )
    assert create_res.status_code == 201
    conv = create_res.json()
    assert conv["project_id"] == project["id"]
    assert conv["title"] == "Story Development"
    assert conv["status"] == "active"

    list_res = await client.get(f"/api/v1/projects/{project['id']}/conversations")
    assert list_res.status_code == 200
    assert list_res.json()["total"] == 1
    assert list_res.json()["items"][0]["id"] == conv["id"]

    get_res = await client.get(f"/api/v1/conversations/{conv['id']}")
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "Story Development"

    patch_res = await client.patch(
        f"/api/v1/conversations/{conv['id']}",
        json={"title": "Creative Intent Interview", "status": "archived"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["title"] == "Creative Intent Interview"
    assert patch_res.json()["status"] == "archived"

    del_res = await client.delete(f"/api/v1/conversations/{conv['id']}")
    assert del_res.status_code == 204

    after_del = await client.get(f"/api/v1/conversations/{conv['id']}")
    assert after_del.status_code == 404
    assert after_del.json()["error"]["code"] == "CONVERSATION_NOT_FOUND"


@pytest.mark.asyncio
async def test_create_conversation_for_nonexistent_project(client: AsyncClient) -> None:
    missing_project_id = uuid.uuid4()
    res = await client.post(
        f"/api/v1/projects/{missing_project_id}/conversations",
        json={"title": "Orphan Thread"},
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "PROJECT_NOT_FOUND"
