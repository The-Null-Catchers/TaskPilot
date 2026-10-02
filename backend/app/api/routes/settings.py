from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, require_project, require_workspace
from app.db import get_db
from app.models import Project, User
from app.settings_models import ProjectSetting, UserSetting, WorkspaceSetting
from app.settings_schemas import (
    ProjectSettingOut,
    ProjectSettingPatch,
    UserSettingOut,
    UserSettingPatch,
    WorkspaceSettingOut,
    WorkspaceSettingPatch,
)

router = APIRouter(tags=["settings"])


async def _user_setting(db: AsyncSession, user_id: UUID) -> UserSetting:
    setting = await db.get(UserSetting, user_id)
    if setting is None:
        setting = UserSetting(user_id=user_id)
        db.add(setting)
        await db.commit()
        await db.refresh(setting)
    return setting


async def _workspace_setting(db: AsyncSession, workspace_id: UUID) -> WorkspaceSetting:
    setting = await db.get(WorkspaceSetting, workspace_id)
    if setting is None:
        setting = WorkspaceSetting(workspace_id=workspace_id)
        db.add(setting)
        await db.commit()
        await db.refresh(setting)
    return setting


async def _project_setting(db: AsyncSession, project_id: UUID) -> ProjectSetting:
    setting = await db.get(ProjectSetting, project_id)
    if setting is None:
        setting = ProjectSetting(project_id=project_id)
        db.add(setting)
        await db.commit()
        await db.refresh(setting)
    return setting


@router.get("/settings/user", response_model=UserSettingOut)
async def get_user_settings(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _user_setting(db, user.id)


@router.patch("/settings/user", response_model=UserSettingOut)
async def patch_user_settings(
    data: UserSettingPatch,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    setting = await _user_setting(db, user.id)
    for field, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(setting, field, value)
    await db.commit()
    await db.refresh(setting)
    return setting


@router.get(
    "/workspaces/{workspace_id}/settings",
    response_model=WorkspaceSettingOut,
)
async def get_workspace_settings(
    workspace_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace(db, workspace_id, user.id)
    return await _workspace_setting(db, workspace_id)


@router.patch(
    "/workspaces/{workspace_id}/settings",
    response_model=WorkspaceSettingOut,
)
async def patch_workspace_settings(
    workspace_id: UUID,
    data: WorkspaceSettingPatch,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace(db, workspace_id, user.id, {"owner", "admin"})
    setting = await _workspace_setting(db, workspace_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(setting, field, value)
    await db.commit()
    await db.refresh(setting)
    return setting


@router.get("/projects/{project_id}/settings/preferences", response_model=ProjectSettingOut)
async def get_project_settings(
    project_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_project(db, project_id, user.id)
    return await _project_setting(db, project_id)


@router.patch("/projects/{project_id}/settings/preferences", response_model=ProjectSettingOut)
async def patch_project_settings(
    project_id: UUID,
    data: ProjectSettingPatch,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project, _ = await require_project(db, project_id, user.id)
    workspace_role = await require_workspace(db, project.workspace_id, user.id)
    if project.owner_id != user.id and workspace_role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Project management access required")
    setting = await _project_setting(db, project_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(setting, field, value)
    await db.commit()
    await db.refresh(setting)
    return setting
