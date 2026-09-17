import json
from datetime import UTC, datetime, time
from typing import Any, Literal
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, delete, exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, require_project, require_workspace
from app.collaboration_models import ProjectMember, TaskDependency, TaskWatcher
from app.db import get_db
from app.models import Project, Task, TaskAssignee, TaskLabel, User, WorkspaceMember
from app.productivity_models import (
    CustomField,
    CustomFieldValue,
    Favorite,
    RecentItem,
    SavedView,
    TimeEntry,
)
from app.productivity_schemas import (
    CalendarItem,
    CustomFieldCreate,
    CustomFieldOut,
    CustomFieldPatch,
    CustomFieldValueSet,
    FavoriteCreate,
    FavoriteOut,
    RecentItemCreate,
    RecentItemOut,
    SavedViewCreate,
    SavedViewOut,
    SavedViewPatch,
    TaskCustomFieldValue,
    TaskPage,
    TimelineOut,
    TimelineTask,
    TimeEntryManual,
    TimeEntryOut,
    TimeSummary,
)
from app.realtime import publish
from app.schemas import TaskOut

router = APIRouter(tags=["productivity"])


def _accessible_task_predicate(user_id: UUID):
    guest_project_access = exists(
        select(ProjectMember.id).where(
            ProjectMember.project_id == Task.project_id,
            ProjectMember.user_id == user_id,
        )
    )
    return or_(WorkspaceMember.role != "guest", guest_project_access)


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


async def _task_access(
    db: AsyncSession, task_id: UUID, user_id: UUID, *, write: bool = False
) -> Task:
    task = await db.get(Task, task_id)
    if not task or task.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Task not found")
    await require_project(db, task.project_id, user_id, write=write)
    return task


async def _validate_entity(
    db: AsyncSession,
    user_id: UUID,
    workspace_id: UUID,
    entity_type: str,
    entity_id: UUID,
) -> None:
    await require_workspace(db, workspace_id, user_id)
    if entity_type in {"project", "board"}:
        project, _ = await require_project(db, entity_id, user_id)
        if project.workspace_id != workspace_id:
            raise HTTPException(status_code=400, detail="Entity does not belong to workspace")
        return
    if entity_type == "task":
        task = await _task_access(db, entity_id, user_id)
        if task.workspace_id != workspace_id:
            raise HTTPException(status_code=400, detail="Entity does not belong to workspace")
        return
    if entity_type == "saved_view":
        view = await db.scalar(
            select(SavedView).where(SavedView.id == entity_id, SavedView.user_id == user_id)
        )
        if not view or view.workspace_id != workspace_id:
            raise HTTPException(status_code=404, detail="Saved view not found")
        return
    raise HTTPException(status_code=400, detail="Unsupported entity type")


def _saved_view_out(view: SavedView) -> SavedViewOut:
    return SavedViewOut(
        id=view.id,
        workspace_id=view.workspace_id,
        project_id=view.project_id,
        name=view.name,
        filters=json.loads(view.filters_json or "{}"),
        sort_by=view.sort_by,
        sort_direction=view.sort_direction,
        display_mode=view.display_mode,
        created_at=view.created_at,
        updated_at=view.updated_at,
    )


def _custom_field_out(field: CustomField) -> CustomFieldOut:
    return CustomFieldOut(
        id=field.id,
        workspace_id=field.workspace_id,
        name=field.name,
        field_type=field.field_type,
        options=json.loads(field.options_json or "[]"),
        required=field.required,
        position=field.position,
        created_at=field.created_at,
        updated_at=field.updated_at,
    )


def _time_entry_out(entry: TimeEntry) -> TimeEntryOut:
    return TimeEntryOut(
        id=entry.id,
        task_id=entry.task_id,
        user_id=entry.user_id,
        started_at=entry.started_at,
        ended_at=entry.ended_at,
        duration_seconds=entry.duration_seconds,
        note=entry.note,
        created_at=entry.created_at,
    )


