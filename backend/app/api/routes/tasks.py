from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import current_user, require_workspace
from app.db import get_db
from app.models import ActivityLog, BoardColumn, Comment, Project, Task, User
from app.realtime import publish
from app.schemas import CommentCreate, CommentOut, TaskCreate, TaskMove, TaskOut, TaskPatch

router = APIRouter(prefix="/tasks", tags=["tasks"])


async def _task_access(db: AsyncSession, task_id: UUID, user_id: UUID) -> Task:
    task = await db.get(Task, task_id)
    if not task or task.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Task not found")
    await require_workspace(db, task.workspace_id, user_id)
    return task


@router.post("", response_model=TaskOut, status_code=201)
async def create_task(data: TaskCreate, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    project = await db.scalar(select(Project).where(Project.id == data.project_id).with_for_update())
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    await require_workspace(db, project.workspace_id, user.id, {"owner", "admin", "member"})
    column = await db.get(BoardColumn, data.column_id)
    if not column or column.project_id != project.id:
        raise HTTPException(status_code=400, detail="Column does not belong to project")
    project.task_counter += 1
    task = Task(workspace_id=project.workspace_id, project_id=project.id, column_id=column.id, reporter_id=user.id, number=project.task_counter, identifier=f"{project.key}-{project.task_counter}", title=data.title.strip(), description=data.description, priority=data.priority, due_date=data.due_date)
    db.add(task)
    await db.flush()
    db.add(ActivityLog(workspace_id=task.workspace_id, project_id=task.project_id, task_id=task.id, actor_id=user.id, action="task.created", summary=f"Created {task.identifier}: {task.title}"))
    await db.commit()
    await db.refresh(task)
    payload = TaskOut.model_validate(task).model_dump(mode="json")
    await publish(task.workspace_id, "task.created", payload)
    return task


@router.patch("/{task_id}", response_model=TaskOut)
async def patch_task(task_id: UUID, data: TaskPatch, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    task = await _task_access(db, task_id, user.id)
    values = data.model_dump(exclude={"version"}, exclude_unset=True)
    values["version"] = data.version + 1
    result = await db.execute(update(Task).where(Task.id == task.id, Task.version == data.version).values(**values).returning(Task))
    updated = result.scalar_one_or_none()
    if not updated:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Task was changed by another collaborator. Refresh and retry.")
    db.add(ActivityLog(workspace_id=task.workspace_id, project_id=task.project_id, task_id=task.id, actor_id=user.id, action="task.updated", summary=f"Updated {task.identifier}"))
    await db.commit()
    await db.refresh(updated)
    payload = TaskOut.model_validate(updated).model_dump(mode="json")
    await publish(updated.workspace_id, "task.updated", payload)
    return updated


@router.post("/{task_id}/move", response_model=TaskOut)
async def move_task(task_id: UUID, data: TaskMove, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    task = await _task_access(db, task_id, user.id)
    column = await db.get(BoardColumn, data.column_id)
    if not column or column.project_id != task.project_id:
        raise HTTPException(status_code=400, detail="Invalid destination column")
    result = await db.execute(update(Task).where(Task.id == task.id, Task.version == data.version).values(column_id=column.id, position=data.position, version=data.version + 1).returning(Task))
    moved = result.scalar_one_or_none()
    if not moved:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Task moved by another collaborator")
    db.add(ActivityLog(workspace_id=task.workspace_id, project_id=task.project_id, task_id=task.id, actor_id=user.id, action="task.moved", summary=f"Moved {task.identifier} to {column.name}"))
    await db.commit()
    await db.refresh(moved)
    payload = TaskOut.model_validate(moved).model_dump(mode="json")
    await publish(moved.workspace_id, "task.moved", payload)
    return moved


@router.get("/{task_id}/comments", response_model=list[CommentOut])
async def comments(task_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await _task_access(db, task_id, user.id)
    return list((await db.scalars(select(Comment).where(Comment.task_id == task_id).order_by(Comment.created_at))).all())


@router.post("/{task_id}/comments", response_model=CommentOut, status_code=201)
async def add_comment(task_id: UUID, data: CommentCreate, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    task = await _task_access(db, task_id, user.id)
    comment = Comment(task_id=task.id, author_id=user.id, body=data.body)
    db.add(comment)
    await db.flush()
    db.add(ActivityLog(workspace_id=task.workspace_id, project_id=task.project_id, task_id=task.id, actor_id=user.id, action="comment.created", summary=f"Commented on {task.identifier}"))
    await db.commit()
    await db.refresh(comment)
    payload = CommentOut.model_validate(comment).model_dump(mode="json")
    await publish(task.workspace_id, "comment.created", payload)
    return comment
