from uuid import uuid4

import pytest


def _headers(token: str, mutation_id: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if mutation_id:
        headers["Idempotency-Key"] = mutation_id
    return headers


async def _create_task(api_client):
    suffix = uuid4().hex[:10]
    registered = await api_client.post(
        "/api/v1/auth/register",
        json={
            "email": f"offline-idempotency-{suffix}@example.com",
            "password": "TaskPilot-offline-2026!",
            "name": "Offline Idempotency User",
        },
    )
    assert registered.status_code == 201, registered.text
    token = registered.json()["access_token"]
    headers = _headers(token)

    workspaces = await api_client.get("/api/v1/workspaces", headers=headers)
    assert workspaces.status_code == 200, workspaces.text
    workspace_id = workspaces.json()[0]["id"]
    project = await api_client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "workspace_id": workspace_id,
            "name": "Offline Sync Regression",
            "key": f"O{suffix[:3]}",
            "description": "",
        },
    )
    assert project.status_code == 201, project.text
    board = await api_client.get(
        f"/api/v1/projects/{project.json()['id']}/board",
        headers=headers,
    )
    assert board.status_code == 200, board.text
    task = await api_client.post(
        "/api/v1/tasks",
        headers=headers,
        json={
            "project_id": project.json()["id"],
            "column_id": board.json()["columns"][0]["id"],
            "title": "Initial offline task",
        },
    )
    assert task.status_code == 201, task.text
    return headers, task.json()


@pytest.mark.asyncio
async def test_task_update_replay_is_idempotent_and_audited_once(api_client):
    headers, task = await _create_task(api_client)
    mutation_id = uuid4().hex
    payload = {"version": 1, "title": "Updated from an offline draft"}

    first = await api_client.patch(
        f"/api/v1/tasks/{task['id']}",
        headers=_headers(headers["Authorization"].removeprefix("Bearer "), mutation_id),
        json=payload,
    )
    assert first.status_code == 200, first.text
    assert first.json()["version"] == 2

    replay = await api_client.patch(
        f"/api/v1/tasks/{task['id']}",
        headers=_headers(headers["Authorization"].removeprefix("Bearer "), mutation_id),
        json=payload,
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["version"] == 2
    assert replay.json()["title"] == payload["title"]

    activity = await api_client.get(
        f"/api/v1/tasks/{task['id']}/activity",
        headers=headers,
    )
    assert activity.status_code == 200, activity.text
    updates = [item for item in activity.json() if item["action"] == "task.updated"]
    assert len(updates) == 1
    assert "title changed" in updates[0]["summary"]
    assert "v1->2" in updates[0]["summary"]

    changed_payload = {"version": 1, "title": "Reusing a key for different content"}
    reused_key = await api_client.patch(
        f"/api/v1/tasks/{task['id']}",
        headers=_headers(headers["Authorization"].removeprefix("Bearer "), mutation_id),
        json=changed_payload,
    )
    assert reused_key.status_code == 409, reused_key.text


@pytest.mark.asyncio
async def test_comment_and_subtask_creation_replays_do_not_duplicate_records(api_client):
    headers, task = await _create_task(api_client)
    comment_key = uuid4().hex
    comment_payload = {"body": "This comment should be created exactly once."}

    first_comment = await api_client.post(
        f"/api/v1/tasks/{task['id']}/comments/rich",
        headers=_headers(headers["Authorization"].removeprefix("Bearer "), comment_key),
        json=comment_payload,
    )
    assert first_comment.status_code == 201, first_comment.text
    replay_comment = await api_client.post(
        f"/api/v1/tasks/{task['id']}/comments/rich",
        headers=_headers(headers["Authorization"].removeprefix("Bearer "), comment_key),
        json=comment_payload,
    )
    assert replay_comment.status_code == 201, replay_comment.text
    assert replay_comment.json()["id"] == first_comment.json()["id"]

    comments = await api_client.get(
        f"/api/v1/tasks/{task['id']}/comments",
        headers=headers,
    )
    assert comments.status_code == 200, comments.text
    assert len([item for item in comments.json() if item["body"] == comment_payload["body"]]) == 1

    subtask_key = uuid4().hex
    subtask_payload = {"title": "Persist this subtask once"}
    first_subtask = await api_client.post(
        f"/api/v1/tasks/{task['id']}/subtasks",
        headers=_headers(headers["Authorization"].removeprefix("Bearer "), subtask_key),
        json=subtask_payload,
    )
    assert first_subtask.status_code == 201, first_subtask.text
    replay_subtask = await api_client.post(
        f"/api/v1/tasks/{task['id']}/subtasks",
        headers=_headers(headers["Authorization"].removeprefix("Bearer "), subtask_key),
        json=subtask_payload,
    )
    assert replay_subtask.status_code == 201, replay_subtask.text
    assert replay_subtask.json()["id"] == first_subtask.json()["id"]

    subtasks = await api_client.get(f"/api/v1/tasks/{task['id']}/subtasks", headers=headers)
    assert subtasks.status_code == 200, subtasks.text
    assert len([item for item in subtasks.json() if item["title"] == subtask_payload["title"]]) == 1


@pytest.mark.asyncio
async def test_comment_key_cannot_be_reused_for_a_different_task(api_client):
    headers, task = await _create_task(api_client)
    second = await api_client.post(
        "/api/v1/tasks",
        headers=headers,
        json={
            "project_id": task["project_id"],
            "column_id": task["column_id"],
            "title": "Different task for key reuse",
        },
    )
    assert second.status_code == 201, second.text

    mutation_id = uuid4().hex
    first = await api_client.post(
        f"/api/v1/tasks/{task['id']}/comments/rich",
        headers={**headers, "Idempotency-Key": mutation_id},
        json={"body": "Original comment"},
    )
    assert first.status_code == 201, first.text

    reused = await api_client.post(
        f"/api/v1/tasks/{second.json()['id']}/comments/rich",
        headers={**headers, "Idempotency-Key": mutation_id},
        json={"body": "Original comment"},
    )
    assert reused.status_code == 409, reused.text

    second_comments = await api_client.get(
        f"/api/v1/tasks/{second.json()['id']}/comments",
        headers=headers,
    )
    assert second_comments.status_code == 200, second_comments.text
    assert second_comments.json() == []
