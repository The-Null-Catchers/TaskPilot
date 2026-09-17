from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db import get_db
from app.models import Project, Task, User, Workspace

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/metrics")
async def metrics(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Administrator access required")
    users = await db.scalar(select(func.count()).select_from(User))
    active_users = await db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True)))
    workspaces = await db.scalar(select(func.count()).select_from(Workspace))
    projects = await db.scalar(select(func.count()).select_from(Project))
    tasks = await db.scalar(select(func.count()).select_from(Task).where(Task.deleted_at.is_(None)))
    completed = await db.scalar(select(func.count()).select_from(Task).where(Task.status == "done", Task.deleted_at.is_(None)))
    return {
        "users": users or 0,
        "active_users": active_users or 0,
        "workspaces": workspaces or 0,
        "projects": projects or 0,
        "tasks": tasks or 0,
        "completed_tasks": completed or 0,
    }
