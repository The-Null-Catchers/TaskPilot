import asyncio
from datetime import UTC, datetime, timedelta

from celery import Celery
from celery.schedules import crontab
from sqlalchemy import exists, or_, select

from app.core.config import settings
from app.db import SessionLocal
from app.email_delivery import send_email
from app.models import Notification, Task, TaskAssignee, User
from app.notification_delivery import kind_allowed, notification_link, send_notification_email, send_push
from app.notification_models import (
    NotificationDelivery,
    NotificationDispatch,
    NotificationPreference,
    PushSubscription,
)
from app.notification_security import decrypt_json, decrypt_text
from app.webhook_delivery import process_webhook_deliveries, queue_webhook_deliveries

celery = Celery("taskpilot", broker=settings.redis_url, backend=settings.redis_url)
celery.conf.beat_schedule = {
    "deadline-reminders-hourly": {
        "task": "taskpilot.deadline_reminders",
        "schedule": 3600.0,
    },
    "notification-dispatch-minute": {
        "task": "taskpilot.notification_dispatch",
        "schedule": 60.0,
    },
    "notification-hourly-digest": {
        "task": "taskpilot.notification_hourly_digest",
        "schedule": crontab(minute=5),
    },
    "notification-daily-digest": {
        "task": "taskpilot.notification_daily_digest",
        "schedule": crontab(hour=8, minute=10),
    },
    "webhook-dispatch-minute": {
        "task": "taskpilot.webhook_dispatch",
        "schedule": 60.0,
    },
}
celery.conf.timezone = "UTC"


async def _preference(db, user_id):
    preference = await db.get(NotificationPreference, user_id)
    if preference is None:
        preference = NotificationPreference(user_id=user_id)
        db.add(preference)
        await db.flush()
    return preference


def _delivery_data(notification: Notification) -> dict:
    return {
        "notification_id": str(notification.id),
        "kind": notification.kind,
        "entity_type": notification.entity_type or "",
        "entity_id": str(notification.entity_id) if notification.entity_id else "",
        "url": notification_link(notification.entity_type, notification.entity_id),
    }


async def _deadline_reminders() -> int:
    now = datetime.now(UTC)
    soon = now + timedelta(hours=24)
    created = 0
    async with SessionLocal() as db:
        tasks = list(
            (
                await db.scalars(
                    select(Task).where(
                        Task.due_date > now,
                        Task.due_date <= soon,
                        Task.status != "done",
                        Task.deleted_at.is_(None),
                    )
                )
            ).all()
        )
        for task in tasks:
            assignees = list(
                (
                    await db.scalars(
                        select(TaskAssignee.user_id).where(TaskAssignee.task_id == task.id)
                    )
                ).all()
            )
            for user_id in assignees:
                existing = await db.scalar(
                    select(Notification.id).where(
                        Notification.user_id == user_id,
                        Notification.kind == "deadline_soon",
                        Notification.entity_id == task.id,
                        Notification.created_at >= now - timedelta(hours=18),
                    )
                )
                if not existing:
                    db.add(
                        Notification(
                            user_id=user_id,
                            kind="deadline_soon",
                            title=f"{task.identifier} is due soon",
                            body=task.title,
                            entity_type="task",
                            entity_id=task.id,
                        )
                    )
                    created += 1
        await db.commit()
    return created


