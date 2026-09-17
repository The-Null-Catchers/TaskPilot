from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import current_user, require_workspace
from app.db import get_db
from app.models import BoardColumn, Project, Task, User
from app.schemas import BoardOut, ColumnOut, ProjectCreate, ProjectOut, TaskOut

router = APIRouter(prefix="/projects", tags=["projects"])
DEFAULT_COLUMNS = ["Backlog", "To Do", "In Progress", "Review", "Done"]


@router.get("", response_model=list[ProjectOut])
async def list_projects(workspace_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await require_workspace(db, workspace_id, user.id)
    return list((await db.scalars(select(Project).where(Project.workspace_id == workspace_id).order_by(Project.updated_at.desc()))).all())


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(data: ProjectCreate, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await require_workspace(db, data.workspace_id, user.id, {"owner", "admin", "member"})
    existing = await db.scalar(select(Project.id).where(Project.workspace_id == data.workspace_id, Project.key == data.key))
    if existing:
        raise HTTPException(status_code=409, detail="Project key already exists in this workspace")
    project = Project(workspace_id=data.workspace_id, owner_id=user.id, name=data.name.strip(), key=data.key, description=data.description, start_date=data.start_date, due_date=data.due_date)
    db.add(project)
    await db.flush()
    db.add_all([BoardColumn(project_id=project.id, name=name, position=i) for i, name in enumerate(DEFAULT_COLUMNS)])
    await db.commit()
    await db.refresh(project)
    return project


@router.get("/{project_id}/board", response_model=BoardOut)
async def board(project_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    await require_workspace(db, project.workspace_id, user.id)
    columns = list((await db.scalars(select(BoardColumn).where(BoardColumn.project_id == project.id).order_by(BoardColumn.position))).all())
    tasks = list((await db.scalars(select(Task).where(Task.project_id == project.id, Task.deleted_at.is_(None)).order_by(Task.column_id, Task.position))).all())
    return BoardOut(project=ProjectOut.model_validate(project), columns=[ColumnOut.model_validate(c) for c in columns], tasks=[TaskOut.model_validate(t) for t in tasks])
