import json
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_session_user, current_user, require_workspace
from app.collaboration_models import AuditLog
from app.core.config import settings
from app.db import get_db
from app.integration_models import PersonalApiToken, WebhookDelivery, WorkspaceWebhook
from app.integration_security import (
    encrypt_secret,
    new_personal_token,
    new_webhook_secret,
    personal_token_digest,
    secret_digest,
)
from app.models import User
from app.webhook_security import validate_webhook_url

router = APIRouter(tags=["integrations"])

ALLOWED_SCOPES = {"read", "write"}


class TokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scopes: list[Literal["read", "write"]] = Field(default_factory=lambda: ["read"])
    expires_at: datetime | None = None


class WebhookCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    url: str = Field(min_length=8, max_length=1000)
    events: list[str] = Field(default_factory=lambda: ["*"])


class WebhookPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    url: str | None = Field(default=None, min_length=8, max_length=1000)
    events: list[str] | None = None
    active: bool | None = None


def _audit(
    db: AsyncSession,
    request: Request,
    action: str,
    actor_id: UUID,
    *,
    workspace_id: UUID | None = None,
    metadata: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_id=actor_id,
            workspace_id=workspace_id,
            action=action,
            ip_address=request.client.host if request.client else None,
            metadata_json=json.dumps(metadata or {}),
        )
    )


def _validate_expiry(expires_at: datetime | None) -> datetime | None:
    if expires_at is None:
        return None
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= datetime.now(UTC):
        raise HTTPException(status_code=422, detail="Token expiry must be in the future")
    return expires_at


def _events(values: list[str]) -> str:
    cleaned = []
    for value in values:
        event = value.strip()
        if not event or len(event) > 80:
            raise HTTPException(status_code=422, detail="Webhook event is invalid")
        if event != "*" and not all(char.isalnum() or char in {".", "_", "-", "*"} for char in event):
            raise HTTPException(status_code=422, detail="Webhook event is invalid")
        if event not in cleaned:
            cleaned.append(event)
    if not cleaned or len(cleaned) > 30:
        raise HTTPException(status_code=422, detail="Webhook requires between 1 and 30 events")
    return ",".join(cleaned)


def _token_out(item: PersonalApiToken) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "prefix": item.token_prefix,
        "scopes": [scope for scope in item.scopes.split(",") if scope],
        "expires_at": item.expires_at,
        "last_used_at": item.last_used_at,
        "revoked_at": item.revoked_at,
        "created_at": item.created_at,
    }


