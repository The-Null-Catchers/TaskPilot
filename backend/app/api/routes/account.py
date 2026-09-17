import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.account_models import AccountSecurity, AccountToken, SessionMetadata
from app.api.deps import current_user
from app.collaboration_models import AuditLog
from app.core.config import settings
from app.core.security import hash_password, new_refresh_token, token_digest, verify_password
from app.db import get_db
from app.email_delivery import send_account_email
from app.models import Project, Session, User, Workspace

router = APIRouter(prefix="/auth", tags=["account"])


class TokenIn(BaseModel):
    token: str = Field(min_length=20, max_length=300)


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(TokenIn):
    password: str = Field(min_length=10, max_length=128)


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=128)


class ChangeEmailIn(BaseModel):
    password: str
    email: EmailStr


class DeleteAccountIn(BaseModel):
    password: str
    confirmation: str


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _audit(db: AsyncSession, action: str, request: Request, actor_id: UUID | None, metadata: dict | None = None) -> None:
    db.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            ip_address=_ip(request),
            metadata_json=json.dumps(metadata or {}),
        )
    )


async def _security(db: AsyncSession, user_id: UUID) -> AccountSecurity:
    security = await db.get(AccountSecurity, user_id)
    if security is None:
        security = AccountSecurity(user_id=user_id)
        db.add(security)
        await db.flush()
    return security


