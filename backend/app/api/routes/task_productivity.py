import json
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, require_project, require_workspace
from app.db import get_db
from app.models import Task, User, WorkspaceMember
from app.productivity_models import CustomField, CustomFieldValue, TimeEntry
from app.productivity_schemas import (
    CustomFieldCreate,
    CustomFieldOut,
    CustomFieldPatch,
    CustomFieldValueSet,
    TaskCustomFieldValue,
    TimeEntryManual,
    TimeEntryOut,
    TimeSummary,
)
from app.realtime import publish

router = APIRouter(tags=['task-productivity'])


async def _task_access(
    db: AsyncSession,
    task_id: UUID,
    user_id: UUID,
    *,
    write: bool = False,
) -> Task:
    task = await db.get(Task, task_id)
    if not task or task.deleted_at is not None:
        raise HTTPException(status_code=404, detail='Task not found')
    await require_project(db, task.project_id, user_id, write=write)
    return task


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


def _custom_field_out(field: CustomField) -> CustomFieldOut:
    return CustomFieldOut(
        id=field.id,
        workspace_id=field.workspace_id,
        name=field.name,
        field_type=field.field_type,
        options=json.loads(field.options_json or '[]'),
        required=field.required,
        position=field.position,
        created_at=field.created_at,
        updated_at=field.updated_at,
    )


