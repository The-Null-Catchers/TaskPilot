from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, require_workspace
from app.db import get_db
from app.models import ActivityLog, User

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("/workspaces/{workspace_id}")
async def workspace_activity(
    workspace_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace(db, workspace_id, user.id)
    items = list(
        (
            await db.scalars(
                select(ActivityLog)
                .where(ActivityLog.workspace_id == workspace_id)
                .order_by(ActivityLog.created_at.desc())
                .limit(100)
            )
        ).all()
    )
    return [
        {
            "id": str(item.id),
            "action": item.action,
            "summary": item.summary,
            "actor_id": str(item.actor_id),
            "project_id": str(item.project_id) if item.project_id else None,
            "task_id": str(item.task_id) if item.task_id else None,
            "created_at": item.created_at,
        }
        for item in items
    ]
