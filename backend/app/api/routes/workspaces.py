import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, require_workspace
from app.collaboration_models import AuditLog, ProjectMember, WorkspaceArchive
from app.collaboration_schemas import (
    OwnershipTransferIn,
    WorkspaceInvitationCreated,
    WorkspaceInvitationOut,
    WorkspaceInvitationPreview,
    WorkspaceInviteCreate,
    WorkspaceLifecycleOut,
    WorkspaceMemberOut,
    WorkspaceMemberUpdate,
    WorkspaceUpdate,
)
from app.core.security import new_refresh_token, token_digest
from app.notification_security import encrypt_text
from app.db import get_db
from app.domain import can_invite_role, can_manage_member
from app.models import Project, User, Workspace, WorkspaceInvitation, WorkspaceMember
from app.schemas import WorkspaceCreate, WorkspaceOut

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _audit(
    db: AsyncSession,
    *,
    actor_id: UUID,
    action: str,
    workspace_id: UUID | None,
    request: Request,
    metadata: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_id=actor_id,
            workspace_id=workspace_id,
            action=action,
            ip_address=_ip(request),
            metadata_json=json.dumps(metadata or {}, default=str),
        )
    )


async def _workspace(db: AsyncSession, workspace_id: UUID) -> Workspace:
    workspace = await db.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


def _archived_out(workspace: Workspace, archive: WorkspaceArchive) -> WorkspaceLifecycleOut:
    return WorkspaceLifecycleOut(
        id=workspace.id,
        name=workspace.name,
        slug=workspace.slug,
        owner_id=workspace.owner_id,
        archived_at=archive.archived_at,
        archived_by_id=archive.archived_by_id,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
    )


@router.get("", response_model=list[WorkspaceOut])
async def list_workspaces(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    archived_ids = select(WorkspaceArchive.workspace_id)
    query = (
        select(Workspace)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(
            WorkspaceMember.user_id == user.id,
            ~Workspace.id.in_(archived_ids),
        )
        .order_by(Workspace.updated_at.desc())
    )
    return list((await db.scalars(query)).all())


@router.get("/archived", response_model=list[WorkspaceLifecycleOut])
async def list_archived_workspaces(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(Workspace, WorkspaceArchive)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .join(WorkspaceArchive, WorkspaceArchive.workspace_id == Workspace.id)
            .where(WorkspaceMember.user_id == user.id)
            .order_by(WorkspaceArchive.archived_at.desc())
        )
    ).all()
    return [_archived_out(workspace, archive) for workspace, archive in rows]


