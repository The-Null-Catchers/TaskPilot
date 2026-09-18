import json
import logging
import re

import pytest

from app import main
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



class _FakeDb:
    def __init__(self, *, fail: bool = False):
        self.fail = fail

    async def execute(self, _query):
        if self.fail:
            raise RuntimeError("postgres-password=must-not-leak")
        return None


class _FakeRedis:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.closed = False

    async def ping(self):
        if self.fail:
            raise RuntimeError("redis://secret@internal:6379")
        return True

    async def aclose(self):
        self.closed = True


@pytest.mark.asyncio
async def test_readiness_reports_database_failure_without_exception_details(monkeypatch):
    redis = _FakeRedis()
    monkeypatch.setattr(main.Redis, "from_url", lambda *_args, **_kwargs: redis)

    checks = await main._readiness_checks(_FakeDb(fail=True))

    assert checks == {"api": "ok", "database": "error", "redis": "ok"}
    assert redis.closed is True
    assert "password" not in str(checks).lower()


@pytest.mark.asyncio
async def test_readiness_reports_redis_failure_and_closes_client(monkeypatch):
    redis = _FakeRedis(fail=True)
    monkeypatch.setattr(main.Redis, "from_url", lambda *_args, **_kwargs: redis)

    checks = await main._readiness_checks(_FakeDb())

    assert checks == {"api": "ok", "database": "ok", "redis": "error"}
    assert redis.closed is True
    assert "internal" not in str(checks).lower()


@pytest.mark.asyncio
async def test_readiness_endpoint_returns_503_for_dependency_failure(api_client, monkeypatch):
    async def failing_readiness(_db):
        return {"api": "ok", "database": "error", "redis": "ok"}

    monkeypatch.setattr(main, "_readiness_checks", failing_readiness)
    response = await api_client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["error"]["detail"] == {
        "api": "ok",
        "database": "error",
        "redis": "ok",
    }
    assert "password" not in response.text.lower()