@router.get("/my-tasks", response_model=TaskPage)
async def my_tasks(
    workspace_id: UUID | None = None,
    project_id: UUID | None = None,
    scope: Literal["assigned", "created", "watching", "all"] = "assigned",
    status: str | None = None,
    priority: str | None = None,
    due_before: datetime | None = None,
    due_after: datetime | None = None,
    assignee_id: UUID | None = None,
    label_id: UUID | None = None,
    sort_by: Literal["due_date", "priority", "created_at", "updated_at"] = "due_date",
    sort_direction: Literal["asc", "desc"] = "asc",
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
            raise HTTPException(status_code=400, detail="Project does not belong to workspace")

    query = _task_query(user.id)
    if workspace_id:
        query = query.where(Task.workspace_id == workspace_id)
    if project_id:
        query = query.where(Task.project_id == project_id)
    if scope == "assigned":
        query = query.where(
            exists(
                select(TaskAssignee.id).where(
                    TaskAssignee.task_id == Task.id,
                    TaskAssignee.user_id == user.id,
                )
            )
        )
    elif scope == "created":
        query = query.where(Task.reporter_id == user.id)
    elif scope == "watching":
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
        (Task.priority == "urgent", 0),
        (Task.priority == "high", 1),
        (Task.priority == "medium", 2),
        (Task.priority == "low", 3),
        else_=4,
    )
    sort_columns = {
        "due_date": Task.due_date,
        "priority": priority_order,
        "created_at": Task.created_at,
        "updated_at": Task.updated_at,
    }
    order = sort_columns[sort_by]
    order = order.desc() if sort_direction == "desc" else order.asc()
    if sort_by == "due_date":
        order = order.nulls_last()
    tasks = list((await db.scalars(query.order_by(order, Task.id).limit(limit).offset(offset))).all())
    return TaskPage(
        items=[TaskOut.model_validate(task) for task in tasks],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/calendar", response_model=list[CalendarItem])
async def calendar(
    start: datetime,
    end: datetime,
    workspace_id: UUID | None = None,
    project_id: UUID | None = None,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    if end <= start:
        raise HTTPException(status_code=422, detail="Calendar end must be after start")
    if project_id:
        project, _ = await require_project(db, project_id, user.id)
        if workspace_id and project.workspace_id != workspace_id:
            raise HTTPException(status_code=400, detail="Project does not belong to workspace")
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
            id=f"task:{task.id}",
            kind="task",
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
                WorkspaceMember.role != "guest",
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
                    id=f"project:{project.id}",
                    kind="project",
                    title=f"{project.name} deadline",
                    starts_at=project_due,
                    workspace_id=project.workspace_id,
                    project_id=project.id,
                    status=project.status,
                )
            )
    return sorted(items, key=lambda item: item.starts_at)


@router.get("/projects/{project_id}/timeline", response_model=TimelineOut)
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


