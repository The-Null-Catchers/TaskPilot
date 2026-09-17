from uuid import uuid4
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import current_user
from app.db import get_db
from app.models import User, Workspace, WorkspaceMember
from app.schemas import WorkspaceCreate, WorkspaceOut

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("", response_model=list[WorkspaceOut])
async def list_workspaces(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    query = select(Workspace).join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id).where(WorkspaceMember.user_id == user.id).order_by(Workspace.updated_at.desc())
    return list((await db.scalars(query)).all())


@router.post("", response_model=WorkspaceOut, status_code=201)
async def create_workspace(data: WorkspaceCreate, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    slug = f"{data.name.lower().replace(' ', '-')[:90]}-{str(uuid4())[:6]}"
    workspace = Workspace(name=data.name.strip(), slug=slug, owner_id=user.id)
    db.add(workspace)
    await db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
    await db.commit()
    await db.refresh(workspace)
    return workspace
