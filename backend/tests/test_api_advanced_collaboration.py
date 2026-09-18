from uuid import uuid4

import pytest


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_advanced_task_collaboration_flows(api_client):
    suffix = uuid4().hex[:10]
    owner_email = f"owner-advanced-{suffix}@example.com"
    member_email = f"member-advanced-{suffix}@example.com"

    owner_register = await api_client.post(
        "/api/v1/auth/register",
        json={"email": owner_email, "password": "Owner-password-123!", "name": "Owner User"},
    )
    assert owner_register.status_code == 201, owner_register.text
    owner_token = owner_register.json()["access_token"]

    owner_workspaces = await api_client.get("/api/v1/workspaces", headers=_headers(owner_token))
    assert owner_workspaces.status_code == 200, owner_workspaces.text
    workspace = owner_workspaces.json()[0]

    project_response = await api_client.post(
        "/api/v1/projects",
        headers=_headers(owner_token),
        json={
            "workspace_id": workspace["id"],
            "name": "Advanced Collaboration",
            "key": f"A{suffix[:3]}",
            "description": "Advanced API collaboration coverage",
        },
    )
    assert project_response.status_code == 201, project_response.text
    project = project_response.json()

    board_response = await api_client.get(
        f"/api/v1/projects/{project['id']}/board",
        headers=_headers(owner_token),
    )
    assert board_response.status_code == 200, board_response.text
    column_id = board_response.json()["columns"][0]["id"]

    async def create_task(title: str):
        response = await api_client.post(
            "/api/v1/tasks",
            headers=_headers(owner_token),
            json={
                "project_id": project["id"],
                "column_id": column_id,
                "title": title,
                "priority": "medium",
            },
        )
        assert response.status_code == 201, response.text
        return response.json()

    blocker = await create_task("Finish backend contract")
    blocked = await create_task("Ship dependent UI")

    member_register = await api_client.post(
        "/api/v1/auth/register",
        json={"email": member_email, "password": "Member-password-123!", "name": "Member User"},
    )
    assert member_register.status_code == 201, member_register.text
    member_token = member_register.json()["access_token"]

    member_me = await api_client.get("/api/v1/auth/me", headers=_headers(member_token))
    assert member_me.status_code == 200, member_me.text
    member_id = member_me.json()["id"]

    invitation_response = await api_client.post(
        f"/api/v1/workspaces/{workspace['id']}/invitations",
        headers=_headers(owner_token),
        json={"email": member_email, "role": "member"},
    )
    assert invitation_response.status_code == 201, invitation_response.text
    invitation_payload = invitation_response.json()
    assert invitation_payload["delivery_status"] == "pending"
    assert invitation_payload["delivered_at"] is None
    assert invitation_payload["token"]

    active_invitations = await api_client.get(
        f"/api/v1/workspaces/{workspace['id']}/invitations",
        headers=_headers(owner_token),
    )
    assert active_invitations.status_code == 200, active_invitations.text
    listed_invitation = next(
        item for item in active_invitations.json() if item["id"] == invitation_payload["id"]
    )
    assert listed_invitation["delivery_status"] == "pending"
    assert "token" not in listed_invitation

    accept_response = await api_client.post(
        f"/api/v1/workspaces/invitations/{invitation_response.json()['token']}/accept",
        headers=_headers(member_token),
    )
    assert accept_response.status_code == 200, accept_response.text

    assign_response = await api_client.post(
        f"/api/v1/tasks/{blocked['id']}/assignees",
        headers=_headers(owner_token),
        json={"user_id": member_id},
    )
    assert assign_response.status_code == 200, assign_response.text
    assert assign_response.json()["id"] == member_id

    watch_response = await api_client.post(
        f"/api/v1/tasks/{blocked['id']}/watch",
        headers=_headers(member_token),
    )
    assert watch_response.status_code == 204, watch_response.text

    watchers = await api_client.get(
        f"/api/v1/tasks/{blocked['id']}/watchers",
        headers=_headers(owner_token),
    )
    assert watchers.status_code == 200, watchers.text
    assert any(item["id"] == member_id for item in watchers.json())

    dependency = await api_client.post(
        f"/api/v1/tasks/{blocked['id']}/dependencies",
        headers=_headers(owner_token),
        json={"blocker_task_id": blocker["id"]},
    )
    assert dependency.status_code == 201, dependency.text
    dependency_id = dependency.json()["id"]

    collaboration_state = await api_client.get(
        f"/api/v1/tasks/{blocked['id']}/collaboration-state",
        headers=_headers(member_token),
    )
    assert collaboration_state.status_code == 200, collaboration_state.text
    assert collaboration_state.json()["blocked"] is True
    assert blocker["id"] in collaboration_state.json()["blocking_task_ids"]
    assert collaboration_state.json()["watching"] is True

    circular = await api_client.post(
        f"/api/v1/tasks/{blocker['id']}/dependencies",
        headers=_headers(owner_token),
        json={"blocker_task_id": blocked["id"]},
    )
    assert circular.status_code == 409, circular.text

    owner_comment = await api_client.post(
        f"/api/v1/tasks/{blocked['id']}/comments",
        headers=_headers(owner_token),
        json={"body": "Watcher should receive this update."},
    )
    assert owner_comment.status_code == 201, owner_comment.text

    member_notifications = await api_client.get(
        "/api/v1/notifications",
        headers=_headers(member_token),
    )
    assert member_notifications.status_code == 200, member_notifications.text
    assert any(item["kind"] == "task.comment" for item in member_notifications.json())

    member_comment = await api_client.post(
        f"/api/v1/tasks/{blocked['id']}/comments",
        headers=_headers(member_token),
        json={"body": "Initial member comment"},
    )
    assert member_comment.status_code == 201, member_comment.text
    member_comment_id = member_comment.json()["id"]

    edited = await api_client.patch(
        f"/api/v1/tasks/{blocked['id']}/comments/{member_comment_id}",
        headers=_headers(member_token),
        json={"body": "Edited member comment"},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["body"] == "Edited member comment"
    assert edited.json()["edited_at"] is not None

    forbidden_edit = await api_client.patch(
        f"/api/v1/tasks/{blocked['id']}/comments/{member_comment_id}",
        headers=_headers(owner_token),
        json={"body": "Owner must not overwrite member comment"},
    )
    assert forbidden_edit.status_code == 403, forbidden_edit.text

    reaction = await api_client.post(
        f"/api/v1/tasks/{blocked['id']}/comments/{member_comment_id}/reactions",
        headers=_headers(owner_token),
        json={"emoji": "👍"},
    )
    assert reaction.status_code == 201, reaction.text
    reaction_id = reaction.json()["id"]

    listed_reactions = await api_client.get(
        f"/api/v1/tasks/{blocked['id']}/comments/{member_comment_id}/reactions",
        headers=_headers(member_token),
    )
    assert listed_reactions.status_code == 200, listed_reactions.text
    assert any(item["id"] == reaction_id and item["emoji"] == "👍" for item in listed_reactions.json())

    bad_reaction = await api_client.post(
        f"/api/v1/tasks/{blocked['id']}/comments/{member_comment_id}/reactions",
        headers=_headers(owner_token),
        json={"emoji": "<script>"},
    )
    assert bad_reaction.status_code == 400, bad_reaction.text

    delete_reaction = await api_client.delete(
        f"/api/v1/tasks/{blocked['id']}/comments/{member_comment_id}/reactions/{reaction_id}",
        headers=_headers(owner_token),
    )
    assert delete_reaction.status_code == 204, delete_reaction.text

    complete_blocker = await api_client.patch(
        f"/api/v1/tasks/{blocker['id']}",
        headers=_headers(owner_token),
        json={"version": blocker["version"], "status": "done"},
    )
    assert complete_blocker.status_code == 200, complete_blocker.text

    member_notifications = await api_client.get(
        "/api/v1/notifications",
        headers=_headers(member_token),
    )
    assert member_notifications.status_code == 200, member_notifications.text
    assert any(item["kind"] == "dependency.resolved" for item in member_notifications.json())

    remove_dependency = await api_client.delete(
        f"/api/v1/tasks/{blocked['id']}/dependencies/{dependency_id}",
        headers=_headers(owner_token),
    )
    assert remove_dependency.status_code == 204, remove_dependency.text

    unwatch_response = await api_client.delete(
        f"/api/v1/tasks/{blocked['id']}/watch",
        headers=_headers(member_token),
    )
    assert unwatch_response.status_code == 204, unwatch_response.text

    forbidden_delete = await api_client.delete(
        f"/api/v1/tasks/{blocked['id']}/comments/{member_comment_id}",
        headers=_headers(owner_token),
    )
    assert forbidden_delete.status_code == 403, forbidden_delete.text

    own_delete = await api_client.delete(
        f"/api/v1/tasks/{blocked['id']}/comments/{member_comment_id}",
        headers=_headers(member_token),
    )
    assert own_delete.status_code == 204, own_delete.text

    final_state = await api_client.get(
        f"/api/v1/tasks/{blocked['id']}/collaboration-state",
        headers=_headers(member_token),
    )
    assert final_state.status_code == 200, final_state.text
    assert final_state.json()["blocked"] is False
    assert final_state.json()["watching"] is False

    archive_response = await api_client.post(
        f"/api/v1/tasks/{blocked['id']}/archive",
        headers=_headers(owner_token),
    )
    assert archive_response.status_code == 200, archive_response.text

    hidden_task = await api_client.get(
        f"/api/v1/tasks/{blocked['id']}",
        headers=_headers(owner_token),
    )
    assert hidden_task.status_code == 404, hidden_task.text

    archived_tasks = await api_client.get(
        f"/api/v1/workspaces/{workspace['id']}/archived-tasks",
        headers=_headers(owner_token),
    )
    assert archived_tasks.status_code == 200, archived_tasks.text
    assert any(item["id"] == blocked["id"] for item in archived_tasks.json())

    member_archived_tasks = await api_client.get(
        f"/api/v1/workspaces/{workspace['id']}/archived-tasks?project_id={project['id']}",
        headers=_headers(member_token),
    )
    assert member_archived_tasks.status_code == 200, member_archived_tasks.text
    assert any(item["id"] == blocked["id"] for item in member_archived_tasks.json())

    restore_response = await api_client.post(
        f"/api/v1/tasks/{blocked['id']}/restore",
        headers=_headers(owner_token),
    )
    assert restore_response.status_code == 200, restore_response.text

    restored_task = await api_client.get(
        f"/api/v1/tasks/{blocked['id']}",
        headers=_headers(owner_token),
    )
    assert restored_task.status_code == 200, restored_task.text

    archive_after_restore = await api_client.get(
        f"/api/v1/workspaces/{workspace['id']}/archived-tasks",
        headers=_headers(owner_token),
    )
    assert archive_after_restore.status_code == 200, archive_after_restore.text
    assert all(item["id"] != blocked["id"] for item in archive_after_restore.json())
