from datetime import UTC, datetime, time
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, require_project, require_workspace
from app.collaboration_models import ProjectMember, TaskDependency, TaskWatcher
from app.db import get_db
from app.models import Project, Task, TaskAssignee, TaskLabel, User, WorkspaceMember
from app.productivity_schemas import CalendarItem, TaskPage, TimelineOut, TimelineTask
from app.schemas import TaskOut

router = APIRouter(tags=['planning'])


def _accessible_task_predicate(user_id: UUID):
    return or_(
        WorkspaceMember.role != 'guest',
        exists(
            select(ProjectMember.id).where(
                ProjectMember.project_id == Task.project_id,
                ProjectMember.user_id == user_id,
            )
        ),
    )


def _task_query(user_id: UUID):
    return (
        select(Task)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Task.workspace_id)
        .where(
            WorkspaceMember.user_id == user_id,
            Task.deleted_at.is_(None),
            _accessible_task_predicate(user_id),
        )
    )


@router.get('/my-tasks', response_model=TaskPage)
async def my_tasks(
    workspace_id: UUID | None = None,
    project_id: UUID | None = None,
    scope: Literal['assigned', 'created', 'watching', 'all'] = 'assigned',
    status: str | None = None,
    priority: str | None = None,
    due_before: datetime | None = None,
    due_after: datetime | None = None,
    assignee_id: UUID | None = None,
    label_id: UUID | None = None,
    sort_by: Literal['due_date', 'priority', 'created_at', 'updated_at'] = 'due_date',
    sort_direction: Literal['asc', 'desc'] = 'asc',
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    if workspace_id:
        await require_workspace(db, workspace_id, user.id)
    if project_id:
        project, _ = await require_project(db, project_id, user.id)
        if workspace_id and project.workspace_id != workspace_id:
            raise HTTPException(status_code=400, detail='Project does not belong to workspace')

    query = _task_query(user.id)
    if workspace_id:
        query = query.where(Task.workspace_id == workspace_id)
    if project_id:
        query = query.where(Task.project_id == project_id)
    if scope == 'assigned':
        query = query.where(
            exists(
                select(TaskAssignee.id).where(
                    TaskAssignee.task_id == Task.id,
                    TaskAssignee.user_id == user.id,
                )
            )
        )
    elif scope == 'created':
        query = query.where(Task.reporter_id == user.id)
    elif scope == 'watching':
        query = query.where(
            exists(
                select(TaskWatcher.id).where(
                    TaskWatcher.task_id == Task.id,
                    TaskWatcher.user_id == user.id,
                )
            )
        )
    if status:
        query = query.where(Task.status == status)
    if priority:
        query = query.where(Task.priority == priority)
    if due_before:
        query = query.where(Task.due_date <= due_before)
    if due_after:
        query = query.where(Task.due_date >= due_after)
    if assignee_id:
        query = query.where(
            exists(
                select(TaskAssignee.id).where(
                    TaskAssignee.task_id == Task.id,
                    TaskAssignee.user_id == assignee_id,
                )
            )
        )
    if label_id:
        query = query.where(
            exists(
                select(TaskLabel.id).where(
                    TaskLabel.task_id == Task.id,
                    TaskLabel.label_id == label_id,
                )
            )
        )

    count_query = select(func.count()).select_from(query.order_by(None).subquery())
    total = int(await db.scalar(count_query) or 0)
    priority_order = case(
        (Task.priority == 'urgent', 0),
        (Task.priority == 'high', 1),
        (Task.priority == 'medium', 2),
        (Task.priority == 'low', 3),
        else_=4,
    )
    sort_columns = {
        'due_date': Task.due_date,
        'priority': priority_order,
        'created_at': Task.created_at,
        'updated_at': Task.updated_at,
    }
    order = sort_columns[sort_by]
    order = order.desc() if sort_direction == 'desc' else order.asc()
    if sort_by == 'due_date':
        order = order.nulls_last()
    tasks = list(
        (await db.scalars(query.order_by(order, Task.id).limit(limit).offset(offset))).all()
    )
    return TaskPage(
        items=[TaskOut.model_validate(task) for task in tasks],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get('/calendar', response_model=list[CalendarItem])
async def calendar(
    start: datetime,
    end: datetime,
    workspace_id: UUID | None = None,
    project_id: UUID | None = None,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    if end <= start:
        raise HTTPException(status_code=422, detail='Calendar end must be after start')
    if project_id:
        project, _ = await require_project(db, project_id, user.id)
        if workspace_id and project.workspace_id != workspace_id:
            raise HTTPException(status_code=400, detail='Project does not belong to workspace')
    elif workspace_id:
        await require_workspace(db, workspace_id, user.id)

    task_query = _task_query(user.id).where(Task.due_date >= start, Task.due_date < end)
    if workspace_id:
        task_query = task_query.where(Task.workspace_id == workspace_id)
    if project_id:
        task_query = task_query.where(Task.project_id == project_id)
    tasks = list((await db.scalars(task_query.order_by(Task.due_date))).all())

    items = [
        CalendarItem(
            id=f'task:{task.id}',
            kind='task',
            title=task.title,
            starts_at=task.due_date,
            workspace_id=task.workspace_id,
            project_id=task.project_id,
            task_id=task.id,
            identifier=task.identifier,
            priority=task.priority,
            status=task.status,
        )
        for task in tasks
        if task.due_date is not None
    ]

    project_query = (
        select(Project)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Project.workspace_id)
        .where(
            WorkspaceMember.user_id == user.id,
            Project.due_date.is_not(None),
            or_(
                WorkspaceMember.role != 'guest',
                exists(
                    select(ProjectMember.id).where(
                        ProjectMember.project_id == Project.id,
                        ProjectMember.user_id == user.id,
                    )
                ),
            ),
        )
    )
    if workspace_id:
        project_query = project_query.where(Project.workspace_id == workspace_id)
    if project_id:
        project_query = project_query.where(Project.id == project_id)
    projects = list((await db.scalars(project_query)).all())
    for project in projects:
        if project.due_date is None:
            continue
        project_due = datetime.combine(project.due_date, time.min, tzinfo=UTC)
        if start <= project_due < end:
            items.append(
                CalendarItem(
                    id=f'project:{project.id}',
                    kind='project',
                    title=f'{project.name} deadline',
                    starts_at=project_due,
                    workspace_id=project.workspace_id,
                    project_id=project.id,
                    status=project.status,
                )
            )
    return sorted(items, key=lambda item: item.starts_at)


@router.get('/projects/{project_id}/timeline', response_model=TimelineOut)
async def project_timeline(
    project_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_project(db, project_id, user.id)
    tasks = list(
        (
            await db.scalars(
                select(Task)
                .where(Task.project_id == project_id, Task.deleted_at.is_(None))
                .order_by(Task.due_date.asc().nulls_last(), Task.created_at)
            )
        ).all()
    )
    task_ids = [task.id for task in tasks]
    dependencies = []
    if task_ids:
        dependencies = list(
            (
                await db.scalars(
                    select(TaskDependency).where(TaskDependency.blocked_task_id.in_(task_ids))
                )
            ).all()
        )
    blocked_by: dict[UUID, list[UUID]] = {}
    for dependency in dependencies:
        blocked_by.setdefault(dependency.blocked_task_id, []).append(dependency.blocker_task_id)
    return TimelineOut(
        project_id=project_id,
        tasks=[
            TimelineTask(
                id=task.id,
                identifier=task.identifier,
                title=task.title,
                status=task.status,
                priority=task.priority,
                start_at=task.created_at,
                due_at=task.due_date,
                blocked_by=blocked_by.get(task.id, []),
            )
            for task in tasks
        ],
    )
