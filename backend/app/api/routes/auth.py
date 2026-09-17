from datetime import UTC, datetime, timedelta
from uuid import uuid4
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import current_user
from app.core.config import settings
from app.core.security import create_access_token, hash_password, new_refresh_token, token_digest, verify_password
from app.db import get_db
from app.models import Session, User, Workspace, WorkspaceMember
from app.schemas import AuthOut, LoginIn, RefreshIn, RegisterIn, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie("tp_refresh", token, max_age=settings.refresh_token_days * 86400, httponly=True, secure=settings.app_env == "production", samesite="lax", path="/api/v1/auth")


async def _issue(db: AsyncSession, user: User, client: str, device_name: str | None, response: Response) -> AuthOut:
    raw = new_refresh_token()
    db.add(Session(user_id=user.id, refresh_token_hash=token_digest(raw), device_name=device_name, expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_days)))
    await db.commit()
    if client == "web":
        _set_refresh_cookie(response, raw)
    return AuthOut(access_token=create_access_token(user.id), expires_in=settings.access_token_minutes * 60, user=UserOut.model_validate(user), refresh_token=raw if client == "mobile" else None)


@router.post("/register", response_model=AuthOut, status_code=201)
async def register(data: RegisterIn, response: Response, db: AsyncSession = Depends(get_db)):
    email = data.email.lower()
    if await db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(email=email, name=data.name.strip(), password_hash=hash_password(data.password))
    db.add(user)
    await db.flush()
    slug = f"{email.split('@')[0].lower().replace('.', '-')}-{str(uuid4())[:6]}"
    workspace = Workspace(name=f"{data.name.strip()}'s Workspace", slug=slug, owner_id=user.id)
    db.add(workspace)
    await db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
    await db.commit()
    await db.refresh(user)
    return await _issue(db, user, "web", None, response)


@router.post("/login", response_model=AuthOut)
async def login(data: LoginIn, response: Response, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == data.email.lower()))
    if not user or not verify_password(data.password, user.password_hash) or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return await _issue(db, user, data.client, data.device_name, response)


@router.post("/refresh", response_model=AuthOut)
async def refresh(data: RefreshIn, response: Response, tp_refresh: str | None = Cookie(default=None), db: AsyncSession = Depends(get_db)):
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
    await db.commit()
    return await _issue(db, user, data.client, data.device_name or session.device_name, response)


@router.post("/logout", status_code=204)
async def logout(response: Response, tp_refresh: str | None = Cookie(default=None), db: AsyncSession = Depends(get_db)):
    if tp_refresh:
        session = await db.scalar(select(Session).where(Session.refresh_token_hash == token_digest(tp_refresh)))
        if session and not session.revoked_at:
            session.revoked_at = datetime.now(UTC)
            await db.commit()
    response.delete_cookie("tp_refresh", path="/api/v1/auth")


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(current_user)):
    return user
