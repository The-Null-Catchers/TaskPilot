from datetime import UTC, datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import current_user
from app.db import get_db
from app.models import Notification, User
from app.schemas import NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
async def list_notifications(unread_only: bool = False, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    query = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    return list((await db.scalars(query.order_by(Notification.created_at.desc()).limit(100))).all())


@router.post("/{notification_id}/read", response_model=NotificationOut)
async def mark_read(notification_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    notification = await db.scalar(select(Notification).where(Notification.id == notification_id, Notification.user_id == user.id))
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.read_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(notification)
    return notification


@router.post("/read-all", status_code=204)
async def mark_all_read(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await db.execute(update(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None)).values(read_at=datetime.now(UTC)))
    await db.commit()
