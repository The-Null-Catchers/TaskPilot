import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, Uuid, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models import now


class UserSetting(Base):
    __tablename__ = "user_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    theme: Mapped[str] = mapped_column(String(16), default="system")
    density: Mapped[str] = mapped_column(String(16), default="comfortable")
    week_start: Mapped[int] = mapped_column(Integer, default=1)
    default_home: Mapped[str] = mapped_column(String(32), default="home")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )


class WorkspaceSetting(Base):
    __tablename__ = "workspace_settings"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    default_project_status: Mapped[str] = mapped_column(String(24), default="active")
    default_task_priority: Mapped[str] = mapped_column(String(16), default="none")
    time_tracking_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    guest_access_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )


class ProjectSetting(Base):
    __tablename__ = "project_settings"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    default_task_priority: Mapped[str] = mapped_column(String(16), default="none")
    time_tracking_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_complete_on_done_column: Mapped[bool] = mapped_column(Boolean, default=False)
    show_completed_tasks: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )
