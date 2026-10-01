from uuid import uuid4

import pytest


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_board_column_management(api_client):
    suffix = uuid4().hex[:8]
    owner = await api_client.post(
        "/api/v1/auth/register",
        json={
            "email": f"columns-owner-{suffix}@example.com",
            "password": "Owner-password-123!",
            "name": "Columns Owner",
        },
    )
    assert owner.status_code == 201, owner.text
    token = owner.json()["access_token"]

    workspaces = await api_client.get("/api/v1/workspaces", headers=_headers(token))
    assert workspaces.status_code == 200
    workspace_id = workspaces.json()[0]["id"]

    project = await api_client.post(
        "/api/v1/projects",
        headers=_headers(token),
        json={
            "workspace_id": workspace_id,
            "name": "Board Columns",
            "key": f"C{suffix[:3]}",
        },
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]

    board = await api_client.get(
        f"/api/v1/projects/{project_id}/board",
        headers=_headers(token),
    )
    assert board.status_code == 200
    original_columns = board.json()["columns"]
    assert len(original_columns) == 5

    created = await api_client.post(
        f"/api/v1/projects/{project_id}/columns",
        headers=_headers(token),
        json={"name": "QA"},
    )
    assert created.status_code == 201, created.text
    qa = created.json()
    assert qa["name"] == "QA"
    assert qa["position"] == 5

    duplicate = await api_client.post(
        f"/api/v1/projects/{project_id}/columns",
        headers=_headers(token),
        json={"name": "qa"},
    )
    assert duplicate.status_code == 409

    renamed = await api_client.patch(
        f"/api/v1/projects/{project_id}/columns/{qa['id']}",
        headers=_headers(token),
        json={"name": "Quality"},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "Quality"

    desired = [qa["id"], *[column["id"] for column in original_columns]]
    reordered = await api_client.put(
        f"/api/v1/projects/{project_id}/columns/reorder",
        headers=_headers(token),
        json={"column_ids": desired},
    )
    assert reordered.status_code == 200, reordered.text
    assert [column["id"] for column in reordered.json()] == desired
    assert [column["position"] for column in reordered.json()] == list(range(6))

    invalid_order = await api_client.put(
        f"/api/v1/projects/{project_id}/columns/reorder",
        headers=_headers(token),
        json={"column_ids": desired[:-1]},
    )
    assert invalid_order.status_code == 422

    task = await api_client.post(
        "/api/v1/tasks",
        headers=_headers(token),
        json={
            "project_id": project_id,
            "column_id": qa["id"],
            "title": "Keep this task safe",
        },
    )
    assert task.status_code == 201, task.text

    blocked_delete = await api_client.delete(
        f"/api/v1/projects/{project_id}/columns/{qa['id']}",
        headers=_headers(token),
    )
    assert blocked_delete.status_code == 409

    destination_id = original_columns[0]["id"]
    deleted = await api_client.delete(
        f"/api/v1/projects/{project_id}/columns/{qa['id']}?move_to_column_id={destination_id}",
        headers=_headers(token),
    )
    assert deleted.status_code == 204, deleted.text

    moved_task = await api_client.get(
        f"/api/v1/tasks/{task.json()['id']}",
        headers=_headers(token),
    )
    assert moved_task.status_code == 200
    assert moved_task.json()["column_id"] == destination_id
    assert moved_task.json()["version"] == 2

    final_board = await api_client.get(
        f"/api/v1/projects/{project_id}/board",
        headers=_headers(token),
    )
    assert final_board.status_code == 200
    final_columns = final_board.json()["columns"]
    assert qa["id"] not in {column["id"] for column in final_columns}
    assert [column["position"] for column in final_columns] == list(range(5))
