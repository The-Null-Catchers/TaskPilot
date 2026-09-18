import json
import logging
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import exists, or_, select

from app.core.config import settings
from app.db import SessionLocal
from app.integration_models import WebhookDelivery, WorkspaceWebhook
from app.integration_security import decrypt_secret, sign_webhook
from app.models import ActivityLog
from app.webhook_security import validate_webhook_url

logger = logging.getLogger("taskpilot.webhooks")


def event_matches(configured: str, event: str) -> bool:
    for pattern in configured.split(","):
        pattern = pattern.strip()
        if pattern == "*" or pattern == event:
            return True
        if pattern.endswith("*") and event.startswith(pattern[:-1]):
            return True
    return False


async def queue_webhook_deliveries(limit: int = 500) -> int:
    created = 0
    async with SessionLocal() as db:
        hooks = list(
            (
                await db.scalars(
                    select(WorkspaceWebhook).where(WorkspaceWebhook.active.is_(True))
                )
            ).all()
        )
        for hook in hooks:
            activities = list(
                (
                    await db.scalars(
                        select(ActivityLog)
                        .where(
                            ActivityLog.workspace_id == hook.workspace_id,
                            ActivityLog.created_at >= hook.created_at,
                            ~exists(
                                select(WebhookDelivery.id).where(
                                    WebhookDelivery.webhook_id == hook.id,
                                    WebhookDelivery.activity_id == ActivityLog.id,
                                )
                            ),
                        )
                        .order_by(ActivityLog.created_at)
                        .limit(limit)
                    )
                ).all()
            )
            for activity in activities:
                matched = event_matches(hook.events, activity.action)
                db.add(
                    WebhookDelivery(
                        webhook_id=hook.id,
                        activity_id=activity.id,
                        event=activity.action,
                        status="pending" if matched else "skipped",
                        last_error=None if matched else "event_not_subscribed",
                    )
                )
                if matched:
                    created += 1
        await db.commit()
    return created


def _mark_failed_delivery(
    delivery: WebhookDelivery,
    error: str,
    now: datetime,
) -> None:
    delivery.status = "failed"
    delivery.last_error = error[:500]
    if delivery.attempts < 5:
        delivery.next_attempt_at = now + timedelta(minutes=2 ** delivery.attempts)
    else:
        delivery.status = "exhausted"
        delivery.next_attempt_at = None
        logger.error(
            "webhook_delivery_exhausted",
            extra={
                "event": "webhook_delivery_exhausted",
                "attempts": delivery.attempts,
            },
        )


def _payload(activity: ActivityLog) -> dict:
    return {
        "id": str(activity.id),
        "event": activity.action,
        "created_at": activity.created_at.isoformat(),
        "workspace_id": str(activity.workspace_id),
        "project_id": str(activity.project_id) if activity.project_id else None,
        "task_id": str(activity.task_id) if activity.task_id else None,
        "actor_id": str(activity.actor_id),
        "summary": activity.summary,
    }


async def process_webhook_deliveries(limit: int = 100) -> int:
    now = datetime.now(UTC)
    processed = 0
    async with SessionLocal() as db:
        deliveries = list(
            (
                await db.scalars(
                    select(WebhookDelivery)
                    .where(
                        WebhookDelivery.status.in_(["pending", "failed"]),
                        WebhookDelivery.attempts < 5,
                        or_(
                            WebhookDelivery.next_attempt_at.is_(None),
                            WebhookDelivery.next_attempt_at <= now,
                        ),
                    )
                    .order_by(WebhookDelivery.created_at)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            for delivery in deliveries:
                hook = await db.get(WorkspaceWebhook, delivery.webhook_id)
                activity = await db.get(ActivityLog, delivery.activity_id)
                if hook is None or not hook.active or activity is None:
                    delivery.status = "skipped"
                    delivery.last_error = "webhook_or_activity_unavailable"
                    delivery.next_attempt_at = None
                    processed += 1
                    continue
                try:
                    url = validate_webhook_url(hook.url, production=settings.app_env == "production")
                    secret = decrypt_secret(hook.secret_ciphertext)
                except Exception as exc:
                    delivery.attempts += 1
                    _mark_failed_delivery(
                        delivery,
                        f"configuration_error:{type(exc).__name__}",
                        now,
                    )
                    processed += 1
                    continue

                body = json.dumps(_payload(activity), separators=(",", ":"), sort_keys=True).encode()
                timestamp = int(now.timestamp())
                headers = {
                    "Content-Type": "application/json",
                    "User-Agent": "TaskPilot-Webhooks/1.0",
                    "X-TaskPilot-Event": activity.action,
                    "X-TaskPilot-Delivery": str(delivery.id),
                    "X-TaskPilot-Timestamp": str(timestamp),
                    "X-TaskPilot-Signature": sign_webhook(secret, timestamp, body),
                }
                delivery.attempts += 1
                try:
                    response = await client.post(url, content=body, headers=headers)
                    delivery.response_status = response.status_code
                    if 200 <= response.status_code < 300:
                        delivery.status = "delivered"
                        delivery.delivered_at = now
                        delivery.last_error = None
                        delivery.next_attempt_at = None
                    else:
                        _mark_failed_delivery(
                            delivery,
                            f"http_{response.status_code}",
                            now,
                        )
                except httpx.HTTPError as exc:
                    _mark_failed_delivery(
                        delivery,
                        f"network_error:{type(exc).__name__}",
                        now,
                    )
                processed += 1
        await db.commit()
    return processed
