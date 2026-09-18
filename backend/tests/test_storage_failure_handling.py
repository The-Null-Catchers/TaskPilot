import io

import pytest
from PIL import Image

from app.api.routes import attachments


async def _project_fixture(api_client, suffix: str):
    register = await api_client.post(
        "/api/v1/auth/register",
        json={
            "email": f"storage-{suffix}@example.com",
            "password": "TaskPilot-storage-test!",
            "name": f"Storage {suffix}",
        },
    )
    assert register.status_code == 201, register.text
    token = register.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    workspaces = await api_client.get("/api/v1/workspaces", headers=headers)
    assert workspaces.status_code == 200, workspaces.text
    workspace_id = workspaces.json()[0]["id"]

    project = await api_client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "workspace_id": workspace_id,
            "name": f"Storage Project {suffix}",
            "key": f"S{suffix[-4:]}".replace("-", "A"),
            "description": "",
        },
    )
    assert project.status_code == 201, project.text
    return headers, workspace_id, project.json()["id"]


@pytest.mark.asyncio
async def test_attachment_upload_storage_failure_returns_generic_503_and_cleans_up(
    api_client, monkeypatch
):
    headers, _, project_id = await _project_fixture(api_client, "upload-failure")
    cleanup_calls = []

    async def fail_put(*_args, **_kwargs):
        raise RuntimeError("s3.internal.example secret-key=do-not-leak")

    async def cleanup(*keys):
        cleanup_calls.append(keys)

    monkeypatch.setattr(attachments, "put_bytes", fail_put)
    monkeypatch.setattr(attachments, "delete_keys", cleanup)

    response = await api_client.post(
        "/api/v1/attachments",
        headers=headers,
        data={"entity_type": "project", "entity_id": project_id},
        files={"file": ("notes.txt", b"safe text attachment", "text/plain")},
    )

    assert response.status_code == 503, response.text
    assert response.json()["error"]["message"] == "Attachment storage is unavailable"
    assert "s3.internal.example" not in response.text
    assert "secret-key" not in response.text
    assert len(cleanup_calls) == 1

    listing = await api_client.get(
        "/api/v1/attachments",
        headers=headers,
        params={"entity_type": "project", "entity_id": project_id},
    )
    assert listing.status_code == 200, listing.text
    assert listing.json() == []


@pytest.mark.asyncio
async def test_partial_thumbnail_upload_cleans_original_and_thumbnail_keys(
    api_client, monkeypatch
):
    headers, _, project_id = await _project_fixture(api_client, "partial-image")
    put_calls = []
    cleanup_calls = []

    async def scripted_put(key, _data, _mime):
        put_calls.append(key)
        if len(put_calls) == 2:
            raise RuntimeError("thumbnail storage failed")

    async def cleanup(*keys):
        cleanup_calls.append(keys)

    monkeypatch.setattr(attachments, "put_bytes", scripted_put)
    monkeypatch.setattr(attachments, "delete_keys", cleanup)

    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(buffer, format="PNG")

    response = await api_client.post(
        "/api/v1/attachments",
        headers=headers,
        data={"entity_type": "project", "entity_id": project_id},
        files={"file": ("image.png", buffer.getvalue(), "image/png")},
    )

    assert response.status_code == 503, response.text
    assert len(put_calls) == 2
    assert len(cleanup_calls) == 1
    original_key, thumbnail_key = cleanup_calls[0]
    assert original_key == put_calls[0]
    assert thumbnail_key == put_calls[1]
    assert original_key.endswith("/original.png")
    assert thumbnail_key.endswith("/thumbnail.jpg")


@pytest.mark.asyncio
async def test_download_presign_failure_is_generic_and_keeps_attachment(
    api_client, monkeypatch
):
    headers, _, project_id = await _project_fixture(api_client, "download-failure")

    async def store_ok(*_args, **_kwargs):
        return None

    async def fail_presign(*_args, **_kwargs):
        raise RuntimeError("minio-root-password=do-not-leak")

    monkeypatch.setattr(attachments, "put_bytes", store_ok)

    uploaded = await api_client.post(
        "/api/v1/attachments",
        headers=headers,
        data={"entity_type": "project", "entity_id": project_id},
        files={"file": ("notes.txt", b"download test", "text/plain")},
    )
    assert uploaded.status_code == 201, uploaded.text
    attachment_id = uploaded.json()["id"]

    monkeypatch.setattr(attachments, "presigned_download_url", fail_presign)
    response = await api_client.get(
        f"/api/v1/attachments/{attachment_id}/download",
        headers=headers,
    )

    assert response.status_code == 503, response.text
    assert response.json()["error"]["message"] == "Attachment storage is unavailable"
    assert "minio-root-password" not in response.text

    listing = await api_client.get(
        "/api/v1/attachments",
        headers=headers,
        params={"entity_type": "project", "entity_id": project_id},
    )
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()] == [attachment_id]


@pytest.mark.asyncio
async def test_delete_storage_failure_preserves_database_metadata(
    api_client, monkeypatch
):
    headers, _, project_id = await _project_fixture(api_client, "delete-failure")

    async def store_ok(*_args, **_kwargs):
        return None

    async def delete_failure(*_args, **_kwargs):
        raise RuntimeError("object-store unavailable")

    monkeypatch.setattr(attachments, "put_bytes", store_ok)

    uploaded = await api_client.post(
        "/api/v1/attachments",
        headers=headers,
        data={"entity_type": "project", "entity_id": project_id},
        files={"file": ("keep.txt", b"keep metadata", "text/plain")},
    )
    assert uploaded.status_code == 201, uploaded.text
    attachment_id = uploaded.json()["id"]

    monkeypatch.setattr(attachments, "delete_keys", delete_failure)
    response = await api_client.delete(
        f"/api/v1/attachments/{attachment_id}",
        headers=headers,
    )

    assert response.status_code == 503, response.text
    assert response.json()["error"]["message"] == "Attachment storage is unavailable"

    listing = await api_client.get(
        "/api/v1/attachments",
        headers=headers,
        params={"entity_type": "project", "entity_id": project_id},
    )
    assert listing.status_code == 200, listing.text
    assert [item["id"] for item in listing.json()] == [attachment_id]
