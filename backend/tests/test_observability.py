import re

import pytest


@pytest.mark.asyncio
async def test_liveness_and_request_id(api_client):
    response = await api_client.get(
        "/health/live",
        headers={"x-request-id": "edge-request-123"},
    )
    assert response.status_code == 200
    assert response.json() == {"api": "ok"}
    assert response.headers["x-request-id"] == "edge-request-123"


@pytest.mark.asyncio
async def test_invalid_request_id_is_replaced(api_client):
    response = await api_client.get(
        "/health/live",
        headers={"x-request-id": "bad request id with spaces"},
    )
    assert response.status_code == 200
    generated = response.headers["x-request-id"]
    assert generated != "bad request id with spaces"
    assert re.fullmatch(r"[0-9a-f]{32}", generated)


@pytest.mark.asyncio
async def test_readiness_checks_database_and_redis(api_client):
    response = await api_client.get("/health/ready")
    assert response.status_code == 200, response.text
    assert response.json() == {
        "api": "ok",
        "database": "ok",
        "redis": "ok",
    }