@router.get('/tasks/{task_id}/time', response_model=TimeSummary)
async def task_time(
    task_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await _task_access(db, task_id, user.id)
    entries = list(
        (
            await db.scalars(
                select(TimeEntry)
                .where(TimeEntry.task_id == task_id)
                .order_by(TimeEntry.started_at.desc())
            )
        ).all()
    )
    total = sum(entry.duration_seconds or 0 for entry in entries)
    running = next(
        (
            entry
            for entry in entries
            if entry.user_id == user.id and entry.ended_at is None
        ),
        None,
    )
    return TimeSummary(
        entries=[_time_entry_out(entry) for entry in entries],
        total_seconds=total,
        running_entry=_time_entry_out(running) if running else None,
    )


@router.post('/tasks/{task_id}/time/start', response_model=TimeEntryOut, status_code=201)
async def start_timer(
    task_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await _task_access(db, task_id, user.id, write=True)
    running = await db.scalar(
        select(TimeEntry).where(
            TimeEntry.user_id == user.id,
            TimeEntry.ended_at.is_(None),
        )
    )
    if running:
        raise HTTPException(
            status_code=409,
            detail='Stop your running timer before starting another',
        )
    entry = TimeEntry(
        task_id=task_id,
        user_id=user.id,
        started_at=datetime.now(UTC),
    )
    db.add(entry)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail='A timer is already running') from None
    await db.refresh(entry)
    return _time_entry_out(entry)


@router.post('/tasks/{task_id}/time/stop', response_model=TimeEntryOut)
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
        raise HTTPException(status_code=404, detail='No running timer for this task')
    ended_at = datetime.now(UTC)
    entry.ended_at = ended_at
    entry.duration_seconds = max(0, int((ended_at - entry.started_at).total_seconds()))
    await db.commit()
    await db.refresh(entry)
    await publish(task.workspace_id, 'time.updated', {'task_id': str(task.id)})
    return _time_entry_out(entry)


@router.post('/tasks/{task_id}/time', response_model=TimeEntryOut, status_code=201)
async def add_manual_time(
    task_id: UUID,
    data: TimeEntryManual,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _task_access(db, task_id, user.id, write=True)
    duration = int((data.ended_at - data.started_at).total_seconds())
    if duration > 60 * 60 * 24 * 31:
        raise HTTPException(
            status_code=422,
            detail='A single manual time entry cannot exceed 31 days',
        )
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
    await publish(task.workspace_id, 'time.updated', {'task_id': str(task.id)})
    return _time_entry_out(entry)


@router.delete('/tasks/{task_id}/time/{entry_id}', status_code=204)
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
        raise HTTPException(status_code=404, detail='Time entry not found')
    await db.delete(entry)
    await db.commit()


@router.get(
    '/workspaces/{workspace_id}/custom-fields',
    response_model=list[CustomFieldOut],
)
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


@router.post(
    '/workspaces/{workspace_id}/custom-fields',
    response_model=CustomFieldOut,
    status_code=201,
)
async def create_custom_field(
    workspace_id: UUID,
    data: CustomFieldCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace(db, workspace_id, user.id, {'owner', 'admin'})
    field = CustomField(
        workspace_id=workspace_id,
        name=data.name.strip(),
        field_type=data.field_type,
        options_json=json.dumps(data.options, separators=(',', ':')),
        required=data.required,
        position=data.position,
    )
    db.add(field)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail='Custom field name already exists',
        ) from None
    await db.refresh(field)
    return _custom_field_out(field)


@router.patch(
    '/workspaces/{workspace_id}/custom-fields/{field_id}',
    response_model=CustomFieldOut,
)
async def patch_custom_field(
    workspace_id: UUID,
    field_id: UUID,
    data: CustomFieldPatch,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace(db, workspace_id, user.id, {'owner', 'admin'})
    field = await db.scalar(
        select(CustomField).where(
            CustomField.id == field_id,
            CustomField.workspace_id == workspace_id,
        )
    )
    if not field:
        raise HTTPException(status_code=404, detail='Custom field not found')
    values = data.model_dump(exclude_unset=True)
    if values.get('name') is not None:
        field.name = values['name'].strip()
    if values.get('options') is not None:
        if field.field_type != 'dropdown':
            raise HTTPException(
                status_code=422,
                detail='Only dropdown fields can have options',
            )
        options = values['options']
        if not options or len(set(options)) != len(options):
            raise HTTPException(
                status_code=422,
                detail='Dropdown options must be non-empty and unique',
            )
        field.options_json = json.dumps(options, separators=(',', ':'))
    for attr in ('required', 'position'):
        if values.get(attr) is not None:
            setattr(field, attr, values[attr])
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail='Custom field name already exists',
        ) from None
    await db.refresh(field)
    return _custom_field_out(field)


@router.delete('/workspaces/{workspace_id}/custom-fields/{field_id}', status_code=204)
async def delete_custom_field(
    workspace_id: UUID,
    field_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace(db, workspace_id, user.id, {'owner', 'admin'})
    field = await db.scalar(
        select(CustomField).where(
            CustomField.id == field_id,
            CustomField.workspace_id == workspace_id,
        )
    )
    if not field:
        raise HTTPException(status_code=404, detail='Custom field not found')
    await db.delete(field)
    await db.commit()


async def _validate_custom_field_value(
    db: AsyncSession,
    field: CustomField,
    value: Any,
) -> Any:
    if value is None:
        if field.required:
            raise HTTPException(status_code=422, detail=f'{field.name} is required')
        return None
    if field.field_type in {'text', 'url', 'date'} and not isinstance(value, str):
        raise HTTPException(status_code=422, detail=f'{field.name} must be a string')
    if field.field_type == 'number' and (
        not isinstance(value, (int, float)) or isinstance(value, bool)
    ):
        raise HTTPException(status_code=422, detail=f'{field.name} must be a number')
    if field.field_type == 'checkbox' and not isinstance(value, bool):
        raise HTTPException(
            status_code=422,
            detail=f'{field.name} must be true or false',
        )
    if field.field_type == 'dropdown':
        options = json.loads(field.options_json or '[]')
        if value not in options:
            raise HTTPException(
                status_code=422,
                detail=f'{field.name} must be one of its configured options',
            )
    if field.field_type == 'url':
        parsed = urlparse(value)
        if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
            raise HTTPException(
                status_code=422,
                detail=f'{field.name} must be an http(s) URL',
            )
    if field.field_type == 'date':
        try:
            datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f'{field.name} must be an ISO date/time',
            ) from None
    if field.field_type == 'user':
        try:
            member_id = UUID(str(value))
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f'{field.name} must contain a user id',
            ) from None
        member = await db.scalar(
            select(WorkspaceMember.id).where(
                WorkspaceMember.workspace_id == field.workspace_id,
                WorkspaceMember.user_id == member_id,
            )
        )
        if member is None:
            raise HTTPException(
                status_code=422,
                detail=f'{field.name} user must belong to the workspace',
            )
        return str(member_id)
    return value


@router.get(
    '/tasks/{task_id}/custom-fields',
    response_model=list[TaskCustomFieldValue],
)
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
            await db.scalars(
                select(CustomFieldValue).where(CustomFieldValue.task_id == task.id)
            )
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


@router.put(
    '/tasks/{task_id}/custom-fields/{field_id}',
    response_model=TaskCustomFieldValue,
)
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
        raise HTTPException(status_code=404, detail='Custom field not found')
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
        await publish(
            task.workspace_id,
            'task.custom_field.updated',
            {'task_id': str(task.id), 'field_id': str(field.id)},
        )
        return TaskCustomFieldValue(
            field=_custom_field_out(field),
            value=None,
            updated_at=None,
        )
    payload = json.dumps(normalized, separators=(',', ':'))
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
    await publish(
        task.workspace_id,
        'task.custom_field.updated',
        {'task_id': str(task.id), 'field_id': str(field.id)},
    )
    return TaskCustomFieldValue(
        field=_custom_field_out(field),
        value=normalized,
        updated_at=value.updated_at,
    )