@router.post("", response_model=WorkspaceOut, status_code=201)
async def create_workspace(
    data: WorkspaceCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    slug = f"{data.name.lower().replace(' ', '-')[:90]}-{str(uuid4())[:6]}"
    workspace = Workspace(name=data.name.strip(), slug=slug, owner_id=user.id)
    db.add(workspace)
    await db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
    await db.commit()
    await db.refresh(workspace)
    return workspace


@router.patch("/{workspace_id}", response_model=WorkspaceOut)
async def update_workspace(
    workspace_id: UUID,
    data: WorkspaceUpdate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace(db, workspace_id, user.id, {"owner", "admin"})
    workspace = await _workspace(db, workspace_id)
    workspace.name = data.name.strip()
    await db.commit()
    await db.refresh(workspace)
    return workspace


@router.get("/{workspace_id}/members", response_model=list[WorkspaceMemberOut])
async def list_members(
    workspace_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace(db, workspace_id, user.id, allow_archived=True)
    rows = (
        await db.execute(
            select(WorkspaceMember, User)
            .join(User, User.id == WorkspaceMember.user_id)
            .where(WorkspaceMember.workspace_id == workspace_id)
            .order_by(WorkspaceMember.created_at)
        )
    ).all()
    return [
        WorkspaceMemberOut(
            user_id=member.user_id,
            email=member_user.email,
            name=member_user.name,
            role=member.role,
            created_at=member.created_at,
        )
        for member, member_user in rows
    ]


@router.patch("/{workspace_id}/members/{member_user_id}", response_model=WorkspaceMemberOut)
async def update_member_role(
    workspace_id: UUID,
    member_user_id: UUID,
    data: WorkspaceMemberUpdate,
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    actor_role = await require_workspace(db, workspace_id, user.id, {"owner", "admin"})
    member = await db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == member_user_id,
        )
    )
    member_user = await db.get(User, member_user_id)
    if not member or not member_user:
        raise HTTPException(status_code=404, detail="Workspace member not found")
    if not can_manage_member(actor_role, member.role, data.role):
        raise HTTPException(status_code=403, detail="You cannot change this member's role")
    previous_role = member.role
    member.role = data.role
    _audit(
        db,
        actor_id=user.id,
        action="workspace.member.role_changed",
        workspace_id=workspace_id,
        request=request,
        metadata={
            "member_user_id": member_user_id,
            "previous_role": previous_role,
            "new_role": data.role,
        },
    )
    await db.commit()
    await db.refresh(member)
    return WorkspaceMemberOut(
        user_id=member.user_id,
        email=member_user.email,
        name=member_user.name,
        role=member.role,
        created_at=member.created_at,
    )


async def _cleanup_project_memberships(
    db: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
) -> None:
    project_ids = select(Project.id).where(Project.workspace_id == workspace_id)
    await db.execute(
        delete(ProjectMember).where(
            ProjectMember.user_id == user_id,
            ProjectMember.project_id.in_(project_ids),
        )
    )


@router.delete("/{workspace_id}/members/{member_user_id}", status_code=204)
async def remove_member(
    workspace_id: UUID,
    member_user_id: UUID,
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    actor_role = await require_workspace(db, workspace_id, user.id, {"owner", "admin"})
    member = await db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == member_user_id,
        )
    )
    if not member:
        raise HTTPException(status_code=404, detail="Workspace member not found")
    if not can_manage_member(actor_role, member.role):
        raise HTTPException(status_code=403, detail="You cannot remove this workspace member")
    await _cleanup_project_memberships(db, workspace_id, member_user_id)
    await db.delete(member)
    _audit(
        db,
        actor_id=user.id,
        action="workspace.member.removed",
        workspace_id=workspace_id,
        request=request,
        metadata={"member_user_id": member_user_id, "role": member.role},
    )
    await db.commit()


@router.get("/{workspace_id}/invitations", response_model=list[WorkspaceInvitationOut])
async def list_invitations(
    workspace_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace(db, workspace_id, user.id, {"owner", "admin"})
    now = datetime.now(UTC)
    query = (
        select(WorkspaceInvitation)
        .where(
            WorkspaceInvitation.workspace_id == workspace_id,
            WorkspaceInvitation.accepted_at.is_(None),
            WorkspaceInvitation.expires_at > now,
        )
        .order_by(WorkspaceInvitation.created_at.desc())
    )
    return list((await db.scalars(query)).all())


@router.post(
    "/{workspace_id}/invitations",
    response_model=WorkspaceInvitationCreated,
    status_code=201,
)
async def create_invitation(
    workspace_id: UUID,
    data: WorkspaceInviteCreate,
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    actor_role = await require_workspace(db, workspace_id, user.id, {"owner", "admin"})
    if not can_invite_role(actor_role, data.role):
        raise HTTPException(status_code=403, detail="You cannot invite a member with this role")
    email = data.email.lower()
    existing_member = await db.scalar(
        select(WorkspaceMember.id)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(WorkspaceMember.workspace_id == workspace_id, User.email == email)
    )
    if existing_member:
        raise HTTPException(status_code=409, detail="User is already a workspace member")
    now = datetime.now(UTC)
    active_invite = await db.scalar(
        select(WorkspaceInvitation.id).where(
            WorkspaceInvitation.workspace_id == workspace_id,
            WorkspaceInvitation.email == email,
            WorkspaceInvitation.accepted_at.is_(None),
            WorkspaceInvitation.expires_at > now,
        )
    )
    if active_invite:
        raise HTTPException(status_code=409, detail="An active invitation already exists")

    raw_token = new_refresh_token()
    invitation = WorkspaceInvitation(
        workspace_id=workspace_id,
        email=email,
        role=data.role,
        token_hash=token_digest(raw_token),
        delivery_token_ciphertext=encrypt_text(raw_token),
        delivery_status="pending",
        expires_at=now + timedelta(days=7),
    )
    db.add(invitation)
    _audit(
        db,
        actor_id=user.id,
        action="workspace.invitation.created",
        workspace_id=workspace_id,
        request=request,
        metadata={"email": email, "role": data.role},
    )
    await db.commit()
    await db.refresh(invitation)
    return WorkspaceInvitationCreated(
        id=invitation.id,
        workspace_id=invitation.workspace_id,
        email=invitation.email,
        role=invitation.role,
        delivery_status=invitation.delivery_status,
        delivered_at=invitation.delivered_at,
        expires_at=invitation.expires_at,
        accepted_at=invitation.accepted_at,
        created_at=invitation.created_at,
        token=raw_token,
    )


async def _invitation_from_token(db: AsyncSession, token: str) -> WorkspaceInvitation:
    invitation = await db.scalar(
        select(WorkspaceInvitation).where(
            WorkspaceInvitation.token_hash == token_digest(token)
        )
    )
    if (
        not invitation
        or invitation.accepted_at is not None
        or invitation.expires_at <= datetime.now(UTC)
    ):
        raise HTTPException(status_code=404, detail="Invitation is invalid or expired")
    archive = await db.get(WorkspaceArchive, invitation.workspace_id)
    if archive is not None:
        raise HTTPException(status_code=409, detail="Workspace is archived")
    return invitation


@router.get("/invitations/{token}", response_model=WorkspaceInvitationPreview)
async def preview_invitation(
    token: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    invitation = await _invitation_from_token(db, token)
    if user.email.lower() != invitation.email.lower():
        raise HTTPException(status_code=403, detail="Invitation belongs to another email address")
    workspace = await _workspace(db, invitation.workspace_id)
    return WorkspaceInvitationPreview(
        workspace_id=workspace.id,
        workspace_name=workspace.name,
        email=invitation.email,
        role=invitation.role,
        expires_at=invitation.expires_at,
    )


@router.delete("/{workspace_id}/invitations/{invitation_id}", status_code=204)
async def cancel_invitation(
    workspace_id: UUID,
    invitation_id: UUID,
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    actor_role = await require_workspace(db, workspace_id, user.id, {"owner", "admin"})
    invitation = await db.get(WorkspaceInvitation, invitation_id)
    if not invitation or invitation.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if invitation.accepted_at is not None:
        raise HTTPException(status_code=409, detail="Invitation has already been accepted")
    if not can_invite_role(actor_role, invitation.role):
        raise HTTPException(status_code=403, detail="You cannot cancel this invitation")
    _audit(
        db,
        actor_id=user.id,
        action="workspace.invitation.cancelled",
        workspace_id=workspace_id,
        request=request,
        metadata={"invitation_id": invitation.id, "email": invitation.email},
    )
    await db.delete(invitation)
    await db.commit()


@router.post("/invitations/{token}/accept", response_model=WorkspaceOut)
async def accept_invitation(
    token: str,
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    invitation = await _invitation_from_token(db, token)
    if user.email.lower() != invitation.email.lower():
        raise HTTPException(status_code=403, detail="Invitation belongs to another email address")
    existing = await db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == invitation.workspace_id,
            WorkspaceMember.user_id == user.id,
        )
    )
    if not existing:
        db.add(
            WorkspaceMember(
                workspace_id=invitation.workspace_id,
                user_id=user.id,
                role=invitation.role,
            )
        )
    invitation.accepted_at = datetime.now(UTC)
    _audit(
        db,
        actor_id=user.id,
        action="workspace.invitation.accepted",
        workspace_id=invitation.workspace_id,
        request=request,
        metadata={"invitation_id": invitation.id},
    )
    await db.commit()
    return await _workspace(db, invitation.workspace_id)


@router.post("/invitations/{token}/reject", status_code=204)
async def reject_invitation(
    token: str,
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    invitation = await _invitation_from_token(db, token)
    if user.email.lower() != invitation.email.lower():
        raise HTTPException(status_code=403, detail="Invitation belongs to another email address")
    workspace_id = invitation.workspace_id
    invitation_id = invitation.id
    await db.delete(invitation)
    _audit(
        db,
        actor_id=user.id,
        action="workspace.invitation.rejected",
        workspace_id=workspace_id,
        request=request,
        metadata={"invitation_id": invitation_id},
    )
    await db.commit()


@router.post("/{workspace_id}/transfer-ownership", response_model=WorkspaceOut)
async def transfer_ownership(
    workspace_id: UUID,
    data: OwnershipTransferIn,
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace(db, workspace_id, user.id, {"owner"})
    if data.user_id == user.id:
        raise HTTPException(status_code=409, detail="You already own this workspace")
    workspace = await _workspace(db, workspace_id)
    current_member = await db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user.id,
        )
    )
    target_member = await db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == data.user_id,
        )
    )
    if not current_member or not target_member:
        raise HTTPException(status_code=404, detail="Target user is not a workspace member")
    workspace.owner_id = data.user_id
    current_member.role = "admin"
    target_member.role = "owner"
    _audit(
        db,
        actor_id=user.id,
        action="workspace.ownership.transferred",
        workspace_id=workspace_id,
        request=request,
        metadata={"new_owner_id": data.user_id},
    )
    await db.commit()
    await db.refresh(workspace)
    return workspace


@router.post("/{workspace_id}/archive", response_model=WorkspaceLifecycleOut)
async def archive_workspace(
    workspace_id: UUID,
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace(db, workspace_id, user.id, {"owner"})
    workspace = await _workspace(db, workspace_id)
    archive = WorkspaceArchive(workspace_id=workspace_id, archived_by_id=user.id)
    db.add(archive)
    await db.execute(
        delete(WorkspaceInvitation).where(
            WorkspaceInvitation.workspace_id == workspace_id,
            WorkspaceInvitation.accepted_at.is_(None),
        )
    )
    _audit(
        db,
        actor_id=user.id,
        action="workspace.archived",
        workspace_id=workspace_id,
        request=request,
        metadata={"workspace_name": workspace.name},
    )
    await db.commit()
    await db.refresh(archive)
    return _archived_out(workspace, archive)


@router.post("/{workspace_id}/restore", response_model=WorkspaceOut)
async def restore_workspace(
    workspace_id: UUID,
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace(
        db,
        workspace_id,
        user.id,
        {"owner"},
        allow_archived=True,
    )
    workspace = await _workspace(db, workspace_id)
    archive = await db.get(WorkspaceArchive, workspace_id)
    if archive is None:
        return workspace
    await db.delete(archive)
    _audit(
        db,
        actor_id=user.id,
        action="workspace.restored",
        workspace_id=workspace_id,
        request=request,
        metadata={"workspace_name": workspace.name},
    )
    await db.commit()
    await db.refresh(workspace)
    return workspace


@router.post("/{workspace_id}/leave", status_code=204)
async def leave_workspace(
    workspace_id: UUID,
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    role = await require_workspace(db, workspace_id, user.id, allow_archived=True)
    if role == "owner":
        raise HTTPException(status_code=409, detail="Transfer ownership before leaving")
    member = await db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user.id,
        )
    )
    if member:
        await _cleanup_project_memberships(db, workspace_id, user.id)
        await db.delete(member)
    _audit(
        db,
        actor_id=user.id,
        action="workspace.member.left",
        workspace_id=workspace_id,
        request=request,
    )
    await db.commit()


@router.delete("/{workspace_id}", status_code=204)
async def delete_workspace(
    workspace_id: UUID,
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace(
        db,
        workspace_id,
        user.id,
        {"owner"},
        allow_archived=True,
    )
    workspace = await _workspace(db, workspace_id)
    _audit(
        db,
        actor_id=user.id,
        action="workspace.deleted",
        workspace_id=workspace_id,
        request=request,
        metadata={"workspace_name": workspace.name},
    )
    await db.flush()
    await db.delete(workspace)
    await db.commit()
