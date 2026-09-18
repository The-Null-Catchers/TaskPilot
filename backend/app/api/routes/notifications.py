from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.core.config import settings
from app.db import get_db
from app.models import Notification, User
from app.notification_models import NotificationPreference, PushSubscription
from app.notification_schemas import (
    NotificationPreferenceOut,
    NotificationPreferencePatch,
    ProviderConfigOut,
    PushSubscriptionCreate,
    PushSubscriptionOut,
)
from app.notification_security import encrypt_json, encrypt_text, target_digest
from app.schemas import NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


async def _preference(db: AsyncSession, user_id: UUID) -> NotificationPreference:
    preference = await db.get(NotificationPreference, user_id)
    if preference is None:
        preference = NotificationPreference(user_id=user_id)
        db.add(preference)
        await db.flush()
    return preference


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    unread_only: bool = False,
    kind: str | None = Query(default=None, max_length=48),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    preference = await _preference(db, user.id)
    if not preference.in_app_enabled:
        await db.commit()
        return []
    query = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    if kind:
        query = query.where(Notification.kind == kind)
    await db.commit()
    return list(
        (
            await db.scalars(
                query.order_by(Notification.created_at.desc()).limit(limit).offset(offset)
            )
        ).all()
    )


@router.get("/unread-count")
async def unread_count(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    preference = await _preference(db, user.id)
    if not preference.in_app_enabled:
        await db.commit()
        return {"count": 0}
    count = int(
        await db.scalar(
            select(func.count(Notification.id)).where(
                Notification.user_id == user.id,
                Notification.read_at.is_(None),
            )
        )
        or 0
    )
    await db.commit()
    return {"count": count}


@router.post("/{notification_id}/read", response_model=NotificationOut)
async def mark_read(
    notification_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    notification = await db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user.id,
        )
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.read_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(notification)
    return notification


@router.post("/read-all", status_code=204)
async def mark_all_read(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    await db.commit()


@router.get("/preferences", response_model=NotificationPreferenceOut)
async def get_preferences(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    preference = await _preference(db, user.id)
    await db.commit()
    await db.refresh(preference)
    return preference


@router.patch("/preferences", response_model=NotificationPreferenceOut)
async def patch_preferences(
    data: NotificationPreferencePatch,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    preference = await _preference(db, user.id)
    for key, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(preference, key, value)
    await db.commit()
    await db.refresh(preference)
    return preference


@router.get("/provider-config", response_model=ProviderConfigOut)
async def provider_config(user: User = Depends(current_user)):
    _ = user
    return ProviderConfigOut(
        web_push_enabled=bool(
            settings.webpush_vapid_private_key
            and settings.webpush_vapid_public_key
            and settings.webpush_vapid_subject
        ),
        web_push_public_key=settings.webpush_vapid_public_key,
        fcm_enabled=bool(settings.fcm_service_account_json),
        apns_enabled=bool(
            settings.apns_team_id
            and settings.apns_key_id
            and settings.apns_private_key
            and settings.apns_bundle_id
        ),
    )


@router.get("/subscriptions", response_model=list[PushSubscriptionOut])
async def list_subscriptions(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    return list(
        (
            await db.scalars(
                select(PushSubscription)
                .where(PushSubscription.user_id == user.id)
                .order_by(PushSubscription.created_at.desc())
            )
        ).all()
    )


@router.post("/subscriptions", response_model=PushSubscriptionOut, status_code=201)
async def register_subscription(
    data: PushSubscriptionCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    if data.channel == "web_push":
        keys = data.config.get("keys") if isinstance(data.config.get("keys"), dict) else {}
        if not keys.get("p256dh") or not keys.get("auth"):
            raise HTTPException(status_code=422, detail="Web Push subscription keys are required")
    digest = target_digest(data.target)
    now = datetime.now(UTC)
    await db.execute(
        update(PushSubscription)
        .where(
            PushSubscription.channel == data.channel,
            PushSubscription.target_hash == digest,
            PushSubscription.user_id != user.id,
            PushSubscription.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    subscription = await db.scalar(
        select(PushSubscription).where(
            PushSubscription.user_id == user.id,
            PushSubscription.channel == data.channel,
            PushSubscription.target_hash == digest,
        )
    )
    if subscription is None:
        subscription = PushSubscription(
            user_id=user.id,
            channel=data.channel,
            target_hash=digest,
            target_ciphertext=encrypt_text(data.target),
            config_ciphertext=encrypt_json(data.config),
            device_name=data.device_name,
            platform=data.platform,
            last_used_at=now,
        )
        db.add(subscription)
    else:
        subscription.target_ciphertext = encrypt_text(data.target)
        subscription.config_ciphertext = encrypt_json(data.config)
        subscription.device_name = data.device_name
        subscription.platform = data.platform
        subscription.last_used_at = now
        subscription.revoked_at = None
    await db.commit()
    await db.refresh(subscription)
    return subscription


@router.delete("/subscriptions/{subscription_id}", status_code=204)
async def revoke_subscription(
    subscription_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    subscription = await db.get(PushSubscription, subscription_id)
    if not subscription or subscription.user_id != user.id:
        raise HTTPException(status_code=404, detail="Push subscription not found")
    subscription.revoked_at = datetime.now(UTC)
    await db.commit()
