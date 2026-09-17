import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, require_project, require_workspace
from app.db import get_db
from app.models import Task, User
from app.productivity_models import Favorite, RecentItem, SavedView
from app.productivity_schemas import (
    FavoriteCreate,
    FavoriteOut,
    RecentItemCreate,
    RecentItemOut,
    SavedViewCreate,
    SavedViewOut,
    SavedViewPatch,
)

router = APIRouter(tags=['personalization'])


def _saved_view_out(view: SavedView) -> SavedViewOut:
    return SavedViewOut(
        id=view.id,
        workspace_id=view.workspace_id,
        project_id=view.project_id,
        name=view.name,
        filters=json.loads(view.filters_json or '{}'),
        sort_by=view.sort_by,
        sort_direction=view.sort_direction,
        display_mode=view.display_mode,
        created_at=view.created_at,
        updated_at=view.updated_at,
    )


async def _require_entity_access(
    db: AsyncSession,
    user_id: UUID,
    workspace_id: UUID,
    entity_type: str,
    entity_id: UUID,
) -> None:
    await require_workspace(db, workspace_id, user_id)
    if entity_type in {'project', 'board'}:
        project, _ = await require_project(db, entity_id, user_id)
        if project.workspace_id != workspace_id:
            raise HTTPException(status_code=400, detail='Entity does not belong to workspace')
        return
    if entity_type == 'task':
        task = await db.get(Task, entity_id)
        if not task or task.deleted_at is not None:
            raise HTTPException(status_code=404, detail='Task not found')
        await require_project(db, task.project_id, user_id)
        if task.workspace_id != workspace_id:
            raise HTTPException(status_code=400, detail='Entity does not belong to workspace')
        return
    if entity_type == 'saved_view':
        view = await db.scalar(
            select(SavedView).where(SavedView.id == entity_id, SavedView.user_id == user_id)
        )
        if not view or view.workspace_id != workspace_id:
            raise HTTPException(status_code=404, detail='Saved view not found')
        return
    raise HTTPException(status_code=400, detail='Unsupported entity type')


@router.get('/saved-views', response_model=list[SavedViewOut])
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


@router.post('/saved-views', response_model=SavedViewOut, status_code=201)
async def create_saved_view(
    data: SavedViewCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace(db, data.workspace_id, user.id)
    if data.project_id:
        project, _ = await require_project(db, data.project_id, user.id)
        if project.workspace_id != data.workspace_id:
            raise HTTPException(status_code=400, detail='Project does not belong to workspace')
    view = SavedView(
        user_id=user.id,
        workspace_id=data.workspace_id,
        project_id=data.project_id,
        name=data.name.strip(),
        filters_json=json.dumps(data.filters, separators=(',', ':'), sort_keys=True),
        sort_by=data.sort_by,
        sort_direction=data.sort_direction,
        display_mode=data.display_mode,
    )
    db.add(view)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail='A saved view with this name already exists',
        ) from None
    await db.refresh(view)
    return _saved_view_out(view)


@router.patch('/saved-views/{view_id}', response_model=SavedViewOut)
async def patch_saved_view(
    view_id: UUID,
    data: SavedViewPatch,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    view = await db.scalar(
        select(SavedView).where(SavedView.id == view_id, SavedView.user_id == user.id)
    )
    if not view:
        raise HTTPException(status_code=404, detail='Saved view not found')
    values = data.model_dump(exclude_unset=True)
    if values.get('name') is not None:
        view.name = values['name'].strip()
    if values.get('filters') is not None:
        view.filters_json = json.dumps(
            values['filters'], separators=(',', ':'), sort_keys=True
        )
    for field in ('sort_by', 'sort_direction', 'display_mode'):
        if values.get(field) is not None:
            setattr(view, field, values[field])
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail='A saved view with this name already exists',
        ) from None
    await db.refresh(view)
    return _saved_view_out(view)


@router.delete('/saved-views/{view_id}', status_code=204)
async def delete_saved_view(
    view_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    view = await db.scalar(
        select(SavedView).where(SavedView.id == view_id, SavedView.user_id == user.id)
    )
    if not view:
        raise HTTPException(status_code=404, detail='Saved view not found')
    await db.delete(view)
    await db.commit()


@router.get('/favorites', response_model=list[FavoriteOut])
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


@router.post('/favorites', response_model=FavoriteOut, status_code=201)
async def create_favorite(
    data: FavoriteCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_entity_access(
        db, user.id, data.workspace_id, data.entity_type, data.entity_id
    )
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


@router.delete('/favorites/{favorite_id}', status_code=204)
async def delete_favorite(
    favorite_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    favorite = await db.scalar(
        select(Favorite).where(Favorite.id == favorite_id, Favorite.user_id == user.id)
    )
    if not favorite:
        raise HTTPException(status_code=404, detail='Favorite not found')
    await db.delete(favorite)
    await db.commit()


@router.get('/recent-items', response_model=list[RecentItemOut])
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


@router.post('/recent-items', response_model=RecentItemOut)
async def touch_recent_item(
    data: RecentItemCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_entity_access(
        db, user.id, data.workspace_id, data.entity_type, data.entity_id
    )
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
