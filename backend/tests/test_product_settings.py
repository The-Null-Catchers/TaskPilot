from uuid import uuid4

import pytest


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_persistent_user_workspace_and_project_settings(api_client):
    suffix = uuid4().hex[:8]
    owner = await api_client.post(
        "/api/v1/auth/register",
        json={
            "email": f"settings-owner-{suffix}@example.com",
            "password": "Owner-password-123!",
            "name": "Settings Owner",
        },
    )
    assert owner.status_code == 201, owner.text
    owner_token = owner.json()["access_token"]

    user_settings = await api_client.get(
        "/api/v1/settings/user",
        headers=_headers(owner_token),
    )
    assert user_settings.status_code == 200, user_settings.text
    assert user_settings.json()["theme"] == "system"
    assert user_settings.json()["density"] == "comfortable"

    updated_user = await api_client.patch(
        "/api/v1/settings/user",
        headers=_headers(owner_token),
        json={
            "theme": "dark",
            "density": "compact",
            "week_start": 0,
            "default_home": "my_tasks",
        },
    )
    assert updated_user.status_code == 200, updated_user.text
    assert updated_user.json()["theme"] == "dark"
    assert updated_user.json()["week_start"] == 0

    workspaces = await api_client.get(
        "/api/v1/workspaces",
        headers=_headers(owner_token),
    )
    workspace_id = workspaces.json()[0]["id"]

    workspace_settings = await api_client.get(
        f"/api/v1/workspaces/{workspace_id}/settings",
        headers=_headers(owner_token),
    )
    assert workspace_settings.status_code == 200, workspace_settings.text
    assert workspace_settings.json()["time_tracking_enabled"] is True

    updated_workspace = await api_client.patch(
        f"/api/v1/workspaces/{workspace_id}/settings",
        headers=_headers(owner_token),
        json={
            "default_project_status": "planning",
            "default_task_priority": "medium",
            "guest_access_enabled": False,
        },
    )
    assert updated_workspace.status_code == 200, updated_workspace.text
    assert updated_workspace.json()["default_project_status"] == "planning"
    assert updated_workspace.json()["default_task_priority"] == "medium"
    assert updated_workspace.json()["guest_access_enabled"] is False

    project = await api_client.post(
        "/api/v1/projects",
        headers=_headers(owner_token),
        json={
            "workspace_id": workspace_id,
            "name": "Settings Project",
            "key": f"S{suffix[:3]}",
        },
    )
    assert project.status_code == 201, project.text
    assert project.json()["status"] == "planning"
    project_id = project.json()["id"]

    project_settings = await api_client.get(
        f"/api/v1/projects/{project_id}/settings/preferences",
        headers=_headers(owner_token),
    )
    assert project_settings.status_code == 200, project_settings.text
    assert project_settings.json()["show_completed_tasks"] is True
    assert project_settings.json()["default_task_priority"] == "medium"

    updated_project = await api_client.patch(
        f"/api/v1/projects/{project_id}/settings/preferences",
        headers=_headers(owner_token),
        json={
            "default_task_priority": "high",
            "time_tracking_enabled": False,
            "auto_complete_on_done_column": True,
            "show_completed_tasks": False,
        },
    )
    assert updated_project.status_code == 200, updated_project.text
    assert updated_project.json()["default_task_priority"] == "high"
    assert updated_project.json()["time_tracking_enabled"] is False
    assert updated_project.json()["auto_complete_on_done_column"] is True
    assert updated_project.json()["show_completed_tasks"] is False

    board = await api_client.get(
        f"/api/v1/projects/{project_id}/board",
        headers=_headers(owner_token),
    )
    assert board.status_code == 200, board.text
    columns = board.json()["columns"]
    backlog_id = columns[0]["id"]
    done_id = next(column["id"] for column in columns if column["name"] == "Done")

    task = await api_client.post(
        "/api/v1/tasks",
        headers=_headers(owner_token),
        json={
            "project_id": project_id,
            "column_id": backlog_id,
            "title": "Use project defaults",
        },
    )
    assert task.status_code == 201, task.text
    assert task.json()["priority"] == "high"

    time_disabled = await api_client.post(
        f"/api/v1/tasks/{task.json()['id']}/time/start",
        headers=_headers(owner_token),
    )
    assert time_disabled.status_code == 409

    moved = await api_client.post(
        f"/api/v1/tasks/{task.json()['id']}/move",
        headers=_headers(owner_token),
        json={
            "column_id": done_id,
            "position": 1000,
            "version": task.json()["version"],
        },
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["status"] == "done"

    filtered_board = await api_client.get(
        f"/api/v1/projects/{project_id}/board",
        headers=_headers(owner_token),
    )
    assert filtered_board.status_code == 200
    assert task.json()["id"] not in {item["id"] for item in filtered_board.json()["tasks"]}

    outsider = await api_client.post(
        "/api/v1/auth/register",
        json={
            "email": f"settings-outsider-{suffix}@example.com",
            "password": "Outsider-password-123!",
            "name": "Settings Outsider",
        },
    )
    assert outsider.status_code == 201, outsider.text
    outsider_token = outsider.json()["access_token"]

    guest_invite = await api_client.post(
        f"/api/v1/workspaces/{workspace_id}/invitations",
        headers=_headers(owner_token),
        json={"email": outsider.json()["user"]["email"], "role": "guest"},
    )
    assert guest_invite.status_code == 409

    forbidden_workspace = await api_client.get(
        f"/api/v1/workspaces/{workspace_id}/settings",
        headers=_headers(outsider_token),
    )
    assert forbidden_workspace.status_code == 403

    forbidden_project = await api_client.patch(
        f"/api/v1/projects/{project_id}/settings/preferences",
        headers=_headers(outsider_token),
        json={"default_task_priority": "urgent"},
    )
    assert forbidden_project.status_code == 403

    invalid_theme = await api_client.patch(
        "/api/v1/settings/user",
        headers=_headers(owner_token),
        json={"theme": "neon"},
    )
    assert invalid_theme.status_code == 422
