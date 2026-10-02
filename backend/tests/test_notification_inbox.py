from uuid import uuid4

import pytest


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_user_can_delete_own_notification(api_client):
    suffix = uuid4().hex[:8]
    owner = await api_client.post(
        "/api/v1/auth/register",
        json={
            "email": f"notify-owner-{suffix}@example.com",
            "password": "Owner-password-123!",
            "name": "Notification Owner",
        },
    )
    assert owner.status_code == 201, owner.text
    owner_token = owner.json()["access_token"]

    teammate = await api_client.post(
        "/api/v1/auth/register",
        json={
            "email": f"notify-member-{suffix}@example.com",
            "password": "Member-password-123!",
            "name": "Notification Member",
        },
    )
    assert teammate.status_code == 201, teammate.text
    teammate_token = teammate.json()["access_token"]
    teammate_user = teammate.json()["user"]

    workspaces = await api_client.get(
        "/api/v1/workspaces",
        headers=_headers(owner_token),
    )
    workspace_id = workspaces.json()[0]["id"]

    invitation = await api_client.post(
        f"/api/v1/workspaces/{workspace_id}/invitations",
        headers=_headers(owner_token),
        json={"email": teammate_user["email"], "role": "member"},
    )
    assert invitation.status_code == 201, invitation.text
    invitation_token = invitation.json()["token"]

    accepted = await api_client.post(
        f"/api/v1/workspaces/invitations/{invitation_token}/accept",
        headers=_headers(teammate_token),
    )
    assert accepted.status_code == 200, accepted.text

    project = await api_client.post(
        "/api/v1/projects",
        headers=_headers(owner_token),
        json={
            "workspace_id": workspace_id,
            "name": "Notification Project",
            "key": f"N{suffix[:3]}",
        },
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]

    board = await api_client.get(
        f"/api/v1/projects/{project_id}/board",
        headers=_headers(owner_token),
    )
    assert board.status_code == 200, board.text

    task = await api_client.post(
        "/api/v1/tasks",
        headers=_headers(owner_token),
        json={
            "project_id": project_id,
            "column_id": board.json()["columns"][0]["id"],
            "title": "Generate assignment notification",
        },
    )
    assert task.status_code == 201, task.text

    assigned = await api_client.post(
        f"/api/v1/tasks/{task.json()['id']}/assignees",
        headers=_headers(owner_token),
        json={"user_id": teammate_user["id"]},
    )
    assert assigned.status_code == 200, assigned.text

    inbox = await api_client.get(
        "/api/v1/notifications",
        headers=_headers(teammate_token),
    )
    assert inbox.status_code == 200, inbox.text
    assert len(inbox.json()) == 1
    notification_id = inbox.json()[0]["id"]

    forbidden = await api_client.delete(
        f"/api/v1/notifications/{notification_id}",
        headers=_headers(owner_token),
    )
    assert forbidden.status_code == 404

    deleted = await api_client.delete(
        f"/api/v1/notifications/{notification_id}",
        headers=_headers(teammate_token),
    )
    assert deleted.status_code == 204, deleted.text

    empty = await api_client.get(
        "/api/v1/notifications",
        headers=_headers(teammate_token),
    )
    assert empty.status_code == 200
    assert empty.json() == []
