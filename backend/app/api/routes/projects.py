from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, require_project, require_workspace
from app.collaboration_models import ProjectMember
from app.collaboration_schemas import ProjectMemberAdd, ProjectMemberOut
from app.db import get_db
from app.models import ActivityLog, BoardColumn, Project, Task, User, WorkspaceMember
from app.realtime import publish
from app.settings_models import ProjectSetting, WorkspaceSetting
from app.schemas import (
    BoardOut,
    ColumnCreate,
    ColumnOut,
    ColumnPatch,
    ColumnReorder,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
    TaskOut,
)

router = APIRouter(prefix="/projects", tags=["projects"])
DEFAULT_COLUMNS = ["Backlog", "To Do", "In Progress", "Review", "Done"]


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    workspace_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    role = await require_workspace(db, workspace_id, user.id)
    query = select(Project).where(
        Project.workspace_id == workspace_id,
        Project.archived_at.is_(None),
    )
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
    workspace_setting = await db.get(WorkspaceSetting, data.workspace_id)
    project = Project(
        workspace_id=data.workspace_id,
        owner_id=user.id,
        name=data.name.strip(),
        key=data.key,
        description=data.description,
        icon=data.icon,
        color=data.color,
        status=workspace_setting.default_project_status if workspace_setting else "active",
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


@router.get("/archived", response_model=list[ProjectOut])
async def list_archived_projects(
    workspace_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    role = await require_workspace(db, workspace_id, user.id)
    query = select(Project).where(
        Project.workspace_id == workspace_id,
        Project.archived_at.is_not(None),
    )
    if role == "guest":
        query = query.join(ProjectMember, ProjectMember.project_id == Project.id).where(
            ProjectMember.user_id == user.id
        )
    return list((await db.scalars(query.order_by(Project.archived_at.desc()))).all())


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: UUID,
    data: ProjectUpdate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project, _ = await require_project(db, project_id, user.id)
    await _can_manage_project(db, project, user.id)
    if project.archived_at is not None:
        raise HTTPException(status_code=409, detail="Restore the project before editing it")

    values = data.model_dump(exclude_unset=True)
    if "name" in values and values["name"] is not None:
        values["name"] = values["name"].strip()
    if values.get("name") == "":
        raise HTTPException(status_code=422, detail="Project name cannot be blank")

    next_start = values.get("start_date", project.start_date)
    next_due = values.get("due_date", project.due_date)
    if next_start and next_due and next_due < next_start:
        raise HTTPException(status_code=422, detail="Project due date cannot be before start date")

    changed = []
    for field, value in values.items():
        if getattr(project, field) != value:
            setattr(project, field, value)
            changed.append(field)
    if changed:
        db.add(
            ActivityLog(
                workspace_id=project.workspace_id,
                project_id=project.id,
                task_id=None,
                actor_id=user.id,
                action="project.updated",
                summary=f"Updated {project.name}: {', '.join(changed)}",
            )
        )
        await db.commit()
        await db.refresh(project)
        await publish(
            project.workspace_id,
            "project.updated",
            ProjectOut.model_validate(project).model_dump(mode="json"),
        )
    return project


@router.post("/{project_id}/archive", response_model=ProjectOut)
async def archive_project(
    project_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project, _ = await require_project(db, project_id, user.id)
    await _can_manage_project(db, project, user.id)
    if project.archived_at is None:
        project.archived_at = datetime.now(UTC)
        project.status = "archived"
        db.add(
            ActivityLog(
                workspace_id=project.workspace_id,
                project_id=project.id,
                task_id=None,
                actor_id=user.id,
                action="project.archived",
                summary=f"Archived {project.name}",
            )
        )
        await db.commit()
        await db.refresh(project)
        await publish(
            project.workspace_id,
            "project.updated",
            ProjectOut.model_validate(project).model_dump(mode="json"),
        )
    return project


@router.post("/{project_id}/restore", response_model=ProjectOut)
async def restore_project(
    project_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project, _ = await require_project(db, project_id, user.id)
    await _can_manage_project(db, project, user.id)
    if project.archived_at is not None:
        project.archived_at = None
        project.status = "active"
        db.add(
            ActivityLog(
                workspace_id=project.workspace_id,
                project_id=project.id,
                task_id=None,
                actor_id=user.id,
                action="project.restored",
                summary=f"Restored {project.name}",
            )
        )
        await db.commit()
        await db.refresh(project)
        await publish(
            project.workspace_id,
            "project.updated",
            ProjectOut.model_validate(project).model_dump(mode="json"),
        )
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
    task_query = select(Task).where(
        Task.project_id == project.id,
        Task.deleted_at.is_(None),
    )
    project_setting = await db.get(ProjectSetting, project.id)
    if project_setting is not None and not project_setting.show_completed_tasks:
        task_query = task_query.where(Task.status != "done")
    tasks = list(
        (
            await db.scalars(
                task_query.order_by(Task.column_id, Task.position)
            )
        ).all()
    )
    return BoardOut(
        project=ProjectOut.model_validate(project),
        columns=[ColumnOut.model_validate(column) for column in columns],
        tasks=[TaskOut.model_validate(task) for task in tasks],
    )


@router.post("/{project_id}/columns", response_model=ColumnOut, status_code=201)
async def create_column(
    project_id: UUID,
    data: ColumnCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project, _ = await require_project(db, project_id, user.id)
    await _can_manage_project(db, project, user.id)
    if project.archived_at is not None:
        raise HTTPException(status_code=409, detail="Restore the project before editing its board")

    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Column name cannot be blank")
    duplicate = await db.scalar(
        select(BoardColumn.id).where(
            BoardColumn.project_id == project.id,
            func.lower(BoardColumn.name) == name.lower(),
        )
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="A column with this name already exists")
    max_position = await db.scalar(
        select(func.max(BoardColumn.position)).where(BoardColumn.project_id == project.id)
    )
    column = BoardColumn(
        project_id=project.id,
        name=name,
        position=(max_position if max_position is not None else -1) + 1,
    )
    db.add(column)
    db.add(
        ActivityLog(
            workspace_id=project.workspace_id,
            project_id=project.id,
            task_id=None,
            actor_id=user.id,
            action="board.column.created",
            summary=f"Created board column {name}",
        )
    )
    await db.commit()
    await db.refresh(column)
    await publish(
        project.workspace_id,
        "board.column.created",
        ColumnOut.model_validate(column).model_dump(mode="json"),
    )
    return column


@router.patch("/{project_id}/columns/{column_id}", response_model=ColumnOut)
async def rename_column(
    project_id: UUID,
    column_id: UUID,
    data: ColumnPatch,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project, _ = await require_project(db, project_id, user.id)
    await _can_manage_project(db, project, user.id)
    if project.archived_at is not None:
        raise HTTPException(status_code=409, detail="Restore the project before editing its board")
    column = await db.get(BoardColumn, column_id)
    if not column or column.project_id != project.id:
        raise HTTPException(status_code=404, detail="Board column not found")

    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Column name cannot be blank")
    duplicate = await db.scalar(
        select(BoardColumn.id).where(
            BoardColumn.project_id == project.id,
            BoardColumn.id != column.id,
            func.lower(BoardColumn.name) == name.lower(),
        )
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="A column with this name already exists")
    column.name = name
    db.add(
        ActivityLog(
            workspace_id=project.workspace_id,
            project_id=project.id,
            task_id=None,
            actor_id=user.id,
            action="board.column.renamed",
            summary=f"Renamed a board column to {name}",
        )
    )
    await db.commit()
    await db.refresh(column)
    await publish(
        project.workspace_id,
        "board.column.updated",
        ColumnOut.model_validate(column).model_dump(mode="json"),
    )
    return column


@router.put("/{project_id}/columns/reorder", response_model=list[ColumnOut])
async def reorder_columns(
    project_id: UUID,
    data: ColumnReorder,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project, _ = await require_project(db, project_id, user.id)
    await _can_manage_project(db, project, user.id)
    if project.archived_at is not None:
        raise HTTPException(status_code=409, detail="Restore the project before editing its board")

    columns = list(
        (
            await db.scalars(
                select(BoardColumn)
                .where(BoardColumn.project_id == project.id)
                .order_by(BoardColumn.position)
                .with_for_update()
            )
        ).all()
    )
    existing_ids = [column.id for column in columns]
    if len(data.column_ids) != len(set(data.column_ids)):
        raise HTTPException(status_code=422, detail="Column order contains duplicates")
    if set(data.column_ids) != set(existing_ids):
        raise HTTPException(
            status_code=422,
            detail="Column order must contain every project column exactly once",
        )

    await db.execute(
        update(BoardColumn)
        .where(BoardColumn.project_id == project.id)
        .values(position=BoardColumn.position + 10000)
    )
    await db.flush()
    for position, column_id in enumerate(data.column_ids):
        await db.execute(
            update(BoardColumn)
            .where(BoardColumn.id == column_id, BoardColumn.project_id == project.id)
            .values(position=position)
        )
    db.add(
        ActivityLog(
            workspace_id=project.workspace_id,
            project_id=project.id,
            task_id=None,
            actor_id=user.id,
            action="board.columns.reordered",
            summary="Reordered board columns",
        )
    )
    await db.commit()
    ordered = list(
        (
            await db.scalars(
                select(BoardColumn)
                .where(BoardColumn.project_id == project.id)
                .order_by(BoardColumn.position)
            )
        ).all()
    )
    payload = [ColumnOut.model_validate(item).model_dump(mode="json") for item in ordered]
    await publish(project.workspace_id, "board.columns.reordered", {"columns": payload})
    return ordered


@router.delete("/{project_id}/columns/{column_id}", status_code=204)
async def delete_column(
    project_id: UUID,
    column_id: UUID,
    move_to_column_id: UUID | None = None,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project, _ = await require_project(db, project_id, user.id)
    await _can_manage_project(db, project, user.id)
    if project.archived_at is not None:
        raise HTTPException(status_code=409, detail="Restore the project before editing its board")

    columns = list(
        (
            await db.scalars(
                select(BoardColumn)
                .where(BoardColumn.project_id == project.id)
                .order_by(BoardColumn.position)
                .with_for_update()
            )
        ).all()
    )
    if len(columns) <= 1:
        raise HTTPException(status_code=409, detail="A board must keep at least one column")
    column = next((item for item in columns if item.id == column_id), None)
    if column is None:
        raise HTTPException(status_code=404, detail="Board column not found")

    task_count = int(
        await db.scalar(
            select(func.count(Task.id)).where(Task.column_id == column.id)
        )
        or 0
    )
    destination = None
    if task_count:
        if move_to_column_id is None:
            raise HTTPException(
                status_code=409,
                detail="Column contains tasks. Move them first or provide move_to_column_id.",
            )
        destination = next(
            (item for item in columns if item.id == move_to_column_id and item.id != column.id),
            None,
        )
        if destination is None:
            raise HTTPException(status_code=422, detail="Destination column is invalid")
        await db.execute(
            update(Task)
            .where(Task.column_id == column.id)
            .values(column_id=destination.id, version=Task.version + 1)
        )

    await db.delete(column)
    await db.flush()
    remaining = [item for item in columns if item.id != column.id]
    await db.execute(
        update(BoardColumn)
        .where(BoardColumn.project_id == project.id)
        .values(position=BoardColumn.position + 10000)
    )
    await db.flush()
    for position, item in enumerate(remaining):
        await db.execute(
            update(BoardColumn)
            .where(BoardColumn.id == item.id)
            .values(position=position)
        )
    db.add(
        ActivityLog(
            workspace_id=project.workspace_id,
            project_id=project.id,
            task_id=None,
            actor_id=user.id,
            action="board.column.deleted",
            summary=(
                f"Deleted board column {column.name}"
                + (f" and moved {task_count} tasks to {destination.name}" if destination else "")
            ),
        )
    )
    await db.commit()
    await publish(
        project.workspace_id,
        "board.column.deleted",
        {
            "project_id": str(project.id),
            "column_id": str(column.id),
            "move_to_column_id": str(destination.id) if destination else None,
        },
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
