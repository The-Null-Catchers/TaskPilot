from uuid import uuid4

import pytest


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_task_planning_fields_and_validation(api_client):
    suffix = uuid4().hex[:8]
    registered = await api_client.post(
        "/api/v1/auth/register",
        json={
            "email": f"planning-{suffix}@example.com",
            "password": "Planning-password-123!",
            "name": "Planning User",
        },
    )
    assert registered.status_code == 201, registered.text
    token = registered.json()["access_token"]

    workspaces = await api_client.get("/api/v1/workspaces", headers=_headers(token))
    workspace_id = workspaces.json()[0]["id"]

    project = await api_client.post(
        "/api/v1/projects",
        headers=_headers(token),
        json={"workspace_id": workspace_id, "name": "Planning", "key": f"T{suffix[:3]}"},
    )
    assert project.status_code == 201, project.text

    board = await api_client.get(
        f"/api/v1/projects/{project.json()['id']}/board",
        headers=_headers(token),
    )
    column_id = board.json()["columns"][0]["id"]

    invalid = await api_client.post(
        "/api/v1/tasks",
        headers=_headers(token),
        json={
            "project_id": project.json()["id"],
            "column_id": column_id,
            "title": "Invalid range",
            "start_date": "2026-10-20T12:00:00Z",
            "due_date": "2026-10-10T12:00:00Z",
        },
    )
    assert invalid.status_code == 422

    created = await api_client.post(
        "/api/v1/tasks",
        headers=_headers(token),
        json={
            "project_id": project.json()["id"],
            "column_id": column_id,
            "title": "Plan release",
            "start_date": "2026-10-10T12:00:00Z",
            "due_date": "2026-10-20T12:00:00Z",
            "estimate_minutes": 180,
        },
    )
    assert created.status_code == 201, created.text
    task = created.json()
    assert task["start_date"].startswith("2026-10-10")
    assert task["due_date"].startswith("2026-10-20")
    assert task["estimate_minutes"] == 180

    updated = await api_client.patch(
        f"/api/v1/tasks/{task['id']}",
        headers=_headers(token),
        json={
            "version": task["version"],
            "start_date": "2026-10-12T12:00:00Z",
            "estimate_minutes": 240,
        },
    )
    assert updated.status_code == 200, updated.text
    changed = updated.json()
    assert changed["start_date"].startswith("2026-10-12")
    assert changed["estimate_minutes"] == 240

    invalid_update = await api_client.patch(
        f"/api/v1/tasks/{task['id']}",
        headers=_headers(token),
        json={
            "version": changed["version"],
            "start_date": "2026-10-25T12:00:00Z",
        },
    )
    assert invalid_update.status_code == 422

    cleared = await api_client.patch(
        f"/api/v1/tasks/{task['id']}",
        headers=_headers(token),
        json={
            "version": changed["version"],
            "start_date": None,
            "due_date": None,
            "estimate_minutes": None,
        },
    )
    assert cleared.status_code == 200, cleared.text
    cleared_task = cleared.json()
    assert cleared_task["start_date"] is None
    assert cleared_task["due_date"] is None
    assert cleared_task["estimate_minutes"] is None

    duplicated = await api_client.post(
        f"/api/v1/tasks/{task['id']}/duplicate",
        headers=_headers(token),
        json={},
    )
    assert duplicated.status_code == 201, duplicated.text
    clone = duplicated.json()["task"]
    assert clone["start_date"] is None
    assert clone["due_date"] is None
    assert clone["estimate_minutes"] is None
