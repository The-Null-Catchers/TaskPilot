import json
import logging
import re

import pytest

from app.core import config
from app.observability import JsonFormatter


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



def test_json_formatter_only_emits_allowlisted_context():
    record = logging.LogRecord(
        name="taskpilot.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request_complete",
        args=(),
        exc_info=None,
    )
    record.request_id = "request-123"
    record.method = "GET"
    record.route = "/api/v1/tasks/{task_id}"
    record.authorization = "Bearer must-not-be-logged"

    payload = json.loads(JsonFormatter().format(record))
    assert payload["request_id"] == "request-123"
    assert payload["method"] == "GET"
    assert payload["route"] == "/api/v1/tasks/{task_id}"
    assert "authorization" not in payload
    assert "must-not-be-logged" not in json.dumps(payload)


@pytest.mark.asyncio
async def test_metrics_are_opt_in_and_can_require_bearer_token(api_client, monkeypatch):
    monkeypatch.setattr(config.settings, "metrics_enabled", False)
    disabled = await api_client.get("/metrics")
    assert disabled.status_code == 404

    monkeypatch.setattr(config.settings, "metrics_enabled", True)
    monkeypatch.setattr(config.settings, "metrics_token", "metrics-test-secret")

    unauthorized = await api_client.get("/metrics")
    assert unauthorized.status_code == 401

    response = await api_client.get(
        "/metrics",
        headers={"Authorization": "Bearer metrics-test-secret"},
    )
    assert response.status_code == 200
    assert "taskpilot_http_requests_total" in response.text
    assert "taskpilot_http_request_duration_seconds" in response.text
