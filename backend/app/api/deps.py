from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.collaboration_models import ProjectMember, WorkspaceArchive
from app.core.security import decode_access_token
from app.db import get_db
from app.integration_models import PersonalApiToken
from app.integration_security import personal_token_digest
from app.models import Project, User, WorkspaceMember

bearer = HTTPBearer(auto_error=False)


async def current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    raw = credentials.credentials
    if raw.startswith("tp_pat_"):
        token = await db.scalar(
            select(PersonalApiToken).where(
                PersonalApiToken.token_hash == personal_token_digest(raw),
                PersonalApiToken.revoked_at.is_(None),
            )
        )
        now = datetime.now(UTC)
        if not token or (token.expires_at is not None and token.expires_at <= now):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired API token",
            )
        scopes = {item for item in token.scopes.split(",") if item}
        if "read" not in scopes:
            raise HTTPException(status_code=403, detail="API token lacks read scope")
        if request.method.upper() not in {"GET", "HEAD", "OPTIONS"} and "write" not in scopes:
            raise HTTPException(status_code=403, detail="API token lacks write scope")
        should_touch = token.last_used_at is None or token.last_used_at <= now - timedelta(minutes=5)
        if should_touch:
            token.last_used_at = now
        user = await db.get(User, token.user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account unavailable",
            )
        if should_touch:
            await db.commit()
        return user

    try:
        user_id = decode_access_token(raw)
    except (jwt.InvalidTokenError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from None
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account unavailable",
        )
    return user


async def current_session_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials or credentials.credentials.startswith("tp_pat_"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Interactive session authentication required",
        )
    try:
        user_id = decode_access_token(credentials.credentials)
    except (jwt.InvalidTokenError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from None
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account unavailable",
        )
    return user


async def workspace_role(db: AsyncSession, workspace_id: UUID, user_id: UUID) -> str | None:
    return await db.scalar(
        select(WorkspaceMember.role).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )


async def require_workspace(
    db: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
    allowed: set[str] | None = None,
    *,
    allow_archived: bool = False,
    write: bool = False,
) -> str:
    role = await workspace_role(db, workspace_id, user_id)
    effective_allowed = allowed
    if write:
        writable = {"owner", "admin", "member"}
        effective_allowed = writable if effective_allowed is None else effective_allowed & writable
    if role is None or (effective_allowed is not None and role not in effective_allowed):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workspace access denied",
        )
    if not allow_archived:
        archived = await db.scalar(
            select(WorkspaceArchive.workspace_id).where(
                WorkspaceArchive.workspace_id == workspace_id
            )
        )
        if archived is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Workspace is archived",
            )
    return role


async def require_project(
    db: AsyncSession,
    project_id: UUID,
    user_id: UUID,
    *,
    write: bool = False,
) -> tuple[Project, str]:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    role = await require_workspace(db, project.workspace_id, user_id)
    if write and role not in {"owner", "admin", "member"}:
        raise HTTPException(status_code=403, detail="Project write access denied")

    if role == "guest":
        project_member = await db.scalar(
            select(ProjectMember.id).where(
                ProjectMember.project_id == project.id,
                ProjectMember.user_id == user_id,
            )
        )
        if project_member is None:
            raise HTTPException(status_code=403, detail="Project access denied")

    return project, role
