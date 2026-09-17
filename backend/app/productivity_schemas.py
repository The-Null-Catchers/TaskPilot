from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas import ORMModel, TaskOut

DisplayMode = Literal["list", "board", "calendar"]
SortDirection = Literal["asc", "desc"]
CustomFieldType = Literal["text", "number", "dropdown", "date", "checkbox", "user", "url"]
FavoriteType = Literal["project", "board", "saved_view"]
RecentType = Literal["task", "project", "board"]


class TaskPage(BaseModel):
    items: list[TaskOut]
    total: int
    limit: int
    offset: int


class SavedViewCreate(BaseModel):
    workspace_id: UUID
    project_id: UUID | None = None
    name: str = Field(min_length=1, max_length=120)
    filters: dict[str, Any] = Field(default_factory=dict)
    sort_by: Literal["due_date", "priority", "created_at", "updated_at"] = "updated_at"
    sort_direction: SortDirection = "desc"
    display_mode: DisplayMode = "list"


class SavedViewPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    filters: dict[str, Any] | None = None
    sort_by: Literal["due_date", "priority", "created_at", "updated_at"] | None = None
    sort_direction: SortDirection | None = None
    display_mode: DisplayMode | None = None


class SavedViewOut(BaseModel):
    id: UUID
    workspace_id: UUID
    project_id: UUID | None
    name: str
    filters: dict[str, Any]
    sort_by: str
    sort_direction: str
    display_mode: str
    created_at: datetime
    updated_at: datetime


class FavoriteCreate(BaseModel):
    workspace_id: UUID
    entity_type: FavoriteType
    entity_id: UUID


class FavoriteOut(ORMModel):
    id: UUID
    workspace_id: UUID
    entity_type: str
    entity_id: UUID
    created_at: datetime


class RecentItemCreate(BaseModel):
    workspace_id: UUID
    entity_type: RecentType
    entity_id: UUID


class RecentItemOut(ORMModel):
    id: UUID
    workspace_id: UUID
    entity_type: str
    entity_id: UUID
    viewed_at: datetime


class TimeEntryManual(BaseModel):
    started_at: datetime
    ended_at: datetime
    note: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def validate_range(self):
        if self.ended_at <= self.started_at:
            raise ValueError("ended_at must be after started_at")
        return self


class TimeEntryOut(BaseModel):
    id: UUID
    task_id: UUID
    user_id: UUID
    started_at: datetime
    ended_at: datetime | None
    duration_seconds: int | None
    note: str
    created_at: datetime


class TimeSummary(BaseModel):
    entries: list[TimeEntryOut]
    total_seconds: int
    running_entry: TimeEntryOut | None = None


class CustomFieldCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    field_type: CustomFieldType
    options: list[str] = Field(default_factory=list, max_length=100)
    required: bool = False
    position: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_options(self):
        if self.field_type == "dropdown" and not self.options:
            raise ValueError("dropdown custom fields require at least one option")
        if self.field_type != "dropdown" and self.options:
            raise ValueError("options are only valid for dropdown custom fields")
        if len(set(self.options)) != len(self.options):
            raise ValueError("custom field options must be unique")
        return self


class CustomFieldPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    options: list[str] | None = Field(default=None, max_length=100)
    required: bool | None = None
    position: int | None = Field(default=None, ge=0)


class CustomFieldOut(BaseModel):
    id: UUID
    workspace_id: UUID
    name: str
    field_type: str
    options: list[str]
    required: bool
    position: int
    created_at: datetime
    updated_at: datetime


class CustomFieldValueSet(BaseModel):
    value: Any


class TaskCustomFieldValue(BaseModel):
    field: CustomFieldOut
    value: Any = None
    updated_at: datetime | None = None


class CalendarItem(BaseModel):
    id: str
    kind: Literal["task", "project", "milestone"]
    title: str
    starts_at: datetime
    workspace_id: UUID
    project_id: UUID
    task_id: UUID | None = None
    identifier: str | None = None
    priority: str | None = None
    status: str | None = None


class TimelineTask(BaseModel):
    id: UUID
    identifier: str
    title: str
    status: str
    priority: str
    start_at: datetime
    due_at: datetime | None
    blocked_by: list[UUID] = Field(default_factory=list)


class TimelineMilestone(BaseModel):
    id: UUID
    title: str
    due_at: datetime
    status: str


class TimelineOut(BaseModel):
    project_id: UUID
    tasks: list[TimelineTask]
    milestones: list[TimelineMilestone] = Field(default_factory=list)
