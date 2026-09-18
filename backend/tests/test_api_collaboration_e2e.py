from uuid import uuid4

import pytest


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_multi_user_workspace_collaboration_and_conflict(api_client):
    suffix = uuid4().hex[:10]
    owner_email = f"owner-{suffix}@example.com"
    member_email = f"member-{suffix}@example.com"

    owner_register = await api_client.post(
        "/api/v1/auth/register",
        json={"email": owner_email, "password": "Owner-password-123!", "name": "Owner User"},
    )
    assert owner_register.status_code == 201, owner_register.text
    owner_token = owner_register.json()["access_token"]

    owner_workspaces = await api_client.get(
        "/api/v1/workspaces",
        headers=_headers(owner_token),
    )
    assert owner_workspaces.status_code == 200, owner_workspaces.text
    workspace = owner_workspaces.json()[0]

    project_response = await api_client.post(
        "/api/v1/projects",
        headers=_headers(owner_token),
        json={
            "workspace_id": workspace["id"],
            "name": "Collaboration E2E",
            "key": f"E{suffix[:3]}",
            "description": "API integration test project",
        },
    )
    assert project_response.status_code == 201, project_response.text
    project = project_response.json()

    board_response = await api_client.get(
        f"/api/v1/projects/{project['id']}/board",
        headers=_headers(owner_token),
    )
    assert board_response.status_code == 200, board_response.text
    board = board_response.json()
    assert board["columns"]
    first_column = board["columns"][0]

    task_response = await api_client.post(
        "/api/v1/tasks",
        headers=_headers(owner_token),
        json={
            "project_id": project["id"],
            "column_id": first_column["id"],
            "title": "Protect collaboration boundaries",
            "description": "Created by the owner",
            "priority": "high",
        },
    )
    assert task_response.status_code == 201, task_response.text
    task = task_response.json()
    assert task["version"] == 1

    member_register = await api_client.post(
        "/api/v1/auth/register",
        json={"email": member_email, "password": "Member-password-123!", "name": "Member User"},
    )
    assert member_register.status_code == 201, member_register.text
    member_token = member_register.json()["access_token"]

    forbidden_board = await api_client.get(
        f"/api/v1/projects/{project['id']}/board",
        headers=_headers(member_token),
    )
    assert forbidden_board.status_code == 403

    invitation_response = await api_client.post(
        f"/api/v1/workspaces/{workspace['id']}/invitations",
        headers=_headers(owner_token),
        json={"email": member_email, "role": "member"},
    )
    assert invitation_response.status_code == 201, invitation_response.text
    invitation_token = invitation_response.json()["token"]

    accept_response = await api_client.post(
        f"/api/v1/workspaces/invitations/{invitation_token}/accept",
        headers=_headers(member_token),
    )
    assert accept_response.status_code == 200, accept_response.text

    allowed_board = await api_client.get(
        f"/api/v1/projects/{project['id']}/board",
        headers=_headers(member_token),
    )
    assert allowed_board.status_code == 200, allowed_board.text

    comment_response = await api_client.post(
        f"/api/v1/tasks/{task['id']}/comments",
        headers=_headers(member_token),
        json={"body": "Member can now collaborate safely."},
    )
    assert comment_response.status_code == 201, comment_response.text

    owner_comments = await api_client.get(
        f"/api/v1/tasks/{task['id']}/comments",
        headers=_headers(owner_token),
    )
    assert owner_comments.status_code == 200, owner_comments.text
    assert any(
        comment["body"] == "Member can now collaborate safely."
        for comment in owner_comments.json()
    )

    owner_update = await api_client.patch(
        f"/api/v1/tasks/{task['id']}",
        headers=_headers(owner_token),
        json={"version": 1, "title": "Owner won the first update"},
    )
    assert owner_update.status_code == 200, owner_update.text
    assert owner_update.json()["version"] == 2

    stale_member_update = await api_client.patch(
        f"/api/v1/tasks/{task['id']}",
        headers=_headers(member_token),
        json={"version": 1, "title": "Stale member update"},
    )
    assert stale_member_update.status_code == 409, stale_member_update.text