def _webhook_out(item: WorkspaceWebhook) -> dict:
    return {
        "id": item.id,
        "workspace_id": item.workspace_id,
        "name": item.name,
        "url": item.url,
        "events": [event for event in item.events.split(",") if event],
        "active": item.active,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


@router.get("/integrations/tokens")
async def list_personal_tokens(
    user: User = Depends(current_session_user), db: AsyncSession = Depends(get_db)
):
    items = list(
        (
            await db.scalars(
                select(PersonalApiToken)
                .where(PersonalApiToken.user_id == user.id)
                .order_by(PersonalApiToken.created_at.desc())
            )
        ).all()
    )
    return [_token_out(item) for item in items]


@router.post("/integrations/tokens", status_code=201)
async def create_personal_token(
    data: TokenCreate,
    request: Request,
    user: User = Depends(current_session_user),
    db: AsyncSession = Depends(get_db),
):
    scopes = set(data.scopes)
    if not scopes or not scopes.issubset(ALLOWED_SCOPES):
        raise HTTPException(status_code=422, detail="Invalid API token scopes")
    scopes.add("read")
    raw = new_personal_token()
    item = PersonalApiToken(
        user_id=user.id,
        name=data.name.strip(),
        token_prefix=raw[:18],
        token_hash=personal_token_digest(raw),
        scopes=",".join(sorted(scopes)),
        expires_at=_validate_expiry(data.expires_at),
    )
    db.add(item)
    await db.flush()
    _audit(
        db,
        request,
        "integration.api_token.created",
        user.id,
        metadata={"token_id": str(item.id), "name": item.name, "scopes": sorted(scopes)},
    )
    await db.commit()
    await db.refresh(item)
    return {**_token_out(item), "token": raw}


@router.delete("/integrations/tokens/{token_id}", status_code=204)
async def revoke_personal_token(
    token_id: UUID,
    request: Request,
    user: User = Depends(current_session_user),
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(PersonalApiToken, token_id)
    if not item or item.user_id != user.id:
        raise HTTPException(status_code=404, detail="API token not found")
    if item.revoked_at is None:
        item.revoked_at = datetime.now(UTC)
        _audit(
            db,
            request,
            "integration.api_token.revoked",
            user.id,
            metadata={"token_id": str(item.id), "name": item.name},
        )
        await db.commit()


@router.get("/workspaces/{workspace_id}/webhooks")
async def list_webhooks(
    workspace_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace(db, workspace_id, user.id, allowed={"owner", "admin"})
    items = list(
        (
            await db.scalars(
                select(WorkspaceWebhook)
                .where(WorkspaceWebhook.workspace_id == workspace_id)
                .order_by(WorkspaceWebhook.created_at.desc())
            )
        ).all()
    )
    return [_webhook_out(item) for item in items]


@router.post("/workspaces/{workspace_id}/webhooks", status_code=201)
async def create_webhook(
    workspace_id: UUID,
    data: WebhookCreate,
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace(db, workspace_id, user.id, allowed={"owner", "admin"}, write=True)
    try:
        url = validate_webhook_url(data.url, production=settings.app_env == "production")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    secret = new_webhook_secret()
    item = WorkspaceWebhook(
        workspace_id=workspace_id,
        created_by=user.id,
        name=data.name.strip(),
        url=url,
        secret_hash=secret_digest(secret),
        secret_ciphertext=encrypt_secret(secret),
        events=_events(data.events),
    )
    db.add(item)
    await db.flush()
    _audit(
        db,
        request,
        "integration.webhook.created",
        user.id,
        workspace_id=workspace_id,
        metadata={"webhook_id": str(item.id), "name": item.name, "events": item.events.split(",")},
    )
    await db.commit()
    await db.refresh(item)
    return {**_webhook_out(item), "secret": secret}


@router.patch("/workspaces/{workspace_id}/webhooks/{webhook_id}")
async def patch_webhook(
    workspace_id: UUID,
    webhook_id: UUID,
    data: WebhookPatch,
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace(db, workspace_id, user.id, allowed={"owner", "admin"}, write=True)
    item = await db.get(WorkspaceWebhook, webhook_id)
    if not item or item.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Webhook not found")
    values = data.model_dump(exclude_unset=True)
    if "name" in values:
        item.name = values["name"].strip()
    if "url" in values:
        try:
            item.url = validate_webhook_url(values["url"], production=settings.app_env == "production")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    if "events" in values:
        item.events = _events(values["events"])
    if "active" in values:
        item.active = values["active"]
    _audit(
        db,
        request,
        "integration.webhook.updated",
        user.id,
        workspace_id=workspace_id,
        metadata={"webhook_id": str(item.id), "changed_fields": sorted(values)},
    )
    await db.commit()
    await db.refresh(item)
    return _webhook_out(item)


@router.post("/workspaces/{workspace_id}/webhooks/{webhook_id}/rotate-secret")
async def rotate_webhook_secret(
    workspace_id: UUID,
    webhook_id: UUID,
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace(db, workspace_id, user.id, allowed={"owner", "admin"}, write=True)
    item = await db.get(WorkspaceWebhook, webhook_id)
    if not item or item.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Webhook not found")
    secret = new_webhook_secret()
    item.secret_hash = secret_digest(secret)
    item.secret_ciphertext = encrypt_secret(secret)
    _audit(
        db,
        request,
        "integration.webhook.secret_rotated",
        user.id,
        workspace_id=workspace_id,
        metadata={"webhook_id": str(item.id)},
    )
    await db.commit()
    return {"secret": secret}


@router.delete("/workspaces/{workspace_id}/webhooks/{webhook_id}", status_code=204)
async def delete_webhook(
    workspace_id: UUID,
    webhook_id: UUID,
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace(db, workspace_id, user.id, allowed={"owner", "admin"}, write=True)
    item = await db.get(WorkspaceWebhook, webhook_id)
    if not item or item.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Webhook not found")
    metadata = {"webhook_id": str(item.id), "name": item.name}
    await db.delete(item)
    _audit(
        db,
        request,
        "integration.webhook.deleted",
        user.id,
        workspace_id=workspace_id,
        metadata=metadata,
    )
    await db.commit()


@router.get("/workspaces/{workspace_id}/webhooks/{webhook_id}/deliveries")
async def list_webhook_deliveries(
    workspace_id: UUID,
    webhook_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace(db, workspace_id, user.id, allowed={"owner", "admin"})
    item = await db.get(WorkspaceWebhook, webhook_id)
    if not item or item.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Webhook not found")
    deliveries = list(
        (
            await db.scalars(
                select(WebhookDelivery)
                .where(WebhookDelivery.webhook_id == webhook_id)
                .order_by(WebhookDelivery.created_at.desc())
                .limit(limit)
            )
        ).all()
    )
    return [
        {
            "id": delivery.id,
            "activity_id": delivery.activity_id,
            "event": delivery.event,
            "status": delivery.status,
            "attempts": delivery.attempts,
            "response_status": delivery.response_status,
            "last_error": delivery.last_error,
            "next_attempt_at": delivery.next_attempt_at,
            "delivered_at": delivery.delivered_at,
            "created_at": delivery.created_at,
        }
        for delivery in deliveries
    ]