@router.get("/saved-views", response_model=list[SavedViewOut])
async def list_saved_views(
    workspace_id: UUID | None = None,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(SavedView).where(SavedView.user_id == user.id)
    if workspace_id:
        await require_workspace(db, workspace_id, user.id)
        query = query.where(SavedView.workspace_id == workspace_id)
    views = list((await db.scalars(query.order_by(SavedView.updated_at.desc()))).all())
    return [_saved_view_out(view) for view in views]


@router.post("/saved-views", response_model=SavedViewOut, status_code=201)
async def create_saved_view(
    data: SavedViewCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace(db, data.workspace_id, user.id)
    if data.project_id:
        project, _ = await require_project(db, data.project_id, user.id)
        if project.workspace_id != data.workspace_id:
            raise HTTPException(status_code=400, detail="Project does not belong to workspace")
    view = SavedView(
        user_id=user.id,
        workspace_id=data.workspace_id,
        project_id=data.project_id,
        name=data.name.strip(),
        filters_json=json.dumps(data.filters, separators=(",", ":"), sort_keys=True),
        sort_by=data.sort_by,
        sort_direction=data.sort_direction,
        display_mode=data.display_mode,
    )
    db.add(view)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="A saved view with this name already exists") from None
    await db.refresh(view)
    return _saved_view_out(view)


@router.patch("/saved-views/{view_id}", response_model=SavedViewOut)
async def patch_saved_view(
    view_id: UUID,
    data: SavedViewPatch,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    view = await db.scalar(select(SavedView).where(SavedView.id == view_id, SavedView.user_id == user.id))
    if not view:
        raise HTTPException(status_code=404, detail="Saved view not found")
    values = data.model_dump(exclude_unset=True)
    if "name" in values and values["name"] is not None:
        view.name = values["name"].strip()
    if "filters" in values and values["filters"] is not None:
        view.filters_json = json.dumps(values["filters"], separators=(",", ":"), sort_keys=True)
    for field in ("sort_by", "sort_direction", "display_mode"):
        if values.get(field) is not None:
            setattr(view, field, values[field])
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="A saved view with this name already exists") from None
    await db.refresh(view)
    return _saved_view_out(view)


@router.delete("/saved-views/{view_id}", status_code=204)
async def delete_saved_view(
    view_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    view = await db.scalar(select(SavedView).where(SavedView.id == view_id, SavedView.user_id == user.id))
    if not view:
        raise HTTPException(status_code=404, detail="Saved view not found")
    await db.delete(view)
    await db.commit()


@router.get("/favorites", response_model=list[FavoriteOut])
async def list_favorites(
    workspace_id: UUID | None = None,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Favorite).where(Favorite.user_id == user.id)
    if workspace_id:
        await require_workspace(db, workspace_id, user.id)
        query = query.where(Favorite.workspace_id == workspace_id)
    return list((await db.scalars(query.order_by(Favorite.created_at.desc()))).all())


@router.post("/favorites", response_model=FavoriteOut, status_code=201)
async def create_favorite(
    data: FavoriteCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await _validate_entity(db, user.id, data.workspace_id, data.entity_type, data.entity_id)
    favorite = await db.scalar(
        select(Favorite).where(
            Favorite.user_id == user.id,
            Favorite.entity_type == data.entity_type,
            Favorite.entity_id == data.entity_id,
        )
    )
    if favorite:
        return favorite
    favorite = Favorite(user_id=user.id, **data.model_dump())
    db.add(favorite)
    await db.commit()
    await db.refresh(favorite)
    return favorite


@router.delete("/favorites/{favorite_id}", status_code=204)
async def delete_favorite(
    favorite_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    favorite = await db.scalar(
        select(Favorite).where(Favorite.id == favorite_id, Favorite.user_id == user.id)
    )
    if not favorite:
        raise HTTPException(status_code=404, detail="Favorite not found")
    await db.delete(favorite)
    await db.commit()


@router.get("/recent-items", response_model=list[RecentItemOut])
async def list_recent_items(
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    return list(
        (
            await db.scalars(
                select(RecentItem)
                .where(RecentItem.user_id == user.id)
                .order_by(RecentItem.viewed_at.desc())
                .limit(limit)
            )
        ).all()
    )


@router.post("/recent-items", response_model=RecentItemOut)
async def touch_recent_item(
    data: RecentItemCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await _validate_entity(db, user.id, data.workspace_id, data.entity_type, data.entity_id)
    item = await db.scalar(
        select(RecentItem).where(
            RecentItem.user_id == user.id,
            RecentItem.entity_type == data.entity_type,
            RecentItem.entity_id == data.entity_id,
        )
    )
    if item:
        item.workspace_id = data.workspace_id
        item.viewed_at = datetime.now(UTC)
    else:
        item = RecentItem(user_id=user.id, **data.model_dump())
        db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.get("/tasks/{task_id}/time", response_model=TimeSummary)
async def task_time(
    task_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await _task_access(db, task_id, user.id)
    entries = list(
        (
            await db.scalars(
                select(TimeEntry).where(TimeEntry.task_id == task_id).order_by(TimeEntry.started_at.desc())
            )
        ).all()
    )
    total = sum(entry.duration_seconds or 0 for entry in entries)
    running = next((entry for entry in entries if entry.user_id == user.id and entry.ended_at is None), None)
    return TimeSummary(
        entries=[_time_entry_out(entry) for entry in entries],
        total_seconds=total,
        running_entry=_time_entry_out(running) if running else None,
    )


@router.post("/tasks/{task_id}/time/start", response_model=TimeEntryOut, status_code=201)
async def start_timer(
    task_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await _task_access(db, task_id, user.id, write=True)
    running = await db.scalar(
        select(TimeEntry).where(TimeEntry.user_id == user.id, TimeEntry.ended_at.is_(None))
    )
    if running:
        raise HTTPException(status_code=409, detail="Stop your running timer before starting another")
    entry = TimeEntry(task_id=task_id, user_id=user.id, started_at=datetime.now(UTC))
    db.add(entry)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="A timer is already running") from None
    await db.refresh(entry)
    return _time_entry_out(entry)


@router.post("/tasks/{task_id}/time/stop", response_model=TimeEntryOut)
async def stop_timer(
    task_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _task_access(db, task_id, user.id, write=True)
    entry = await db.scalar(
        select(TimeEntry).where(
            TimeEntry.task_id == task_id,
            TimeEntry.user_id == user.id,
            TimeEntry.ended_at.is_(None),
        )
    )
    if not entry:
        raise HTTPException(status_code=404, detail="No running timer for this task")
    ended_at = datetime.now(UTC)
    entry.ended_at = ended_at
    entry.duration_seconds = max(0, int((ended_at - entry.started_at).total_seconds()))
    await db.commit()
    await db.refresh(entry)
    await publish(task.workspace_id, "time.updated", {"task_id": str(task.id)})
    return _time_entry_out(entry)


@router.post("/tasks/{task_id}/time", response_model=TimeEntryOut, status_code=201)
async def add_manual_time(
    task_id: UUID,
    data: TimeEntryManual,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _task_access(db, task_id, user.id, write=True)
    duration = int((data.ended_at - data.started_at).total_seconds())
    if duration > 60 * 60 * 24 * 31:
        raise HTTPException(status_code=422, detail="A single manual time entry cannot exceed 31 days")
    entry = TimeEntry(
        task_id=task_id,
        user_id=user.id,
        started_at=data.started_at,
        ended_at=data.ended_at,
        duration_seconds=duration,
        note=data.note.strip(),
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    await publish(task.workspace_id, "time.updated", {"task_id": str(task.id)})
    return _time_entry_out(entry)


@router.delete("/tasks/{task_id}/time/{entry_id}", status_code=204)
async def delete_time_entry(
    task_id: UUID,
    entry_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await _task_access(db, task_id, user.id, write=True)
    entry = await db.scalar(
        select(TimeEntry).where(
            TimeEntry.id == entry_id,
            TimeEntry.task_id == task_id,
            TimeEntry.user_id == user.id,
        )
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Time entry not found")
    await db.delete(entry)
    await db.commit()


@router.get("/workspaces/{workspace_id}/custom-fields", response_model=list[CustomFieldOut])
async def list_custom_fields(
    workspace_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace(db, workspace_id, user.id)
    fields = list(
        (
            await db.scalars(
                select(CustomField)
                .where(CustomField.workspace_id == workspace_id)
                .order_by(CustomField.position, CustomField.created_at)
            )
        ).all()
    )
    return [_custom_field_out(field) for field in fields]


@router.post("/workspaces/{workspace_id}/custom-fields", response_model=CustomFieldOut, status_code=201)
async def create_custom_field(
    workspace_id: UUID,
    data: CustomFieldCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace(db, workspace_id, user.id, {"owner", "admin"})
    field = CustomField(
        workspace_id=workspace_id,
        name=data.name.strip(),
        field_type=data.field_type,
        options_json=json.dumps(data.options, separators=(",", ":")),
        required=data.required,
        position=data.position,
    )
    db.add(field)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Custom field name already exists") from None
    await db.refresh(field)
    return _custom_field_out(field)


@router.patch("/workspaces/{workspace_id}/custom-fields/{field_id}", response_model=CustomFieldOut)
async def patch_custom_field(
    workspace_id: UUID,
    field_id: UUID,
    data: CustomFieldPatch,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace(db, workspace_id, user.id, {"owner", "admin"})
    field = await db.scalar(
        select(CustomField).where(CustomField.id == field_id, CustomField.workspace_id == workspace_id)
    )
    if not field:
        raise HTTPException(status_code=404, detail="Custom field not found")
    values = data.model_dump(exclude_unset=True)
    if values.get("name") is not None:
        field.name = values["name"].strip()
    if values.get("options") is not None:
        if field.field_type != "dropdown":
            raise HTTPException(status_code=422, detail="Only dropdown fields can have options")
        if not values["options"] or len(set(values["options"])) != len(values["options"]):
            raise HTTPException(status_code=422, detail="Dropdown options must be non-empty and unique")
        field.options_json = json.dumps(values["options"], separators=(",", ":"))
    for attr in ("required", "position"):
        if values.get(attr) is not None:
            setattr(field, attr, values[attr])
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Custom field name already exists") from None
    await db.refresh(field)
    return _custom_field_out(field)


@router.delete("/workspaces/{workspace_id}/custom-fields/{field_id}", status_code=204)
async def delete_custom_field(
    workspace_id: UUID,
    field_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace(db, workspace_id, user.id, {"owner", "admin"})
    field = await db.scalar(
        select(CustomField).where(CustomField.id == field_id, CustomField.workspace_id == workspace_id)
    )
    if not field:
        raise HTTPException(status_code=404, detail="Custom field not found")
    await db.delete(field)
    await db.commit()


async def _validate_custom_field_value(
    db: AsyncSession, field: CustomField, value: Any
) -> Any:
    if value is None:
        if field.required:
            raise HTTPException(status_code=422, detail=f"{field.name} is required")
        return None
    if field.field_type in {"text", "url", "date"} and not isinstance(value, str):
        raise HTTPException(status_code=422, detail=f"{field.name} must be a string")
    if field.field_type == "number" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
        raise HTTPException(status_code=422, detail=f"{field.name} must be a number")
    if field.field_type == "checkbox" and not isinstance(value, bool):
        raise HTTPException(status_code=422, detail=f"{field.name} must be true or false")
    if field.field_type == "dropdown":
        options = json.loads(field.options_json or "[]")
        if value not in options:
            raise HTTPException(status_code=422, detail=f"{field.name} must be one of its configured options")
    if field.field_type == "url":
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise HTTPException(status_code=422, detail=f"{field.name} must be an http(s) URL")
    if field.field_type == "date":
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=422, detail=f"{field.name} must be an ISO date/time") from None
    if field.field_type == "user":
        try:
            member_id = UUID(str(value))
        except ValueError:
            raise HTTPException(status_code=422, detail=f"{field.name} must contain a user id") from None
        member = await db.scalar(
            select(WorkspaceMember.id).where(
                WorkspaceMember.workspace_id == field.workspace_id,
                WorkspaceMember.user_id == member_id,
            )
        )
        if member is None:
            raise HTTPException(status_code=422, detail=f"{field.name} user must belong to the workspace")
        return str(member_id)
    return value


@router.get("/tasks/{task_id}/custom-fields", response_model=list[TaskCustomFieldValue])
async def task_custom_fields(
    task_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _task_access(db, task_id, user.id)
    fields = list(
        (
            await db.scalars(
                select(CustomField)
                .where(CustomField.workspace_id == task.workspace_id)
                .order_by(CustomField.position, CustomField.created_at)
            )
        ).all()
    )
    values = list(
        (
            await db.scalars(select(CustomFieldValue).where(CustomFieldValue.task_id == task.id))
        ).all()
    )
    by_field = {value.custom_field_id: value for value in values}
    return [
        TaskCustomFieldValue(
            field=_custom_field_out(field),
            value=json.loads(by_field[field.id].value_json) if field.id in by_field else None,
            updated_at=by_field[field.id].updated_at if field.id in by_field else None,
        )
        for field in fields
    ]


@router.put("/tasks/{task_id}/custom-fields/{field_id}", response_model=TaskCustomFieldValue)
async def set_task_custom_field(
    task_id: UUID,
    field_id: UUID,
    data: CustomFieldValueSet,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _task_access(db, task_id, user.id, write=True)
    field = await db.get(CustomField, field_id)
    if not field or field.workspace_id != task.workspace_id:
        raise HTTPException(status_code=404, detail="Custom field not found")
    normalized = await _validate_custom_field_value(db, field, data.value)
    value = await db.scalar(
        select(CustomFieldValue).where(
            CustomFieldValue.custom_field_id == field.id,
            CustomFieldValue.task_id == task.id,
        )
    )
    if normalized is None:
        if value:
            await db.delete(value)
            await db.commit()
        await publish(task.workspace_id, "task.custom_field.updated", {"task_id": str(task.id), "field_id": str(field.id)})
        return TaskCustomFieldValue(field=_custom_field_out(field), value=None, updated_at=None)
    payload = json.dumps(normalized, separators=(",", ":"))
    if value:
        value.value_json = payload
        value.updated_by_id = user.id
        value.updated_at = datetime.now(UTC)
    else:
        value = CustomFieldValue(
            custom_field_id=field.id,
            task_id=task.id,
            value_json=payload,
            updated_by_id=user.id,
        )
        db.add(value)
    await db.commit()
    await db.refresh(value)
    await publish(task.workspace_id, "task.custom_field.updated", {"task_id": str(task.id), "field_id": str(field.id)})
    return TaskCustomFieldValue(
        field=_custom_field_out(field),
        value=normalized,
        updated_at=value.updated_at,
    )
