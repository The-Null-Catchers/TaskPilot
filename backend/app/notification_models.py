import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models import now


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    browser_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mobile_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    digest_frequency: Mapped[str] = mapped_column(String(16), default="instant")
    assignments_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    mentions_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    comments_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    deadlines_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    dependencies_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    __table_args__ = (
        UniqueConstraint("user_id", "channel", "target_hash", name="uq_push_subscription_target"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(20), index=True)
    target_hash: Mapped[str] = mapped_column(String(64), index=True)
    target_ciphertext: Mapped[str] = mapped_column(Text)
    config_ciphertext: Mapped[str] = mapped_column(Text, default="")
    device_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    platform: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class NotificationDispatch(Base):
    __tablename__ = "notification_dispatches"

    notification_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("notifications.id", ondelete="CASCADE"), primary_key=True
    )
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "notification_id",
            "channel",
            "target_key",
            name="uq_notification_delivery_target",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    notification_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("notifications.id", ondelete="CASCADE"), index=True
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("push_subscriptions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    channel: Mapped[str] = mapped_column(String(20), index=True)
    target_key: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
