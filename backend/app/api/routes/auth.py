import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.account_models import AccountSecurity, SessionMetadata
from app.api.deps import current_user
from app.collaboration_models import AuditLog
from app.core.config import settings
from app.core.security import create_access_token, hash_password, new_refresh_token, token_digest, verify_password
from app.db import get_db
from app.models import Session, User, Workspace, WorkspaceMember
from app.security_controls import client_ip, enforce_rate_limit
from app.schemas import AuthOut, LoginIn, RefreshIn, RegisterIn, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        "tp_refresh",
        token,
        max_age=settings.refresh_token_days * 86400,
        httponly=True,
        secure=settings.app_env == "production",
        samesite=settings.refresh_cookie_samesite,
        path="/api/v1/auth",
    )


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _audit(db: AsyncSession, action: str, request: Request, actor_id=None, metadata=None) -> None:
    db.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            ip_address=_ip(request),
            metadata_json=json.dumps(metadata or {}),
        )
    )


async def _issue(
    db: AsyncSession,
    user: User,
    client: str,
    device_name: str | None,
    response: Response,
    request: Request,
) -> AuthOut:
    raw = new_refresh_token()
    session = Session(
        user_id=user.id,
        refresh_token_hash=token_digest(raw),
        device_name=device_name,
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_days),
    )
    db.add(session)
    await db.flush()
    db.add(
        SessionMetadata(
            session_id=session.id,
            ip_address=_ip(request),
            user_agent=request.headers.get("user-agent", "")[:500] or None,
            last_used_at=datetime.now(UTC),
        )
    )
    await db.commit()
    if client == "web":
        _set_refresh_cookie(response, raw)
    return AuthOut(
        access_token=create_access_token(user.id),
        expires_in=settings.access_token_minutes * 60,
        user=UserOut.model_validate(user),
        refresh_token=raw if client == "mobile" else None,
    )


@router.post("/register", response_model=AuthOut, status_code=201)
async def register(
    data: RegisterIn,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(request, bucket="register", limit=10, window_seconds=3600)
    email = data.email.lower()
    if await db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(email=email, name=data.name.strip(), password_hash=hash_password(data.password))
    db.add(user)
    await db.flush()
    db.add(AccountSecurity(user_id=user.id))
    slug = f"{email.split('@')[0].lower().replace('.', '-')}-{str(uuid4())[:6]}"
    workspace = Workspace(name=f"{data.name.strip()}'s Workspace", slug=slug, owner_id=user.id)
    db.add(workspace)
    await db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
    _audit(db, "auth.register", request, user.id)
    await db.commit()
    await db.refresh(user)
    return await _issue(db, user, "web", None, response, request)


@router.post("/login", response_model=AuthOut)
async def login(
    data: LoginIn,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    email = data.email.lower()
    await enforce_rate_limit(request, bucket="login_ip", limit=60, window_seconds=300)
    await enforce_rate_limit(
        request,
        bucket="login_account",
        limit=20,
        window_seconds=300,
        subject=f"{client_ip(request)}:{email}",
    )
    user = await db.scalar(select(User).where(User.email == email))
    if not user or not verify_password(data.password, user.password_hash) or not user.is_active:
        _audit(
            db,
            "auth.login_failed",
            request,
            user.id if user else None,
            {"email": email},
        )
        await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    previous_session = await db.scalar(select(Session.id).where(Session.user_id == user.id).limit(1))
    known_context = await db.scalar(
        select(SessionMetadata.session_id)
        .join(Session, Session.id == SessionMetadata.session_id)
        .where(
            Session.user_id == user.id,
            SessionMetadata.ip_address == _ip(request),
            Session.device_name == data.device_name,
        )
        .limit(1)
    )
    if previous_session and known_context is None:
        _audit(
            db,
            "auth.suspicious_login",
            request,
            user.id,
            {"reason": "new_device_or_network", "device_name": data.device_name},
        )
    _audit(db, "auth.login", request, user.id, {"device_name": data.device_name})
    await db.commit()
    return await _issue(db, user, data.client, data.device_name, response, request)


@router.post("/refresh", response_model=AuthOut)
async def refresh(
    data: RefreshIn,
    request: Request,
    response: Response,
    tp_refresh: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(request, bucket="refresh", limit=120, window_seconds=60)
    raw = data.refresh_token or tp_refresh
    if not raw:
        raise HTTPException(status_code=401, detail="Refresh token required")
    session = await db.scalar(select(Session).where(Session.refresh_token_hash == token_digest(raw)))
    if not session or session.revoked_at or session.expires_at <= datetime.now(UTC):
        raise HTTPException(status_code=401, detail="Refresh token invalid")
    user = await db.get(User, session.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Account unavailable")
    session.revoked_at = datetime.now(UTC)
    metadata = await db.get(SessionMetadata, session.id)
    if metadata:
        metadata.last_used_at = datetime.now(UTC)
    await db.commit()
    return await _issue(
        db,
        user,
        data.client,
        data.device_name or session.device_name,
        response,
        request,
    )


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    tp_refresh: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if tp_refresh:
        session = await db.scalar(select(Session).where(Session.refresh_token_hash == token_digest(tp_refresh)))
        if session and not session.revoked_at:
            session.revoked_at = datetime.now(UTC)
            _audit(db, "auth.logout", request, session.user_id, {"session_id": str(session.id)})
            await db.commit()
    response.delete_cookie("tp_refresh", path="/api/v1/auth")


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(current_user)):
    return user
