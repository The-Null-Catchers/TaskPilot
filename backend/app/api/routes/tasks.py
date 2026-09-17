from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, require_project, require_workspace
from app.collaboration_models import (
    Checklist,
    ChecklistItem,
    ProjectMember,
    Subtask,
    TaskDependency,
    TaskWatcher,
)
from app.collaboration_schemas import (
    ChecklistCreate,
    ChecklistItemCreate,
    ChecklistItemOut,
    ChecklistItemPatch,
    ChecklistOut,
    CommentPatch,
    DependencyCreate,
    DependencyOut,
    SubtaskCreate,
    SubtaskOut,
    SubtaskPatch,
    TaskDependenciesOut,
    TaskUserIn,
    UserSummary,
)
from app.db import get_db
from app.domain import would_create_dependency_cycle
from app.models import (
    ActivityLog,
    BoardColumn,
    Comment,
    Notification,
    Project,
    Task,
    TaskAssignee,
    User,
    WorkspaceMember,
)
from app.realtime import publish
from app.schemas import CommentCreate, CommentOut, TaskCreate, TaskMove, TaskOut, TaskPatch

router = APIRouter(prefix="/tasks", tags=["tasks"])


async def _task_access(
    db: AsyncSession,
    task_id: UUID,
    user_id: UUID,
    *,
    write: bool = False,
) -> Task:
    task = await db.get(Task, task_id)
    if not task or task.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Task not found")
    await require_project(db, task.project_id, user_id, write=write)
    return task


def _activity(db: AsyncSession, task: Task, user_id: UUID, action: str, summary: str) -> None:
    db.add(
        ActivityLog(
            workspace_id=task.workspace_id,
            project_id=task.project_id,
            task_id=task.id,
            actor_id=user_id,
            action=action,
            summary=summary,
        )
    )


async def _assignable_user(db: AsyncSession, task: Task, user_id: UUID) -> User:
    target = await db.get(User, user_id)
    if not target or not target.is_active:
        raise HTTPException(status_code=400, detail="Assignee is not an active user")
    membership = await db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == task.workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    if not membership:
        raise HTTPException(status_code=400, detail="Assignee must be a workspace member")
    if membership.role == "guest":
        project_member = await db.scalar(
            select(ProjectMember.id).where(
                ProjectMember.project_id == task.project_id,
                ProjectMember.user_id == user_id,
            )
        )
        if project_member is None:
            raise HTTPException(status_code=400, detail="Guest must have access to this project")
    return target


