import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app

WORKSPACE_ID = "00000000-0000-0000-0000-000000000001"


def test_websocket_rejects_disallowed_browser_origin():
    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            f"/api/v1/ws/workspaces/{WORKSPACE_ID}",
            headers={"origin": "https://attacker.example"},
        ):
            pass
    assert exc_info.value.code == 4403


def test_websocket_query_token_does_not_authenticate():
    client = TestClient(app)
    with client.websocket_connect(
        f"/api/v1/ws/workspaces/{WORKSPACE_ID}?token=legacy-query-token",
    ) as websocket:
        websocket.send_text("{}")
        with pytest.raises(WebSocketDisconnect) as exc_info:
            websocket.receive_text()
    assert exc_info.value.code == 4401


def test_websocket_requires_valid_first_auth_frame():
    client = TestClient(app)
    with client.websocket_connect(
        f"/api/v1/ws/workspaces/{WORKSPACE_ID}",
    ) as websocket:
        websocket.send_text('{"type":"auth","token":"not-a-jwt"}')
        with pytest.raises(WebSocketDisconnect) as exc_info:
            websocket.receive_text()
    assert exc_info.value.code == 4401
