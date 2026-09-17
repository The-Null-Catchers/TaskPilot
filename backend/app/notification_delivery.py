import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import jwt
from pywebpush import WebPushException, webpush

from app.core.config import settings
from app.email_delivery import send_email
from app.notification_models import NotificationPreference


def kind_allowed(kind: str, preference: NotificationPreference) -> bool:
    normalized = kind.lower()
    if "assign" in normalized:
        return preference.assignments_enabled
    if "mention" in normalized:
        return preference.mentions_enabled
    if "comment" in normalized:
        return preference.comments_enabled
    if "deadline" in normalized or "due" in normalized:
        return preference.deadlines_enabled
    if "depend" in normalized or "block" in normalized:
        return preference.dependencies_enabled
    return True


def notification_link(entity_type: str | None, entity_id: Any | None) -> str:
    base = settings.app_url.rstrip("/")
    if entity_type == "task" and entity_id:
        return f"{base}/app/tasks/{entity_id}"
    return f"{base}/app/notifications"


def send_notification_email(recipient: str, title: str, body: str, link: str) -> tuple[str, str | None]:
    text = f"{title}\n\n{body}\n\nOpen TaskPilot: {link}".strip()
    try:
        if not send_email(recipient, title, text):
            return "skipped", "smtp_not_configured"
        return "sent", None
    except Exception as exc:
        return "failed", type(exc).__name__


def _web_push(target: str, config: dict, title: str, body: str, data: dict) -> tuple[str, str | None]:
    if not settings.webpush_vapid_private_key or not settings.webpush_vapid_subject:
        return "skipped", "webpush_not_configured"
    keys = config.get("keys") if isinstance(config.get("keys"), dict) else {}
    if not keys.get("p256dh") or not keys.get("auth"):
        return "failed", "webpush_keys_missing"
    payload = json.dumps({"title": title, "body": body, "data": data}, separators=(",", ":"))
    try:
        webpush(
            subscription_info={"endpoint": target, "keys": keys},
            data=payload,
            vapid_private_key=settings.webpush_vapid_private_key,
            vapid_claims={"sub": settings.webpush_vapid_subject},
            ttl=300,
        )
        return "sent", None
    except WebPushException as exc:
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
        if status_code in {404, 410}:
            return "failed", "subscription_gone"
        return "failed", f"webpush_{status_code or 'error'}"
    except Exception as exc:
        return "failed", type(exc).__name__


def _fcm_access_token(service_account: dict) -> str:
    now = datetime.now(UTC)
    token_uri = service_account.get("token_uri") or "https://oauth2.googleapis.com/token"
    assertion = jwt.encode(
        {
            "iss": service_account["client_email"],
            "scope": "https://www.googleapis.com/auth/firebase.messaging",
            "aud": token_uri,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=55)).timestamp()),
        },
        service_account["private_key"],
        algorithm="RS256",
    )
    response = httpx.post(
        token_uri,
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        },
        timeout=15,
    )
    response.raise_for_status()
    return str(response.json()["access_token"])


def _fcm(target: str, title: str, body: str, data: dict) -> tuple[str, str | None]:
    if not settings.fcm_service_account_json:
        return "skipped", "fcm_not_configured"
    try:
        service_account = json.loads(settings.fcm_service_account_json)
        project_id = service_account["project_id"]
        access_token = _fcm_access_token(service_account)
        response = httpx.post(
            f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "message": {
                    "token": target,
                    "notification": {"title": title, "body": body},
                    "data": {str(key): str(value) for key, value in data.items() if value is not None},
                }
            },
            timeout=15,
        )
        if response.status_code in {404, 410}:
            return "failed", "subscription_gone"
        response.raise_for_status()
        return "sent", None
    except (KeyError, ValueError, jwt.PyJWTError):
        return "failed", "fcm_configuration_invalid"
    except httpx.HTTPStatusError as exc:
        return "failed", f"fcm_http_{exc.response.status_code}"
    except Exception as exc:
        return "failed", type(exc).__name__


def _apns(target: str, title: str, body: str, data: dict) -> tuple[str, str | None]:
    required = (
        settings.apns_team_id,
        settings.apns_key_id,
        settings.apns_private_key,
        settings.apns_bundle_id,
    )
    if not all(required):
        return "skipped", "apns_not_configured"
    try:
        provider_token = jwt.encode(
            {"iss": settings.apns_team_id, "iat": int(datetime.now(UTC).timestamp())},
            settings.apns_private_key,
            algorithm="ES256",
            headers={"kid": settings.apns_key_id},
        )
        host = "https://api.sandbox.push.apple.com" if settings.apns_use_sandbox else "https://api.push.apple.com"
        payload = {
            "aps": {"alert": {"title": title, "body": body}, "sound": "default"},
            "taskpilot": data,
        }
        with httpx.Client(http2=True, timeout=15) as client:
            response = client.post(
                f"{host}/3/device/{target}",
                headers={
                    "authorization": f"bearer {provider_token}",
                    "apns-topic": str(settings.apns_bundle_id),
                    "apns-push-type": "alert",
                    "apns-priority": "10",
                },
                json=payload,
            )
        if response.status_code in {404, 410}:
            return "failed", "subscription_gone"
        if response.status_code != 200:
            return "failed", f"apns_http_{response.status_code}"
        return "sent", None
    except (ValueError, jwt.PyJWTError):
        return "failed", "apns_configuration_invalid"
    except Exception as exc:
        return "failed", type(exc).__name__


def send_push(
    channel: str,
    target: str,
    config: dict,
    title: str,
    body: str,
    data: dict,
) -> tuple[str, str | None]:
    if channel == "web_push":
        return _web_push(target, config, title, body, data)
    if channel == "fcm":
        return _fcm(target, title, body, data)
    if channel == "apns":
        return _apns(target, title, body, data)
    return "failed", "unsupported_push_channel"
