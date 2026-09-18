import pytest

from app.api.routes import attachments


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _register(api_client, email: str, name: str, password: str = "TaskPilot-security-2026!"):
    response = await api_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "name": name},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_refresh_token_rotation_is_one_time(api_client):
    email = "rotation-security@example.com"
    password = "TaskPilot-security-2026!"
    await _register(api_client, email, "Rotation User", password)

    login = await api_client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": password,
            "client": "mobile",
            "device_name": "Security test device",
        },
    )
    assert login.status_code == 200, login.text
    old_refresh = login.json()["refresh_token"]
    assert old_refresh

    rotated = await api_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh, "client": "mobile"},
    )
    assert rotated.status_code == 200, rotated.text
    new_refresh = rotated.json()["refresh_token"]
    assert new_refresh and new_refresh != old_refresh

    replay = await api_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh, "client": "mobile"},
    )
    assert replay.status_code == 401, replay.text

    successor = await api_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": new_refresh, "client": "mobile"},
    )
    assert successor.status_code == 200, successor.text


@pytest.mark.asyncio
async def test_password_reset_revokes_existing_refresh_sessions(api_client):
    email = "reset-security@example.com"
    old_password = "TaskPilot-security-2026!"
    new_password = "TaskPilot-new-security-2026!"
    await _register(api_client, email, "Reset User", old_password)

    mobile_login = await api_client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": old_password,
            "client": "mobile",
            "device_name": "Before password reset",
        },
    )
    assert mobile_login.status_code == 200, mobile_login.text
    refresh_token = mobile_login.json()["refresh_token"]

    forgot = await api_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": email},
    )
    assert forgot.status_code == 202, forgot.text
    reset_token = forgot.json().get("development_token")
    assert reset_token, "Development test environment must expose its one-time reset token"

    reset = await api_client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "password": new_password},
    )
    assert reset.status_code == 204, reset.text

    stale_refresh = await api_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token, "client": "mobile"},
    )
    assert stale_refresh.status_code == 401, stale_refresh.text

    old_login = await api_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": old_password, "client": "mobile"},
    )
    assert old_login.status_code == 401, old_login.text

    new_login = await api_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": new_password, "client": "mobile"},
    )
    assert new_login.status_code == 200, new_login.text


@pytest.mark.asyncio
async def test_personal_api_token_read_scope_cannot_write(api_client):
    auth = await _register(
        api_client,
        "pat-security@example.com",
        "PAT Security User",
    )
    session_headers = _headers(auth["access_token"])

    read_token_response = await api_client.post(
        "/api/v1/integrations/tokens",
        headers=session_headers,
        json={"name": "Read only CI token", "scopes": ["read"]},
    )
    assert read_token_response.status_code == 201, read_token_response.text
    read_pat = read_token_response.json()["token"]
    read_headers = _headers(read_pat)

    readable = await api_client.get("/api/v1/workspaces", headers=read_headers)
    assert readable.status_code == 200, readable.text

    forbidden_write = await api_client.post(
        "/api/v1/workspaces",
        headers=read_headers,
        json={"name": "PAT must not create this"},
    )
    assert forbidden_write.status_code == 403, forbidden_write.text
    assert "write scope" in forbidden_write.text.lower()

    write_token_response = await api_client.post(
        "/api/v1/integrations/tokens",
        headers=session_headers,
        json={"name": "Read-write CI token", "scopes": ["read", "write"]},
    )
    assert write_token_response.status_code == 201, write_token_response.text
    write_headers = _headers(write_token_response.json()["token"])

    allowed_write = await api_client.post(
        "/api/v1/workspaces",
        headers=write_headers,
        json={"name": "Created through scoped PAT"},
    )
    assert allowed_write.status_code == 201, allowed_write.text


@pytest.mark.asyncio
async def test_attachment_idor_is_blocked_across_workspaces(api_client, monkeypatch):
    owner = await _register(
        api_client,
        "attachment-owner-security@example.com",
        "Attachment Owner",
    )
    outsider = await _register(
        api_client,
        "attachment-outsider-security@example.com",
        "Attachment Outsider",
    )
    owner_headers = _headers(owner["access_token"])
    outsider_headers = _headers(outsider["access_token"])

    workspaces = await api_client.get("/api/v1/workspaces", headers=owner_headers)
    assert workspaces.status_code == 200, workspaces.text
    workspace_id = workspaces.json()[0]["id"]

    project = await api_client.post(
        "/api/v1/projects",
        headers=owner_headers,
        json={
            "workspace_id": workspace_id,
            "name": "Private Security Project",
            "key": "SEC",
            "description": "",
        },
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]

    async def store_ok(*_args, **_kwargs):
        return None

    async def fake_presign(*_args, **_kwargs):
        return "https://storage.example.test/should-not-be-issued"

    monkeypatch.setattr(attachments, "put_bytes", store_ok)
    monkeypatch.setattr(attachments, "presigned_download_url", fake_presign)

    upload = await api_client.post(
        "/api/v1/attachments",
        headers=owner_headers,
        data={"entity_type": "project", "entity_id": project_id},
        files={"file": ("private.txt", b"private workspace content", "text/plain")},
    )
    assert upload.status_code == 201, upload.text
    attachment_id = upload.json()["id"]

    outsider_list = await api_client.get(
        "/api/v1/attachments",
        headers=outsider_headers,
        params={"entity_type": "project", "entity_id": project_id},
    )
    assert outsider_list.status_code == 403, outsider_list.text

    outsider_download = await api_client.get(
        f"/api/v1/attachments/{attachment_id}/download",
        headers=outsider_headers,
    )
    assert outsider_download.status_code == 403, outsider_download.text
    assert "storage.example.test" not in outsider_download.text

    owner_download = await api_client.get(
        f"/api/v1/attachments/{attachment_id}/download",
        headers=owner_headers,
    )
    assert owner_download.status_code == 200, owner_download.text
    assert owner_download.json()["url"] == "https://storage.example.test/should-not-be-issued"
