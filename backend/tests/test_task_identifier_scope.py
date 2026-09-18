import pytest


async def _account(api_client, email: str, name: str):
    response = await api_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "TaskPilot-identifier-test!",
            "name": name,
        },
    )
    assert response.status_code == 201, response.text
    auth = response.json()
    headers = {"Authorization": f"Bearer {auth['access_token']}"}

    workspaces = await api_client.get("/api/v1/workspaces", headers=headers)
    assert workspaces.status_code == 200, workspaces.text
    return headers, workspaces.json()[0]["id"]


async def _project_and_first_task(api_client, headers, workspace_id: str):
    project = await api_client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "workspace_id": workspace_id,
            "name": "Development",
            "key": "DEV",
            "description": "",
        },
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]

    board = await api_client.get(
        f"/api/v1/projects/{project_id}/board",
        headers=headers,
    )
    assert board.status_code == 200, board.text
    column_id = board.json()["columns"][0]["id"]

    task = await api_client.post(
        "/api/v1/tasks",
        headers=headers,
        json={
            "project_id": project_id,
            "column_id": column_id,
            "title": "First task",
            "description": "",
            "priority": "none",
        },
    )
    assert task.status_code == 201, task.text
    return task.json()


@pytest.mark.asyncio
async def test_same_readable_task_identifier_is_allowed_in_different_workspaces(api_client):
    headers_a, workspace_a = await _account(
        api_client,
        "identifier-a@example.com",
        "Identifier A",
    )
    headers_b, workspace_b = await _account(
        api_client,
        "identifier-b@example.com",
        "Identifier B",
    )

    task_a = await _project_and_first_task(api_client, headers_a, workspace_a)
    task_b = await _project_and_first_task(api_client, headers_b, workspace_b)

    assert task_a["identifier"] == "DEV-1"
    assert task_b["identifier"] == "DEV-1"
    assert task_a["workspace_id"] != task_b["workspace_id"]