async def _notify_dependency_resolved(db: AsyncSession, blocker: Task) -> None:
    dependencies = list(
        (
            await db.scalars(
                select(TaskDependency).where(TaskDependency.blocker_task_id == blocker.id)
            )
        ).all()
    )
    for dependency in dependencies:
        blocked = await db.get(Task, dependency.blocked_task_id)
        if not blocked or blocked.deleted_at is not None:
            continue
        assignees = set(
            (
                await db.scalars(
                    select(TaskAssignee.user_id).where(TaskAssignee.task_id == blocked.id)
                )
            ).all()
        )
        watchers = set(
            (
                await db.scalars(
                    select(TaskWatcher.user_id).where(TaskWatcher.task_id == blocked.id)
                )
            ).all()
        )
        for recipient_id in assignees | watchers:
            db.add(
                Notification(
                    user_id=recipient_id,
                    kind="dependency.resolved",
                    title="Dependency resolved",
                    body=f"{blocker.identifier} no longer blocks {blocked.identifier}.",
                    entity_type="task",
                    entity_id=blocked.id,
                )
            )


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(
    task_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _task_access(db, task_id, user.id)


@router.post("", response_model=TaskOut, status_code=201)
async def create_task(
    data: TaskCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await db.scalar(select(Project).where(Project.id == data.project_id).with_for_update())
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    await require_project(db, project.id, user.id, write=True)
    column = await db.get(BoardColumn, data.column_id)
    if not column or column.project_id != project.id:
        raise HTTPException(status_code=400, detail="Column does not belong to project")
    project.task_counter += 1
    max_position = await db.scalar(
        select(func.max(Task.position)).where(
            Task.column_id == column.id,
            Task.deleted_at.is_(None),
        )
    )
    task = Task(
        workspace_id=project.workspace_id,
        project_id=project.id,
        column_id=column.id,
        reporter_id=user.id,
        number=project.task_counter,
        identifier=f"{project.key}-{project.task_counter}",
        title=data.title.strip(),
        description=data.description,
        priority=data.priority,
        due_date=data.due_date,
        position=(max_position or 0) + 1000,
    )
    db.add(task)
    await db.flush()
    _activity(db, task, user.id, "task.created", f"Created {task.identifier}: {task.title}")
    await db.commit()
    await db.refresh(task)
    payload = TaskOut.model_validate(task).model_dump(mode="json")
    await publish(task.workspace_id, "task.created", payload)
    return task


@router.patch("/{task_id}", response_model=TaskOut)
async def patch_task(
    task_id: UUID,
    data: TaskPatch,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _task_access(db, task_id, user.id, write=True)
    previous_status = task.status
    values = data.model_dump(exclude={"version"}, exclude_unset=True)
    for field in ("title", "description", "priority", "status"):
        if values.get(field) is None:
            values.pop(field, None)
    values["version"] = data.version + 1
    result = await db.execute(
        update(Task)
        .where(Task.id == task.id, Task.version == data.version)
        .values(**values)
        .returning(Task)
    )
    updated = result.scalar_one_or_none()
    if not updated:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Task was changed by another collaborator. Refresh and retry.",
        )
    _activity(db, task, user.id, "task.updated", f"Updated {task.identifier}")
    if previous_status != "done" and updated.status == "done":
        await _notify_dependency_resolved(db, updated)
    await db.commit()
    await db.refresh(updated)
    payload = TaskOut.model_validate(updated).model_dump(mode="json")
    await publish(updated.workspace_id, "task.updated", payload)
    return updated


@router.post("/{task_id}/move", response_model=TaskOut)
async def move_task(
    task_id: UUID,
    data: TaskMove,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _task_access(db, task_id, user.id, write=True)
    column = await db.get(BoardColumn, data.column_id)
    if not column or column.project_id != task.project_id:
        raise HTTPException(status_code=400, detail="Invalid destination column")
    result = await db.execute(
        update(Task)
        .where(Task.id == task.id, Task.version == data.version)
        .values(column_id=column.id, position=data.position, version=data.version + 1)
        .returning(Task)
    )
    moved = result.scalar_one_or_none()
    if not moved:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Task moved by another collaborator")
    _activity(db, task, user.id, "task.moved", f"Moved {task.identifier} to {column.name}")
    await db.commit()
    await db.refresh(moved)
    payload = TaskOut.model_validate(moved).model_dump(mode="json")
    await publish(moved.workspace_id, "task.moved", payload)
    return moved


@router.get("/{task_id}/assignees", response_model=list[UserSummary])
async def list_assignees(
    task_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await _task_access(db, task_id, user.id)
    query = (
        select(User)
        .join(TaskAssignee, TaskAssignee.user_id == User.id)
        .where(TaskAssignee.task_id == task_id)
        .order_by(User.name)
    )
    return list((await db.scalars(query)).all())


@router.post("/{task_id}/assignees", response_model=UserSummary)
async def assign_user(
    task_id: UUID,
    data: TaskUserIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _task_access(db, task_id, user.id, write=True)
    target = await _assignable_user(db, task, data.user_id)
    existing = await db.scalar(
        select(TaskAssignee.id).where(
            TaskAssignee.task_id == task.id,
            TaskAssignee.user_id == target.id,
        )
    )
    if existing is None:
        db.add(TaskAssignee(task_id=task.id, user_id=target.id))
        if target.id != user.id:
            db.add(
                Notification(
                    user_id=target.id,
                    kind="task.assigned",
                    title=f"Assigned to {task.identifier}",
                    body=task.title,
                    entity_type="task",
                    entity_id=task.id,
                )
            )
        _activity(db, task, user.id, "task.assigned", f"Assigned {target.name} to {task.identifier}")
        await db.commit()
        await publish(task.workspace_id, "task.assigned", {"task_id": str(task.id), "user_id": str(target.id)})
    return target


@router.delete("/{task_id}/assignees/{assignee_id}", status_code=204)
async def unassign_user(
    task_id: UUID,
    assignee_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _task_access(db, task_id, user.id, write=True)
    assignment = await db.scalar(
        select(TaskAssignee).where(
            TaskAssignee.task_id == task.id,
            TaskAssignee.user_id == assignee_id,
        )
    )
    if not assignment:
        raise HTTPException(status_code=404, detail="Task assignee not found")
    await db.delete(assignment)
    _activity(db, task, user.id, "task.unassigned", f"Unassigned a member from {task.identifier}")
    await db.commit()
    await publish(task.workspace_id, "task.unassigned", {"task_id": str(task.id), "user_id": str(assignee_id)})


@router.post("/{task_id}/watch", status_code=204)
async def watch_task(
    task_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _task_access(db, task_id, user.id)
    existing = await db.scalar(
        select(TaskWatcher.id).where(TaskWatcher.task_id == task.id, TaskWatcher.user_id == user.id)
    )
    if existing is None:
        db.add(TaskWatcher(task_id=task.id, user_id=user.id))
        await db.commit()


@router.delete("/{task_id}/watch", status_code=204)
async def unwatch_task(
    task_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _task_access(db, task_id, user.id)
    watcher = await db.scalar(
        select(TaskWatcher).where(TaskWatcher.task_id == task.id, TaskWatcher.user_id == user.id)
    )
    if watcher:
        await db.delete(watcher)
        await db.commit()


@router.get("/{task_id}/subtasks", response_model=list[SubtaskOut])
async def list_subtasks(
    task_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await _task_access(db, task_id, user.id)
    query = select(Subtask).where(Subtask.task_id == task_id).order_by(Subtask.position, Subtask.created_at)
    return list((await db.scalars(query)).all())


@router.post("/{task_id}/subtasks", response_model=SubtaskOut, status_code=201)
async def create_subtask(
    task_id: UUID,
    data: SubtaskCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _task_access(db, task_id, user.id, write=True)
    if data.assignee_id:
        await _assignable_user(db, task, data.assignee_id)
    max_position = await db.scalar(select(func.max(Subtask.position)).where(Subtask.task_id == task.id))
    subtask = Subtask(
        task_id=task.id,
        title=data.title.strip(),
        assignee_id=data.assignee_id,
        due_date=data.due_date,
        position=(max_position or 0) + 1000,
    )
    db.add(subtask)
    await db.flush()
    _activity(db, task, user.id, "subtask.created", f"Added subtask to {task.identifier}: {subtask.title}")
    await db.commit()
    await db.refresh(subtask)
    await publish(task.workspace_id, "subtask.created", SubtaskOut.model_validate(subtask).model_dump(mode="json"))
    return subtask


@router.patch("/{task_id}/subtasks/{subtask_id}", response_model=SubtaskOut)
async def patch_subtask(
    task_id: UUID,
    subtask_id: UUID,
    data: SubtaskPatch,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _task_access(db, task_id, user.id, write=True)
    current = await db.scalar(select(Subtask).where(Subtask.id == subtask_id, Subtask.task_id == task.id))
    if not current:
        raise HTTPException(status_code=404, detail="Subtask not found")
    values = data.model_dump(exclude={"version"}, exclude_unset=True)
    if values.get("title") is None:
        values.pop("title", None)
    if values.get("status") is None:
        values.pop("status", None)
    if "assignee_id" in values and values["assignee_id"] is not None:
        await _assignable_user(db, task, values["assignee_id"])
    values["version"] = data.version + 1
    result = await db.execute(
        update(Subtask)
        .where(Subtask.id == current.id, Subtask.version == data.version)
        .values(**values)
        .returning(Subtask)
    )
    updated = result.scalar_one_or_none()
    if not updated:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Subtask was changed by another collaborator")
    await db.commit()
    await db.refresh(updated)
    await publish(task.workspace_id, "subtask.updated", SubtaskOut.model_validate(updated).model_dump(mode="json"))
    return updated


@router.delete("/{task_id}/subtasks/{subtask_id}", status_code=204)
async def delete_subtask(
    task_id: UUID,
    subtask_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _task_access(db, task_id, user.id, write=True)
    subtask = await db.scalar(select(Subtask).where(Subtask.id == subtask_id, Subtask.task_id == task.id))
    if not subtask:
        raise HTTPException(status_code=404, detail="Subtask not found")
    await db.delete(subtask)
    await db.commit()
    await publish(task.workspace_id, "subtask.deleted", {"task_id": str(task.id), "subtask_id": str(subtask_id)})


@router.get("/{task_id}/checklists", response_model=list[ChecklistOut])
async def list_checklists(
    task_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await _task_access(db, task_id, user.id)
    return list((await db.scalars(select(Checklist).where(Checklist.task_id == task_id).order_by(Checklist.position))).all())


@router.post("/{task_id}/checklists", response_model=ChecklistOut, status_code=201)
async def create_checklist(
    task_id: UUID,
    data: ChecklistCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _task_access(db, task_id, user.id, write=True)
    max_position = await db.scalar(select(func.max(Checklist.position)).where(Checklist.task_id == task.id))
    checklist = Checklist(task_id=task.id, title=data.title.strip(), position=(max_position or 0) + 1000)
    db.add(checklist)
    await db.commit()
    await db.refresh(checklist)
    await publish(task.workspace_id, "checklist.created", ChecklistOut.model_validate(checklist).model_dump(mode="json"))
    return checklist


async def _checklist_access(db: AsyncSession, task: Task, checklist_id: UUID) -> Checklist:
    checklist = await db.scalar(
        select(Checklist).where(Checklist.id == checklist_id, Checklist.task_id == task.id)
    )
    if not checklist:
        raise HTTPException(status_code=404, detail="Checklist not found")
    return checklist


@router.delete("/{task_id}/checklists/{checklist_id}", status_code=204)
async def delete_checklist(
    task_id: UUID,
    checklist_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _task_access(db, task_id, user.id, write=True)
    checklist = await _checklist_access(db, task, checklist_id)
    await db.delete(checklist)
    await db.commit()
    await publish(task.workspace_id, "checklist.deleted", {"task_id": str(task.id), "checklist_id": str(checklist_id)})


@router.get("/{task_id}/checklists/{checklist_id}/items", response_model=list[ChecklistItemOut])
async def list_checklist_items(
    task_id: UUID,
    checklist_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _task_access(db, task_id, user.id)
    await _checklist_access(db, task, checklist_id)
    query = select(ChecklistItem).where(ChecklistItem.checklist_id == checklist_id).order_by(ChecklistItem.position)
    return list((await db.scalars(query)).all())


@router.post("/{task_id}/checklists/{checklist_id}/items", response_model=ChecklistItemOut, status_code=201)
async def create_checklist_item(
    task_id: UUID,
    checklist_id: UUID,
    data: ChecklistItemCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _task_access(db, task_id, user.id, write=True)
    await _checklist_access(db, task, checklist_id)
    if data.assignee_id:
        await _assignable_user(db, task, data.assignee_id)
    max_position = await db.scalar(
        select(func.max(ChecklistItem.position)).where(ChecklistItem.checklist_id == checklist_id)
    )
    item = ChecklistItem(
        checklist_id=checklist_id,
        title=data.title.strip(),
        assignee_id=data.assignee_id,
        position=(max_position or 0) + 1000,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    await publish(task.workspace_id, "checklist.item.created", ChecklistItemOut.model_validate(item).model_dump(mode="json"))
    return item


@router.patch("/{task_id}/checklists/{checklist_id}/items/{item_id}", response_model=ChecklistItemOut)
async def patch_checklist_item(
    task_id: UUID,
    checklist_id: UUID,
    item_id: UUID,
    data: ChecklistItemPatch,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _task_access(db, task_id, user.id, write=True)
    await _checklist_access(db, task, checklist_id)
    current = await db.scalar(
        select(ChecklistItem).where(
            ChecklistItem.id == item_id,
            ChecklistItem.checklist_id == checklist_id,
        )
    )
    if not current:
        raise HTTPException(status_code=404, detail="Checklist item not found")
    values = data.model_dump(exclude={"version"}, exclude_unset=True)
    if values.get("title") is None:
        values.pop("title", None)
    if "assignee_id" in values and values["assignee_id"] is not None:
        await _assignable_user(db, task, values["assignee_id"])
    values["version"] = data.version + 1
    result = await db.execute(
        update(ChecklistItem)
        .where(ChecklistItem.id == current.id, ChecklistItem.version == data.version)
        .values(**values)
        .returning(ChecklistItem)
    )
    updated = result.scalar_one_or_none()
    if not updated:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Checklist item changed by another collaborator")
    await db.commit()
    await db.refresh(updated)
    await publish(task.workspace_id, "checklist.item.updated", ChecklistItemOut.model_validate(updated).model_dump(mode="json"))
    return updated


@router.delete("/{task_id}/checklists/{checklist_id}/items/{item_id}", status_code=204)
async def delete_checklist_item(
    task_id: UUID,
    checklist_id: UUID,
    item_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _task_access(db, task_id, user.id, write=True)
    await _checklist_access(db, task, checklist_id)
    item = await db.scalar(
        select(ChecklistItem).where(
            ChecklistItem.id == item_id,
            ChecklistItem.checklist_id == checklist_id,
        )
    )
    if not item:
        raise HTTPException(status_code=404, detail="Checklist item not found")
    await db.delete(item)
    await db.commit()
    await publish(task.workspace_id, "checklist.item.deleted", {"task_id": str(task.id), "item_id": str(item_id)})


@router.get("/{task_id}/dependencies", response_model=TaskDependenciesOut)
async def list_dependencies(
    task_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _task_access(db, task_id, user.id)
    blocked_by = list(
        (
            await db.scalars(
                select(TaskDependency).where(TaskDependency.blocked_task_id == task.id)
            )
        ).all()
    )
    blocks = list(
        (
            await db.scalars(
                select(TaskDependency).where(TaskDependency.blocker_task_id == task.id)
            )
        ).all()
    )
    return TaskDependenciesOut(
        blocked_by=[DependencyOut.model_validate(item) for item in blocked_by],
        blocks=[DependencyOut.model_validate(item) for item in blocks],
    )


@router.post("/{task_id}/dependencies", response_model=DependencyOut, status_code=201)
async def create_dependency(
    task_id: UUID,
    data: DependencyCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    blocked = await _task_access(db, task_id, user.id, write=True)
    blocker = await _task_access(db, data.blocker_task_id, user.id)
    if blocker.project_id != blocked.project_id:
        raise HTTPException(status_code=400, detail="Dependencies must belong to the same project")
    project_task_ids = select(Task.id).where(Task.project_id == blocked.project_id, Task.deleted_at.is_(None))
    rows = (
        await db.execute(
            select(TaskDependency.blocker_task_id, TaskDependency.blocked_task_id).where(
                TaskDependency.blocker_task_id.in_(project_task_ids),
                TaskDependency.blocked_task_id.in_(project_task_ids),
            )
        )
    ).all()
    if would_create_dependency_cycle(rows, blocker.id, blocked.id):
        raise HTTPException(status_code=409, detail="Dependency would create a circular relationship")
    existing = await db.scalar(
        select(TaskDependency).where(
            TaskDependency.blocker_task_id == blocker.id,
            TaskDependency.blocked_task_id == blocked.id,
        )
    )
    if existing:
        return existing
    dependency = TaskDependency(
        blocker_task_id=blocker.id,
        blocked_task_id=blocked.id,
        created_by_id=user.id,
    )
    db.add(dependency)
    await db.flush()
    _activity(db, blocked, user.id, "task.dependency.added", f"{blocked.identifier} is blocked by {blocker.identifier}")
    await db.commit()
    await db.refresh(dependency)
    await publish(blocked.workspace_id, "task.dependency.added", DependencyOut.model_validate(dependency).model_dump(mode="json"))
    return dependency


@router.delete("/{task_id}/dependencies/{dependency_id}", status_code=204)
async def delete_dependency(
    task_id: UUID,
    dependency_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _task_access(db, task_id, user.id, write=True)
    dependency = await db.get(TaskDependency, dependency_id)
    if not dependency or task.id not in {dependency.blocker_task_id, dependency.blocked_task_id}:
        raise HTTPException(status_code=404, detail="Dependency not found")
    await db.delete(dependency)
    await db.commit()
    await publish(task.workspace_id, "task.dependency.deleted", {"task_id": str(task.id), "dependency_id": str(dependency_id)})


@router.get("/{task_id}/comments", response_model=list[CommentOut])
async def comments(
    task_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await _task_access(db, task_id, user.id)
    return list(
        (
            await db.scalars(
                select(Comment).where(Comment.task_id == task_id).order_by(Comment.created_at)
            )
        ).all()
    )


@router.post("/{task_id}/comments", response_model=CommentOut, status_code=201)
async def add_comment(
    task_id: UUID,
    data: CommentCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _task_access(db, task_id, user.id)
    comment = Comment(task_id=task.id, author_id=user.id, body=data.body.strip())
    db.add(comment)
    await db.flush()
    watcher_ids = set(
        (
            await db.scalars(
                select(TaskWatcher.user_id).where(
                    TaskWatcher.task_id == task.id,
                    TaskWatcher.user_id != user.id,
                )
            )
        ).all()
    )
    for watcher_id in watcher_ids:
        db.add(
            Notification(
                user_id=watcher_id,
                kind="task.comment",
                title=f"New comment on {task.identifier}",
                body=data.body.strip()[:500],
                entity_type="task",
                entity_id=task.id,
            )
        )
    _activity(db, task, user.id, "comment.created", f"Commented on {task.identifier}")
    await db.commit()
    await db.refresh(comment)
    payload = CommentOut.model_validate(comment).model_dump(mode="json")
    await publish(task.workspace_id, "comment.created", payload)
    return comment


@router.patch("/{task_id}/comments/{comment_id}", response_model=CommentOut)
async def edit_comment(
    task_id: UUID,
    comment_id: UUID,
    data: CommentPatch,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _task_access(db, task_id, user.id)
    comment = await db.scalar(
        select(Comment).where(Comment.id == comment_id, Comment.task_id == task.id)
    )
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    if comment.author_id != user.id:
        raise HTTPException(status_code=403, detail="You can only edit your own comments")
    comment.body = data.body.strip()
    comment.edited_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(comment)
    payload = CommentOut.model_validate(comment).model_dump(mode="json")
    await publish(task.workspace_id, "comment.updated", payload)
    return comment


@router.delete("/{task_id}/comments/{comment_id}", status_code=204)
async def delete_comment(
    task_id: UUID,
    comment_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _task_access(db, task_id, user.id)
    comment = await db.scalar(
        select(Comment).where(Comment.id == comment_id, Comment.task_id == task.id)
    )
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    if comment.author_id != user.id:
        raise HTTPException(status_code=403, detail="You can only delete your own comments")
    await db.delete(comment)
    await db.commit()
    await publish(task.workspace_id, "comment.deleted", {"task_id": str(task.id), "comment_id": str(comment_id)})
