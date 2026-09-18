from datetime import UTC, datetime, timedelta

import pytest


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_project_analytics_aggregate_contract(api_client):
    register = await api_client.post(
        "/api/v1/auth/register",
        json={
            "email": "analytics-perf@example.com",
            "password": "TaskPilot-analytics-2026!",
            "name": "Analytics Performance",
        },
    )
    assert register.status_code == 201, register.text
    headers = _headers(register.json()["access_token"])

    workspaces = await api_client.get("/api/v1/workspaces", headers=headers)
    assert workspaces.status_code == 200, workspaces.text
    workspace_id = workspaces.json()[0]["id"]

    project = await api_client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "workspace_id": workspace_id,
            "name": "Analytics Aggregate Project",
            "key": "AGG",
            "description": "",
        },
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]

    board = await api_client.get(f"/api/v1/projects/{project_id}/board", headers=headers)
    assert board.status_code == 200, board.text
    column_id = board.json()["columns"][0]["id"]

    async def create(title: str, priority: str, due_date: datetime | None = None):
        response = await api_client.post(
            "/api/v1/tasks",
            headers=headers,
            json={
                "project_id": project_id,
                "column_id": column_id,
                "title": title,
                "priority": priority,
                "due_date": due_date.isoformat() if due_date else None,
            },
        )
        assert response.status_code == 201, response.text
        return response.json()

    now = datetime.now(UTC)
    done = await create("Completed urgent", "urgent", now - timedelta(days=2))
    overdue = await create("Overdue high", "high", now - timedelta(days=1))
    await create("Open high", "high", now + timedelta(days=3))
    archived = await create("Archived medium", "medium", now - timedelta(days=5))

    done_update = await api_client.patch(
        f"/api/v1/tasks/{done['id']}",
        headers=headers,
        json={"version": done["version"], "status": "done"},
    )
    assert done_update.status_code == 200, done_update.text

    archive = await api_client.post(
        f"/api/v1/tasks/{archived['id']}/archive",
        headers=headers,
    )
    assert archive.status_code == 200, archive.text

    response = await api_client.get(
        f"/api/v1/analytics/projects/{project_id}",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()

    assert data == {
        "total_tasks": 3,
        "completed_tasks": 1,
        "open_tasks": 2,
        "overdue_tasks": 1,
        "completion_percentage": 33.3,
        "by_status": {"done": 1, "open": 2},
        "by_priority": {"high": 2, "urgent": 1},
    }

    task = await api_client.get(f"/api/v1/tasks/{overdue['id']}", headers=headers)
    assert task.status_code == 200, task.text
