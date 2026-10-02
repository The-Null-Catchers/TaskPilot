from datetime import date, datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserOut(ORMModel):
    id: UUID
    email: EmailStr
    name: str
    is_admin: bool


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    name: str = Field(min_length=2, max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str
    client: Literal["web", "mobile"] = "web"
    device_name: str | None = Field(default=None, max_length=160)


class RefreshIn(BaseModel):
    refresh_token: str | None = None
    client: Literal["web", "mobile"] = "web"
    device_name: str | None = Field(default=None, max_length=160)


class AuthOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
    refresh_token: str | None = None


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class WorkspaceOut(ORMModel):
    id: UUID
    name: str
    slug: str
    owner_id: UUID
    created_at: datetime


class ProjectCreate(BaseModel):
    workspace_id: UUID
    name: str = Field(min_length=2, max_length=160)
    key: str = Field(min_length=2, max_length=12, pattern=r"^[A-Za-z][A-Za-z0-9]*$")
    description: str = Field(default="", max_length=10000)
    icon: str | None = Field(default=None, max_length=32)
    color: str = Field(default="#6366f1", pattern=r"^#[0-9A-Fa-f]{6}$")
    start_date: date | None = None
    due_date: date | None = None

    @field_validator("key")
    @classmethod
    def normalize_key(cls, value: str) -> str:
        return value.upper()


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=10000)
    icon: str | None = Field(default=None, max_length=32)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    start_date: date | None = None
    due_date: date | None = None
    status: Literal["planning", "active", "on_hold", "completed"] | None = None


class ProjectOut(ORMModel):
    id: UUID
    workspace_id: UUID
    owner_id: UUID
    name: str
    key: str
    description: str
    icon: str | None
    color: str
    status: str
    start_date: date | None
    due_date: date | None
    archived_at: datetime | None
    created_at: datetime


class ColumnCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class ColumnPatch(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class ColumnReorder(BaseModel):
    column_ids: list[UUID] = Field(min_length=1)


class ColumnOut(ORMModel):
    id: UUID
    project_id: UUID
    name: str
    position: int


class TaskCreate(BaseModel):
    project_id: UUID
    column_id: UUID
    title: str = Field(min_length=1, max_length=240)
    description: str = Field(default="", max_length=50000)
    priority: Literal["urgent", "high", "medium", "low", "none"] = "none"
    start_date: datetime | None = None
    due_date: datetime | None = None
    estimate_minutes: int | None = Field(default=None, ge=0, le=525600)


class TaskPatch(BaseModel):
    version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=50000)
    priority: Literal["urgent", "high", "medium", "low", "none"] | None = None
    status: Literal["open", "in_progress", "review", "done"] | None = None
    start_date: datetime | None = None
    due_date: datetime | None = None
    estimate_minutes: int | None = Field(default=None, ge=0, le=525600)


class TaskMove(BaseModel):
    column_id: UUID
    position: float
    version: int = Field(ge=1)


class TaskOut(ORMModel):
    id: UUID
    workspace_id: UUID
    project_id: UUID
    column_id: UUID
    reporter_id: UUID
    identifier: str
    title: str
    description: str
    priority: str
    status: str
    position: float
    start_date: datetime | None
    due_date: datetime | None
    estimate_minutes: int | None
    version: int
    created_at: datetime
    updated_at: datetime


class BoardOut(BaseModel):
    project: ProjectOut
    columns: list[ColumnOut]
    tasks: list[TaskOut]


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=20000)


class CommentOut(ORMModel):
    id: UUID
    task_id: UUID
    author_id: UUID
    body: str
    edited_at: datetime | None
    created_at: datetime


class NotificationOut(ORMModel):
    id: UUID
    kind: str
    title: str
    body: str
    entity_type: str | None
    entity_id: UUID | None
    read_at: datetime | None
    created_at: datetime
