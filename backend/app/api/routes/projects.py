from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, require_project, require_workspace
from app.collaboration_models import ProjectMember
from app.collaboration_schemas import ProjectMemberAdd, ProjectMemberOut
from app.db import get_db
from app.models import BoardColumn, Project, Task, User, WorkspaceMember
from app.schemas import BoardOut, ColumnOut, ProjectCreate, ProjectOut, TaskOut

router = APIRouter(prefix="/projects", tags=["projects"])
DEFAULT_COLUMNS = ["Backlog", "To Do", "In Progress", "Review", "Done"]


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    workspace_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    role = await require_workspace(db, workspace_id, user.id)
    query = select(Project).where(Project.workspace_id == workspace_id)
    if role == "guest":
        query = query.join(ProjectMember, ProjectMember.project_id == Project.id).where(
            ProjectMember.user_id == user.id
        )
    query = query.order_by(Project.updated_at.desc())
    return list((await db.scalars(query)).all())


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(
    data: ProjectCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace(db, data.workspace_id, user.id, {"owner", "admin", "member"})
    existing = await db.scalar(
        select(Project.id).where(
            Project.workspace_id == data.workspace_id,
            Project.key == data.key,
        )
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Project key already exists in this workspace",
        )
    project = Project(
        workspace_id=data.workspace_id,
        owner_id=user.id,
        name=data.name.strip(),
        key=data.key,
        description=data.description,
        start_date=data.start_date,
        due_date=data.due_date,
    )
    db.add(project)
    await db.flush()
    db.add(ProjectMember(project_id=project.id, user_id=user.id, role="owner"))
    db.add_all(
        [
            BoardColumn(project_id=project.id, name=name, position=i)
            for i, name in enumerate(DEFAULT_COLUMNS)
        ]
    )
    await db.commit()
    await db.refresh(project)
    return project


@router.get("/{project_id}/board", response_model=BoardOut)
async def board(
    project_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project, _ = await require_project(db, project_id, user.id)
    columns = list(
        (
            await db.scalars(
                select(BoardColumn)
                .where(BoardColumn.project_id == project.id)
                .order_by(BoardColumn.position)
            )
        ).all()
    )
    tasks = list(
        (
            await db.scalars(
                select(Task)
                .where(Task.project_id == project.id, Task.deleted_at.is_(None))
                .order_by(Task.column_id, Task.position)
            )
        ).all()
    )
    return BoardOut(
        project=ProjectOut.model_validate(project),
        columns=[ColumnOut.model_validate(column) for column in columns],
        tasks=[TaskOut.model_validate(task) for task in tasks],
    )


async def _can_manage_project(
    db: AsyncSession,
    project: Project,
    user_id: UUID,
) -> None:
    workspace_role = await require_workspace(db, project.workspace_id, user_id)
    if project.owner_id != user_id and workspace_role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Project management access required")


@router.get("/{project_id}/members", response_model=list[ProjectMemberOut])
async def list_project_members(
    project_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project, _ = await require_project(db, project_id, user.id)
    rows = (
        await db.execute(
            select(ProjectMember, User)
            .join(User, User.id == ProjectMember.user_id)
            .where(ProjectMember.project_id == project.id)
            .order_by(ProjectMember.created_at)
        )
    ).all()
    return [
        ProjectMemberOut(
            user_id=member.user_id,
            email=member_user.email,
            name=member_user.name,
            role=member.role,
            created_at=member.created_at,
        )
        for member, member_user in rows
    ]


@router.post("/{project_id}/members", response_model=ProjectMemberOut)
async def add_project_member(
    project_id: UUID,
    data: ProjectMemberAdd,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project, _ = await require_project(db, project_id, user.id)
    await _can_manage_project(db, project, user.id)
    target_membership = await db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == project.workspace_id,
            WorkspaceMember.user_id == data.user_id,
        )
    )
    target_user = await db.get(User, data.user_id)
    if not target_membership or not target_user or not target_user.is_active:
        raise HTTPException(status_code=400, detail="User must be an active workspace member")

    member = await db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == data.user_id,
        )
    )
    if member:
        if member.user_id == project.owner_id:
            member.role = "owner"
        else:
            member.role = data.role
    else:
        member = ProjectMember(
            project_id=project.id,
            user_id=data.user_id,
            role="owner" if data.user_id == project.owner_id else data.role,
        )
        db.add(member)
    await db.commit()
    await db.refresh(member)
    return ProjectMemberOut(
        user_id=member.user_id,
        email=target_user.email,
        name=target_user.name,
        role=member.role,
        created_at=member.created_at,
    )


@router.delete("/{project_id}/members/{member_user_id}", status_code=204)
async def remove_project_member(
    project_id: UUID,
    member_user_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project, _ = await require_project(db, project_id, user.id)
    await _can_manage_project(db, project, user.id)
    if member_user_id == project.owner_id:
        raise HTTPException(status_code=409, detail="Project owner cannot be removed")
    member = await db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == member_user_id,
        )
    )
    if not member:
        raise HTTPException(status_code=404, detail="Project member not found")
    await db.delete(member)
    await db.commit()
