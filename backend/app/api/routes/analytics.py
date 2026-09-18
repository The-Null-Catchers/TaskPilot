from datetime import UTC, datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, require_workspace
from app.db import get_db
from app.models import Project, Task, User

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/projects/{project_id}")
async def project_analytics(
    project_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    await require_workspace(db, project.workspace_id, user.id)
    filters = (Task.project_id == project.id, Task.deleted_at.is_(None))
    now = datetime.now(UTC)
    summary = (
        await db.execute(
            select(
                func.count(Task.id),
                func.count(Task.id).filter(Task.status == "done"),
                func.count(Task.id).filter(
                    Task.status != "done",
                    Task.due_date.is_not(None),
                    Task.due_date < now,
                ),
            ).where(*filters)
        )
    ).one()
    total = int(summary[0] or 0)
    completed = int(summary[1] or 0)
    overdue = int(summary[2] or 0)

    status_rows = (
        await db.execute(
            select(Task.status, func.count(Task.id))
            .where(*filters)
            .group_by(Task.status)
        )
    ).all()
    priority_rows = (
        await db.execute(
            select(Task.priority, func.count(Task.id))
            .where(*filters)
            .group_by(Task.priority)
        )
    ).all()

    return {
        "total_tasks": total,
        "completed_tasks": completed,
        "open_tasks": total - completed,
        "overdue_tasks": overdue,
        "completion_percentage": round((completed / total * 100) if total else 0, 1),
        "by_status": {status: int(count) for status, count in status_rows},
        "by_priority": {priority: int(count) for priority, count in priority_rows},
    }
