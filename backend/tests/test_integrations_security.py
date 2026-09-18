import socket

import pytest

from app.api.routes.integrations import _events
from app.integration_security import (
    decrypt_secret,
    encrypt_secret,
    new_personal_token,
    new_webhook_secret,
    personal_token_digest,
    sign_webhook,
)
from app.webhook_delivery import event_matches
from app.webhook_security import validate_webhook_url


def test_personal_tokens_are_prefixed_and_digest_stable() -> None:
    token = new_personal_token()
    assert token.startswith("tp_pat_")
    assert personal_token_digest(token) == personal_token_digest(token)
    assert len(personal_token_digest(token)) == 64


def test_webhook_secret_round_trip_and_signature() -> None:
    secret = new_webhook_secret()
    encrypted = encrypt_secret(secret)
    assert encrypted != secret
    assert decrypt_secret(encrypted) == secret
    signature = sign_webhook(secret, 1234, b'{"event":"task.updated"}')
    assert signature.startswith("v1=")
    assert signature == sign_webhook(secret, 1234, b'{"event":"task.updated"}')
    assert signature != sign_webhook(secret, 1235, b'{"event":"task.updated"}')


def test_event_matching_supports_exact_and_prefix_wildcard() -> None:
    assert event_matches("task.*,comment.created", "task.updated")
    assert event_matches("task.*,comment.created", "comment.created")
    assert not event_matches("task.*,comment.created", "workspace.updated")
    assert event_matches("*", "anything.happened")


def test_event_validation_rejects_invalid_values() -> None:
    assert _events(["task.*", "task.*", "comment.created"]) == "task.*,comment.created"
    with pytest.raises(Exception):
        _events(["task updated"])


def test_webhook_url_rejects_private_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))],
    )
    with pytest.raises(ValueError, match="non-public"):
        validate_webhook_url("https://hooks.example.com/taskpilot", production=True)


def test_webhook_url_accepts_public_https(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))],
    )
    assert (
        validate_webhook_url("https://hooks.example.com/taskpilot", production=True)
        == "https://hooks.example.com/taskpilot"
    )


def test_production_webhook_requires_https(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))],
    )
    with pytest.raises(ValueError, match="HTTPS"):
        validate_webhook_url("http://hooks.example.com/taskpilot", production=True)
