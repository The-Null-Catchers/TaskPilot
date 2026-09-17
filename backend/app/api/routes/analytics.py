from collections import Counter
from datetime import UTC, datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
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
    tasks = list(
        (
            await db.scalars(
                select(Task).where(Task.project_id == project.id, Task.deleted_at.is_(None))
            )
        ).all()
    )
    now = datetime.now(UTC)
    completed = sum(task.status == "done" for task in tasks)
    overdue = sum(bool(task.due_date and task.due_date < now and task.status != "done") for task in tasks)
    total = len(tasks)
    return {
        "total_tasks": total,
        "completed_tasks": completed,
        "open_tasks": total - completed,
        "overdue_tasks": overdue,
        "completion_percentage": round((completed / total * 100) if total else 0, 1),
        "by_status": dict(Counter(task.status for task in tasks)),
        "by_priority": dict(Counter(task.priority for task in tasks)),
    }
