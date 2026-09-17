import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.attachment_models import Attachment
from app.collaboration_models import AuditLog
from app.db import get_db
from app.models import Project, Session, Task, User, Workspace
from app.notification_models import NotificationDelivery, PushSubscription

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(user: User) -> None:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Administrator access required")


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/metrics")
async def metrics(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(user)
    users = await db.scalar(select(func.count()).select_from(User))
    active_users = await db.scalar(
        select(func.count()).select_from(User).where(User.is_active.is_(True))
    )
    workspaces = await db.scalar(select(func.count()).select_from(Workspace))
    projects = await db.scalar(select(func.count()).select_from(Project))
    tasks = await db.scalar(
        select(func.count()).select_from(Task).where(Task.deleted_at.is_(None))
    )
    completed = await db.scalar(
        select(func.count())
        .select_from(Task)
        .where(Task.status == "done", Task.deleted_at.is_(None))
    )
    return {
        "users": users or 0,
        "active_users": active_users or 0,
        "workspaces": workspaces or 0,
        "projects": projects or 0,
        "tasks": tasks or 0,
        "completed_tasks": completed or 0,
    }


@router.get("/overview")
async def operational_overview(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(user)
    now = datetime.now(UTC)
    week_ago = now - timedelta(days=7)

    users = int(await db.scalar(select(func.count()).select_from(User)) or 0)
    active_users = int(
        await db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True)))
        or 0
    )
    suspended_users = users - active_users
    recent_signups = int(
        await db.scalar(
            select(func.count()).select_from(User).where(User.created_at >= week_ago)
        )
        or 0
    )
    active_sessions = int(
        await db.scalar(
            select(func.count())
            .select_from(Session)
            .where(Session.revoked_at.is_(None), Session.expires_at > now)
        )
        or 0
    )
    workspaces = int(await db.scalar(select(func.count()).select_from(Workspace)) or 0)
    projects = int(await db.scalar(select(func.count()).select_from(Project)) or 0)
    tasks = int(
        await db.scalar(
            select(func.count()).select_from(Task).where(Task.deleted_at.is_(None))
        )
        or 0
    )
    completed_tasks = int(
        await db.scalar(
            select(func.count())
            .select_from(Task)
            .where(Task.status == "done", Task.deleted_at.is_(None))
        )
        or 0
    )
    storage_bytes = int(
        await db.scalar(select(func.coalesce(func.sum(Attachment.size_bytes), 0))) or 0
    )
    attachment_count = int(
        await db.scalar(select(func.count()).select_from(Attachment)) or 0
    )

    delivery_rows = (
        await db.execute(
            select(NotificationDelivery.status, func.count(NotificationDelivery.id)).group_by(
                NotificationDelivery.status
            )
        )
    ).all()
    deliveries = {status: int(count) for status, count in delivery_rows}

    push_rows = (
        await db.execute(
            select(PushSubscription.channel, func.count(PushSubscription.id))
            .where(PushSubscription.revoked_at.is_(None))
            .group_by(PushSubscription.channel)
        )
    ).all()
    push_subscriptions = {channel: int(count) for channel, count in push_rows}

    recent_users = list(
        (
            await db.scalars(
                select(User).order_by(User.created_at.desc()).limit(8)
            )
        ).all()
    )
    return {
        "users": {
            "total": users,
            "active": active_users,
            "suspended": suspended_users,
            "recent_signups_7d": recent_signups,
        },
        "sessions": {"active": active_sessions},
        "workspaces": workspaces,
        "projects": projects,
        "tasks": {
            "total": tasks,
            "completed": completed_tasks,
            "completion_percentage": round((completed_tasks / tasks * 100) if tasks else 0, 1),
        },
        "storage": {"bytes": storage_bytes, "attachments": attachment_count},
        "notification_deliveries": deliveries,
        "push_subscriptions": push_subscriptions,
        "recent_users": [
            {
                "id": item.id,
                "email": item.email,
                "name": item.name,
                "is_active": item.is_active,
                "is_admin": item.is_admin,
                "created_at": item.created_at,
            }
            for item in recent_users
        ],
    }


@router.get("/users")
async def list_users(
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(user)
    limit = min(max(limit, 1), 100)
    offset = max(offset, 0)
    query = select(User)
    if q and q.strip():
        needle = f"%{q.strip()}%"
        query = query.where(or_(User.name.ilike(needle), User.email.ilike(needle)))
    users = list(
        (
            await db.scalars(
                query.order_by(User.created_at.desc()).limit(limit).offset(offset)
            )
        ).all()
    )
    return [
        {
            "id": item.id,
            "email": item.email,
            "name": item.name,
            "is_active": item.is_active,
            "is_admin": item.is_admin,
            "created_at": item.created_at,
        }
        for item in users
    ]


@router.post("/users/{user_id}/suspend")
async def suspend_user(
    user_id: UUID,
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(user)
    if user_id == user.id:
        raise HTTPException(status_code=409, detail="You cannot suspend your own account")
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.is_active = False
    now = datetime.now(UTC)
    await db.execute(
        update(Session)
        .where(Session.user_id == target.id, Session.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    db.add(
        AuditLog(
            actor_id=user.id,
            action="admin.user.suspended",
            ip_address=_ip(request),
            metadata_json=json.dumps({"user_id": str(target.id), "email": target.email}),
        )
    )
    await db.commit()
    return {"id": target.id, "is_active": target.is_active}


@router.post("/users/{user_id}/reactivate")
async def reactivate_user(
    user_id: UUID,
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(user)
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.is_active = True
    db.add(
        AuditLog(
            actor_id=user.id,
            action="admin.user.reactivated",
            ip_address=_ip(request),
            metadata_json=json.dumps({"user_id": str(target.id), "email": target.email}),
        )
    )
    await db.commit()
    return {"id": target.id, "is_active": target.is_active}


@router.get("/audit-logs")
async def audit_logs(
    action: str | None = None,
    workspace_id: UUID | None = None,
    limit: int = 100,
    offset: int = 0,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(user)
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    query = select(AuditLog)
    if action:
        query = query.where(AuditLog.action == action)
    if workspace_id:
        query = query.where(AuditLog.workspace_id == workspace_id)
    logs = list(
        (
            await db.scalars(
                query.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
            )
        ).all()
    )
    return [
        {
            "id": item.id,
            "actor_id": item.actor_id,
            "workspace_id": item.workspace_id,
            "action": item.action,
            "ip_address": item.ip_address,
            "metadata": json.loads(item.metadata_json or "{}"),
            "created_at": item.created_at,
        }
        for item in logs
    ]
