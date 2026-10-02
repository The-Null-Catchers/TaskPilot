from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


Priority = Literal["urgent", "high", "medium", "low", "none"]


class UserSettingPatch(BaseModel):
    theme: Literal["light", "dark", "system"] | None = None
    density: Literal["comfortable", "compact"] | None = None
    week_start: int | None = Field(default=None, ge=0, le=6)
    default_home: Literal["home", "my_tasks", "calendar"] | None = None


class UserSettingOut(ORMModel):
    theme: str
    density: str
    week_start: int
    default_home: str
    updated_at: datetime


class WorkspaceSettingPatch(BaseModel):
    default_project_status: Literal["planning", "active"] | None = None
    default_task_priority: Priority | None = None
    time_tracking_enabled: bool | None = None
    guest_access_enabled: bool | None = None


class WorkspaceSettingOut(ORMModel):
    default_project_status: str
    default_task_priority: str
    time_tracking_enabled: bool
    guest_access_enabled: bool
    updated_at: datetime


class ProjectSettingPatch(BaseModel):
    default_task_priority: Priority | None = None
    time_tracking_enabled: bool | None = None
    auto_complete_on_done_column: bool | None = None
    show_completed_tasks: bool | None = None


class ProjectSettingOut(ORMModel):
    default_task_priority: str
    time_tracking_enabled: bool
    auto_complete_on_done_column: bool
    show_completed_tasks: bool
    updated_at: datetime
