import asyncio
from datetime import UTC, datetime, timedelta
from celery import Celery
from sqlalchemy import select
from app.core.config import settings
from app.db import SessionLocal
from app.models import Notification, Task, TaskAssignee

celery = Celery("taskpilot", broker=settings.redis_url, backend=settings.redis_url)
celery.conf.beat_schedule = {"deadline-reminders-hourly": {"task": "taskpilot.deadline_reminders", "schedule": 3600.0}}
celery.conf.timezone = "UTC"


async def _deadline_reminders() -> int:
    now = datetime.now(UTC)
    soon = now + timedelta(hours=24)
    created = 0
    async with SessionLocal() as db:
        tasks = list((await db.scalars(select(Task).where(Task.due_date > now, Task.due_date <= soon, Task.status != "done", Task.deleted_at.is_(None)))).all())
        for task in tasks:
            assignees = list((await db.scalars(select(TaskAssignee.user_id).where(TaskAssignee.task_id == task.id))).all())
            for user_id in assignees:
                existing = await db.scalar(select(Notification.id).where(Notification.user_id == user_id, Notification.kind == "deadline_soon", Notification.entity_id == task.id, Notification.created_at >= now - timedelta(hours=18)))
                if not existing:
                    db.add(Notification(user_id=user_id, kind="deadline_soon", title=f"{task.identifier} is due soon", body=task.title, entity_type="task", entity_id=task.id))
                    created += 1
        await db.commit()
    return created


@celery.task(name="taskpilot.deadline_reminders")
def deadline_reminders() -> int:
    return asyncio.run(_deadline_reminders())