async def _dispatch_notifications(limit: int = 200) -> int:
    created = 0
    async with SessionLocal() as db:
        notifications = list(
            (
                await db.scalars(
                    select(Notification)
                    .where(
                        ~exists(
                            select(NotificationDispatch.notification_id).where(
                                NotificationDispatch.notification_id == Notification.id
                            )
                        )
                    )
                    .order_by(Notification.created_at)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        for notification in notifications:
            preference = await _preference(db, notification.user_id)
            if kind_allowed(notification.kind, preference):
                if preference.email_enabled and preference.digest_frequency == "instant":
                    db.add(
                        NotificationDelivery(
                            notification_id=notification.id,
                            channel="email",
                            target_key="email",
                        )
                    )
                    created += 1
                subscriptions = list(
                    (
                        await db.scalars(
                            select(PushSubscription).where(
                                PushSubscription.user_id == notification.user_id,
                                PushSubscription.revoked_at.is_(None),
                            )
                        )
                    ).all()
                )
                for subscription in subscriptions:
                    enabled = (
                        preference.browser_enabled
                        if subscription.channel == "web_push"
                        else preference.mobile_enabled
                    )
                    if not enabled:
                        continue
                    db.add(
                        NotificationDelivery(
                            notification_id=notification.id,
                            subscription_id=subscription.id,
                            channel=subscription.channel,
                            target_key=str(subscription.id),
                        )
                    )
                    created += 1
            db.add(NotificationDispatch(notification_id=notification.id))
        await db.commit()
    return created


async def _process_pending_deliveries(limit: int = 100) -> int:
    now = datetime.now(UTC)
    processed = 0
    async with SessionLocal() as db:
        deliveries = list(
            (
                await db.scalars(
                    select(NotificationDelivery)
                    .where(
                        NotificationDelivery.status.in_(["pending", "failed"]),
                        NotificationDelivery.attempts < 3,
                        or_(
                            NotificationDelivery.next_attempt_at.is_(None),
                            NotificationDelivery.next_attempt_at <= now,
                        ),
                    )
                    .order_by(NotificationDelivery.created_at)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        for delivery in deliveries:
            notification = await db.get(Notification, delivery.notification_id)
            if notification is None:
                delivery.status = "skipped"
                delivery.last_error = "notification_missing"
                continue
            delivery.attempts += 1
            link = notification_link(notification.entity_type, notification.entity_id)
            if delivery.channel == "email":
                user = await db.get(User, notification.user_id)
                if user is None or not user.is_active:
                    status, error = "skipped", "user_unavailable"
                else:
                    status, error = await asyncio.to_thread(
                        send_notification_email,
                        user.email,
                        notification.title,
                        notification.body,
                        link,
                    )
            else:
                subscription = (
                    await db.get(PushSubscription, delivery.subscription_id)
                    if delivery.subscription_id
                    else None
                )
                if subscription is None or subscription.revoked_at is not None:
                    status, error = "skipped", "subscription_unavailable"
                else:
                    try:
                        target = decrypt_text(subscription.target_ciphertext)
                        config = decrypt_json(subscription.config_ciphertext)
                    except ValueError:
                        status, error = "failed", "subscription_decryption_failed"
                    else:
                        status, error = await asyncio.to_thread(
                            send_push,
                            delivery.channel,
                            target,
                            config,
                            notification.title,
                            notification.body,
                            _delivery_data(notification),
                        )
                    if error == "subscription_gone":
                        subscription.revoked_at = now
            delivery.status = status
            delivery.last_error = error
            if status == "sent":
                delivery.sent_at = now
                delivery.next_attempt_at = None
            elif status == "failed" and delivery.attempts < 3:
                delivery.next_attempt_at = now + timedelta(minutes=2**delivery.attempts)
            else:
                delivery.next_attempt_at = None
            processed += 1
        await db.commit()
    return processed


async def _send_digest(frequency: str, period: timedelta) -> int:
    now = datetime.now(UTC)
    sent = 0
    async with SessionLocal() as db:
        preferences = list(
            (
                await db.scalars(
                    select(NotificationPreference).where(
                        NotificationPreference.email_enabled.is_(True),
                        NotificationPreference.digest_frequency == frequency,
                    )
                )
            ).all()
        )
        for preference in preferences:
            user = await db.get(User, preference.user_id)
            if user is None or not user.is_active:
                continue
            candidates = list(
                (
                    await db.scalars(
                        select(Notification)
                        .where(
                            Notification.user_id == user.id,
                            Notification.created_at >= now - period,
                            ~exists(
                                select(NotificationDelivery.id).where(
                                    NotificationDelivery.notification_id == Notification.id,
                                    NotificationDelivery.channel == "email",
                                    NotificationDelivery.target_key == "email",
                                    NotificationDelivery.status.in_(["sent", "skipped"]),
                                )
                            ),
                        )
                        .order_by(Notification.created_at.desc())
                        .limit(100)
                    )
                ).all()
            )
            candidates = [item for item in candidates if kind_allowed(item.kind, preference)]
            if not candidates:
                continue
            lines = [f"• {item.title}: {item.body}".strip() for item in candidates[:25]]
            if len(candidates) > 25:
                lines.append(f"• …and {len(candidates) - 25} more")
            text = "\n".join(
                [
                    f"You have {len(candidates)} TaskPilot notifications.",
                    "",
                    *lines,
                    "",
                    f"Open TaskPilot: {settings.app_url.rstrip('/')}/app/notifications",
                ]
            )
            try:
                delivered = await asyncio.to_thread(
                    send_email,
                    user.email,
                    f"TaskPilot {frequency} notification digest",
                    text,
                )
            except Exception:
                delivered = False
            if not delivered:
                continue
            for notification in candidates:
                db.add(
                    NotificationDelivery(
                        notification_id=notification.id,
                        channel="email",
                        target_key="email",
                        status="sent",
                        attempts=1,
                        sent_at=now,
                    )
                )
            sent += 1
        await db.commit()
    return sent


@celery.task(name="taskpilot.deadline_reminders")
def deadline_reminders() -> int:
    return asyncio.run(_deadline_reminders())


@celery.task(name="taskpilot.notification_dispatch")
def notification_dispatch() -> dict[str, int]:
    queued = asyncio.run(_dispatch_notifications())
    processed = asyncio.run(_process_pending_deliveries())
    return {"queued": queued, "processed": processed}


@celery.task(name="taskpilot.notification_hourly_digest")
def notification_hourly_digest() -> int:
    return asyncio.run(_send_digest("hourly", timedelta(hours=1, minutes=10)))


@celery.task(name="taskpilot.notification_daily_digest")
def notification_daily_digest() -> int:
    return asyncio.run(_send_digest("daily", timedelta(days=1, hours=1)))


@celery.task(name="taskpilot.webhook_dispatch")
def webhook_dispatch() -> dict[str, int]:
    queued = asyncio.run(queue_webhook_deliveries())
    processed = asyncio.run(process_webhook_deliveries())
    return {"queued": queued, "processed": processed}
