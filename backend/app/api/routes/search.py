from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db import get_db
from app.models import Project, Task, User, Workspace, WorkspaceMember

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
async def search(
    q: str = Query(min_length=2, max_length=100),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    term = f"%{q.strip()}%"
    allowed = select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == user.id)
    workspaces = list(
        (
            await db.scalars(
                select(Workspace)
                .where(Workspace.id.in_(allowed), Workspace.name.ilike(term))
                .limit(10)
            )
        ).all()
    )
    projects = list(
        (
            await db.scalars(
                select(Project)
                .where(Project.workspace_id.in_(allowed), Project.name.ilike(term))
                .limit(10)
            )
        ).all()
    )
    tasks = list(
        (
            await db.scalars(
                select(Task)
                .where(
                    Task.workspace_id.in_(allowed),
                    Task.deleted_at.is_(None),
                    or_(Task.title.ilike(term), Task.description.ilike(term), Task.identifier.ilike(term)),
                )
                .order_by(Task.updated_at.desc())
                .limit(20)
            )
        ).all()
    )
    return {
        "workspaces": [{"id": str(item.id), "name": item.name, "slug": item.slug} for item in workspaces],
        "projects": [{"id": str(item.id), "workspace_id": str(item.workspace_id), "name": item.name, "key": item.key} for item in projects],
        "tasks": [
            {
                "id": str(item.id),
                "workspace_id": str(item.workspace_id),
                "project_id": str(item.project_id),
                "identifier": item.identifier,
                "title": item.title,
                "priority": item.priority,
                "status": item.status,
            }
            for item in tasks
        ],
    }
