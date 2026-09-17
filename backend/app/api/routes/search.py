from fastapi import APIRouter, Depends, Query
from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.collaboration_models import ProjectMember
from app.db import get_db
from app.models import Comment, Label, Project, Task, User, Workspace, WorkspaceMember

router = APIRouter(prefix="/search", tags=["search"])


def _project_visible(user_id):
    return or_(
        WorkspaceMember.role != "guest",
        exists(
            select(ProjectMember.id).where(
                ProjectMember.project_id == Project.id,
                ProjectMember.user_id == user_id,
            )
        ),
    )


def _task_visible(user_id):
    return or_(
        WorkspaceMember.role != "guest",
        exists(
            select(ProjectMember.id).where(
                ProjectMember.project_id == Task.project_id,
                ProjectMember.user_id == user_id,
            )
        ),
    )


@router.get("")
async def search(
    q: str = Query(min_length=2, max_length=100),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    term = f"%{q.strip()}%"

    workspaces = list(
        (
            await db.scalars(
                select(Workspace)
                .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
                .where(
                    WorkspaceMember.user_id == user.id,
                    Workspace.name.ilike(term),
                )
                .order_by(Workspace.updated_at.desc())
                .limit(10)
            )
        ).all()
    )

    projects = list(
        (
            await db.scalars(
                select(Project)
                .join(WorkspaceMember, WorkspaceMember.workspace_id == Project.workspace_id)
                .where(
                    WorkspaceMember.user_id == user.id,
                    Project.name.ilike(term),
                    _project_visible(user.id),
                )
                .order_by(Project.updated_at.desc())
                .limit(10)
            )
        ).all()
    )

    tasks = list(
        (
            await db.scalars(
                select(Task)
                .join(WorkspaceMember, WorkspaceMember.workspace_id == Task.workspace_id)
                .where(
                    WorkspaceMember.user_id == user.id,
                    Task.deleted_at.is_(None),
                    _task_visible(user.id),
                    or_(
                        Task.title.ilike(term),
                        Task.description.ilike(term),
                        Task.identifier.ilike(term),
                    ),
                )
                .order_by(Task.updated_at.desc())
                .limit(20)
            )
        ).all()
    )

    comments = list(
        (
            await db.execute(
                select(Comment, Task)
                .join(Task, Task.id == Comment.task_id)
                .join(WorkspaceMember, WorkspaceMember.workspace_id == Task.workspace_id)
                .where(
                    WorkspaceMember.user_id == user.id,
                    Task.deleted_at.is_(None),
                    _task_visible(user.id),
                    Comment.body.ilike(term),
                )
                .order_by(Comment.created_at.desc())
                .limit(10)
            )
        ).all()
    )

    labels = list(
        (
            await db.scalars(
                select(Label)
                .join(WorkspaceMember, WorkspaceMember.workspace_id == Label.workspace_id)
                .where(
                    WorkspaceMember.user_id == user.id,
                    Label.name.ilike(term),
                )
                .order_by(Label.name)
                .limit(10)
            )
        ).all()
    )

    return {
        "workspaces": [
            {"id": str(item.id), "name": item.name, "slug": item.slug}
            for item in workspaces
        ],
        "projects": [
            {
                "id": str(item.id),
                "workspace_id": str(item.workspace_id),
                "name": item.name,
                "key": item.key,
            }
            for item in projects
        ],
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
        "comments": [
            {
                "id": str(comment.id),
                "task_id": str(task.id),
                "project_id": str(task.project_id),
                "workspace_id": str(task.workspace_id),
                "task_identifier": task.identifier,
                "body": comment.body[:240],
            }
            for comment, task in comments
        ],
        "labels": [
            {
                "id": str(item.id),
                "workspace_id": str(item.workspace_id),
                "name": item.name,
                "color": item.color,
            }
            for item in labels
        ],
    }
