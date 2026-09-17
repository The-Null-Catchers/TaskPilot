from pydantic import ValidationError
import pytest

from app.core import config
from app.notification_delivery import kind_allowed, send_push
from app.notification_models import NotificationPreference
from app.notification_schemas import NotificationPreferencePatch, PushSubscriptionCreate
from app.notification_security import decrypt_json, decrypt_text, encrypt_json, encrypt_text, target_digest


def preference(**values):
    return NotificationPreference(user_id=None, **values)


def test_kind_preferences_route_expected_events():
    pref = preference(
        assignments_enabled=False,
        mentions_enabled=True,
        comments_enabled=False,
        deadlines_enabled=True,
        dependencies_enabled=False,
    )
    assert not kind_allowed("task.assigned", pref)
    assert kind_allowed("task.mention", pref)
    assert not kind_allowed("comment.created", pref)
    assert kind_allowed("deadline_soon", pref)
    assert not kind_allowed("dependency.resolved", pref)
    assert kind_allowed("workspace.invited", pref)


def test_subscription_targets_are_encrypted_and_hashable(monkeypatch):
    monkeypatch.setattr(config.settings, "notification_secret", "test-notification-secret")
    target = "https://push.example.test/subscription/secret-token"
    encrypted = encrypt_text(target)
    assert encrypted != target
    assert decrypt_text(encrypted) == target
    assert target_digest(target) == target_digest(target)
    assert target_digest(target) != target_digest(target + "x")
    value = {"keys": {"p256dh": "public-key", "auth": "auth-secret"}}
    assert decrypt_json(encrypt_json(value)) == value


def test_notification_schema_rejects_unknown_delivery_modes():
    with pytest.raises(ValidationError):
        NotificationPreferencePatch(digest_frequency="weekly")
    with pytest.raises(ValidationError):
        PushSubscriptionCreate(channel="sms", target="12345678901")


def test_push_adapters_skip_cleanly_when_not_configured(monkeypatch):
    monkeypatch.setattr(config.settings, "webpush_vapid_private_key", None)
    monkeypatch.setattr(config.settings, "webpush_vapid_subject", None)
    monkeypatch.setattr(config.settings, "fcm_service_account_json", None)
    monkeypatch.setattr(config.settings, "apns_team_id", None)
    monkeypatch.setattr(config.settings, "apns_key_id", None)
    monkeypatch.setattr(config.settings, "apns_private_key", None)
    monkeypatch.setattr(config.settings, "apns_bundle_id", None)
    assert send_push("web_push", "https://push.example.test/token", {"keys": {}}, "A", "B", {}) == (
        "skipped",
        "webpush_not_configured",
    )
    assert send_push("fcm", "device-token", {}, "A", "B", {}) == (
        "skipped",
        "fcm_not_configured",
    )
    assert send_push("apns", "device-token", {}, "A", "B", {}) == (
        "skipped",
        "apns_not_configured",
    )