async def _issue_token(
    db: AsyncSession,
    user_id: UUID,
    purpose: str,
    *,
    payload: dict | None = None,
) -> str:
    now = datetime.now(UTC)
    await db.execute(
        update(AccountToken)
        .where(
            AccountToken.user_id == user_id,
            AccountToken.purpose == purpose,
            AccountToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    raw = new_refresh_token()
    db.add(
        AccountToken(
            user_id=user_id,
            purpose=purpose,
            token_hash=token_digest(raw),
            payload_json=json.dumps(payload or {}),
            expires_at=now + timedelta(minutes=settings.account_token_minutes),
        )
    )
    await db.flush()
    return raw


async def _consume_token(db: AsyncSession, raw: str, purpose: str) -> AccountToken:
    token = await db.scalar(
        select(AccountToken)
        .where(
            AccountToken.token_hash == token_digest(raw),
            AccountToken.purpose == purpose,
        )
        .with_for_update()
    )
    now = datetime.now(UTC)
    if not token or token.used_at is not None or token.expires_at <= now:
        raise HTTPException(status_code=400, detail="Token is invalid or expired")
    token.used_at = now
    return token


def _dev_token(raw: str | None) -> dict:
    if raw and settings.app_env != "production":
        return {"development_token": raw}
    return {}


@router.get("/account")
async def account_status(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    security = await _security(db, user.id)
    await db.commit()
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "email_verified": security.email_verified_at is not None,
        "email_verified_at": security.email_verified_at,
    }


@router.post("/email-verification/request", status_code=202)
async def request_email_verification(
    background: BackgroundTasks,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    security = await _security(db, user.id)
    if security.email_verified_at is not None:
        return {"message": "Email is already verified"}
    raw = await _issue_token(db, user.id, "verify_email")
    await db.commit()
    url = f"{settings.app_url.rstrip('/')}/verify-email?token={raw}"
    background.add_task(send_account_email, user.email, "Verify your TaskPilot email", f"Verify your email: {url}")
    return {"message": "Verification email queued", **_dev_token(raw)}


@router.post("/email-verification/confirm")
async def confirm_email_verification(
    data: TokenIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    token = await _consume_token(db, data.token, "verify_email")
    security = await _security(db, token.user_id)
    security.email_verified_at = datetime.now(UTC)
    _audit(db, "auth.email_verified", request, token.user_id)
    await db.commit()
    return {"verified": True}


@router.post("/forgot-password", status_code=202)
async def forgot_password(
    data: ForgotPasswordIn,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    user = await db.scalar(select(User).where(User.email == data.email.lower(), User.is_active.is_(True)))
    raw = None
    if user:
        raw = await _issue_token(db, user.id, "password_reset")
        await db.commit()
        url = f"{settings.app_url.rstrip('/')}/reset-password?token={raw}"
        background.add_task(send_account_email, user.email, "Reset your TaskPilot password", f"Reset your password: {url}")
    return {"message": "If the account exists, a reset email has been queued", **_dev_token(raw)}


@router.post("/reset-password", status_code=204)
async def reset_password(data: ResetPasswordIn, request: Request, db: AsyncSession = Depends(get_db)):
    token = await _consume_token(db, data.token, "password_reset")
    user = await db.get(User, token.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail="Account is unavailable")
    user.password_hash = hash_password(data.password)
    await db.execute(
        update(Session)
        .where(Session.user_id == user.id, Session.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    _audit(db, "auth.password_reset", request, user.id)
    await db.commit()


@router.post("/change-password", status_code=204)
async def change_password(
    data: ChangePasswordIn,
    request: Request,
    response: Response,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.password_hash = hash_password(data.new_password)
    await db.execute(
        update(Session)
        .where(Session.user_id == user.id, Session.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    _audit(db, "auth.password_changed", request, user.id)
    await db.commit()
    response.delete_cookie("tp_refresh", path="/api/v1/auth")


@router.post("/change-email", status_code=202)
async def request_change_email(
    data: ChangeEmailIn,
    background: BackgroundTasks,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Password is incorrect")
    new_email = data.email.lower()
    if new_email == user.email:
        raise HTTPException(status_code=400, detail="New email must be different")
    if await db.scalar(select(User.id).where(User.email == new_email)):
        raise HTTPException(status_code=409, detail="Email is already registered")
    raw = await _issue_token(db, user.id, "change_email", payload={"email": new_email})
    await db.commit()
    url = f"{settings.app_url.rstrip('/')}/confirm-email?token={raw}"
    background.add_task(send_account_email, new_email, "Confirm your TaskPilot email", f"Confirm your new email: {url}")
    return {"message": "Confirmation email queued", **_dev_token(raw)}


@router.post("/change-email/confirm", status_code=204)
async def confirm_change_email(
    data: TokenIn,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    token = await _consume_token(db, data.token, "change_email")
    user = await db.get(User, token.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail="Account is unavailable")
    payload = json.loads(token.payload_json or "{}")
    new_email = str(payload.get("email", "")).lower()
    if not new_email:
        raise HTTPException(status_code=400, detail="Email change token is invalid")
    if await db.scalar(select(User.id).where(User.email == new_email, User.id != user.id)):
        raise HTTPException(status_code=409, detail="Email is already registered")
    user.email = new_email
    security = await _security(db, user.id)
    security.email_verified_at = datetime.now(UTC)
    await db.execute(
        update(Session)
        .where(Session.user_id == user.id, Session.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    _audit(db, "auth.email_changed", request, user.id)
    await db.commit()
    response.delete_cookie("tp_refresh", path="/api/v1/auth")


@router.get("/sessions")
async def list_sessions(
    tp_refresh: str | None = Cookie(default=None),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    current_hash = token_digest(tp_refresh) if tp_refresh else None
    rows = (
        await db.execute(
            select(Session, SessionMetadata)
            .outerjoin(SessionMetadata, SessionMetadata.session_id == Session.id)
            .where(Session.user_id == user.id)
            .order_by(Session.created_at.desc())
        )
    ).all()
    now = datetime.now(UTC)
    return [
        {
            "id": session.id,
            "device_name": session.device_name,
            "ip_address": metadata.ip_address if metadata else None,
            "user_agent": metadata.user_agent if metadata else None,
            "last_used_at": metadata.last_used_at if metadata else session.created_at,
            "created_at": session.created_at,
            "expires_at": session.expires_at,
            "revoked_at": session.revoked_at,
            "active": session.revoked_at is None and session.expires_at > now,
            "current": current_hash == session.refresh_token_hash,
        }
        for session, metadata in rows
    ]


@router.delete("/sessions/{session_id}", status_code=204)
async def revoke_session(
    session_id: UUID,
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(Session, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.revoked_at is None:
        session.revoked_at = datetime.now(UTC)
    _audit(db, "auth.session_revoked", request, user.id, {"session_id": str(session.id)})
    await db.commit()


@router.post("/sessions/logout-all", status_code=204)
async def logout_all_sessions(
    request: Request,
    response: Response,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        update(Session)
        .where(Session.user_id == user.id, Session.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    _audit(db, "auth.sessions_revoked_all", request, user.id)
    await db.commit()
    response.delete_cookie("tp_refresh", path="/api/v1/auth")


@router.post("/delete-account", status_code=204)
async def delete_account(
    data: DeleteAccountIn,
    request: Request,
    response: Response,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    if data.confirmation != "DELETE":
        raise HTTPException(status_code=400, detail="Type DELETE to confirm account deletion")
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Password is incorrect")
    owned_workspace = await db.scalar(select(Workspace.id).where(Workspace.owner_id == user.id).limit(1))
    owned_project = await db.scalar(select(Project.id).where(Project.owner_id == user.id).limit(1))
    if owned_workspace or owned_project:
        raise HTTPException(
            status_code=409,
            detail="Transfer or delete owned workspaces and projects before deleting the account",
        )
    _audit(db, "auth.account_deleted", request, user.id)
    user.is_active = False
    user.email = f"deleted-{uuid4().hex}@deleted.taskpilot.invalid"
    user.name = "Deleted user"
    user.password_hash = hash_password(new_refresh_token())
    await db.execute(
        update(Session)
        .where(Session.user_id == user.id, Session.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    tokens = list((await db.scalars(select(AccountToken).where(AccountToken.user_id == user.id))).all())
    for token in tokens:
        await db.delete(token)
    await db.commit()
    response.delete_cookie("tp_refresh", path="/api/v1/auth")
