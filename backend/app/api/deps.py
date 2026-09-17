from uuid import UUID
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import decode_access_token
from app.db import get_db
from app.models import User, WorkspaceMember

bearer = HTTPBearer(auto_error=False)


async def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: AsyncSession = Depends(get_db)) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        user_id = decode_access_token(credentials.credentials)
    except (jwt.InvalidTokenError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from None
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account unavailable")
    return user


async def workspace_role(db: AsyncSession, workspace_id: UUID, user_id: UUID) -> str | None:
    role = await db.scalar(select(WorkspaceMember.role).where(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == user_id))
    return role


async def require_workspace(db: AsyncSession, workspace_id: UUID, user_id: UUID, allowed: set[str] | None = None) -> str:
    role = await workspace_role(db, workspace_id, user_id)
    if role is None or (allowed is not None and role not in allowed):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace access denied")
    return role
