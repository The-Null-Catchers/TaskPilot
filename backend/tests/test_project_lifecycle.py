from uuid import uuid4

import pytest


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_project_settings_archive_and_restore(api_client):
    suffix = uuid4().hex[:8]
    owner = await api_client.post(
        "/api/v1/auth/register",
        json={
            "email": f"project-owner-{suffix}@example.com",
            "password": "Owner-password-123!",
            "name": "Project Owner",
        },
    )
    assert owner.status_code == 201, owner.text
    owner_token = owner.json()["access_token"]

    workspaces = await api_client.get("/api/v1/workspaces", headers=_headers(owner_token))
    assert workspaces.status_code == 200
    workspace_id = workspaces.json()[0]["id"]

    created = await api_client.post(
        "/api/v1/projects",
        headers=_headers(owner_token),
        json={
            "workspace_id": workspace_id,
            "name": "Launch Project",
            "key": f"P{suffix[:3]}",
            "description": "Initial",
            "icon": "rocket",
            "color": "#7c3aed",
            "start_date": "2026-10-01",
            "due_date": "2026-11-01",
        },
    )
    assert created.status_code == 201, created.text
    project = created.json()
    assert project["icon"] == "rocket"
    assert project["color"] == "#7c3aed"
    assert project["archived_at"] is None

    updated = await api_client.patch(
        f"/api/v1/projects/{project['id']}",
        headers=_headers(owner_token),
        json={
            "name": "Launch Project 2",
            "status": "on_hold",
            "color": "#0f766e",
            "due_date": "2026-12-01",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Launch Project 2"
    assert updated.json()["status"] == "on_hold"
    assert updated.json()["color"] == "#0f766e"

    invalid_dates = await api_client.patch(
        f"/api/v1/projects/{project['id']}",
        headers=_headers(owner_token),
        json={"due_date": "2026-09-01"},
    )
    assert invalid_dates.status_code == 422

    outsider = await api_client.post(
        "/api/v1/auth/register",
        json={
            "email": f"project-outsider-{suffix}@example.com",
            "password": "Outsider-password-123!",
            "name": "Outsider",
        },
    )
    assert outsider.status_code == 201
    forbidden = await api_client.patch(
        f"/api/v1/projects/{project['id']}",
        headers=_headers(outsider.json()["access_token"]),
        json={"name": "Nope"},
    )
    assert forbidden.status_code == 403

    archived = await api_client.post(
        f"/api/v1/projects/{project['id']}/archive",
        headers=_headers(owner_token),
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["status"] == "archived"
    assert archived.json()["archived_at"] is not None

    active_list = await api_client.get(
        f"/api/v1/projects?workspace_id={workspace_id}",
        headers=_headers(owner_token),
    )
    assert active_list.status_code == 200
    assert project["id"] not in {item["id"] for item in active_list.json()}

    archived_list = await api_client.get(
        f"/api/v1/projects/archived?workspace_id={workspace_id}",
        headers=_headers(owner_token),
    )
    assert archived_list.status_code == 200
    assert project["id"] in {item["id"] for item in archived_list.json()}

    edit_archived = await api_client.patch(
        f"/api/v1/projects/{project['id']}",
        headers=_headers(owner_token),
        json={"name": "Still archived"},
    )
    assert edit_archived.status_code == 409

    restored = await api_client.post(
        f"/api/v1/projects/{project['id']}/restore",
        headers=_headers(owner_token),
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["status"] == "active"
    assert restored.json()["archived_at"] is None
