from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.schemas import ORMModel

WorkspaceRole = Literal["owner", "admin", "member", "guest"]
EditableWorkspaceRole = Literal["admin", "member", "guest"]


class WorkspaceUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class WorkspaceMemberOut(BaseModel):
    user_id: UUID
    email: EmailStr
    name: str
    role: WorkspaceRole
    created_at: datetime


class WorkspaceMemberUpdate(BaseModel):
    role: EditableWorkspaceRole


class WorkspaceInviteCreate(BaseModel):
    email: EmailStr
    role: EditableWorkspaceRole = "member"


class WorkspaceInvitationOut(ORMModel):
    id: UUID
    workspace_id: UUID
    email: EmailStr
    role: str
    expires_at: datetime
    accepted_at: datetime | None
    created_at: datetime


class WorkspaceInvitationCreated(WorkspaceInvitationOut):
    token: str


class OwnershipTransferIn(BaseModel):
    user_id: UUID


class ProjectMemberOut(BaseModel):
    user_id: UUID
    email: EmailStr
    name: str
    role: str
    created_at: datetime


class ProjectMemberAdd(BaseModel):
    user_id: UUID
    role: Literal["member", "guest"] = "member"


class UserSummary(ORMModel):
    id: UUID
    email: EmailStr
    name: str


class TaskUserIn(BaseModel):
    user_id: UUID


class SubtaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    assignee_id: UUID | None = None
    due_date: datetime | None = None


class SubtaskPatch(BaseModel):
    version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=240)
    status: Literal["open", "done"] | None = None
    assignee_id: UUID | None = None
    due_date: datetime | None = None
    position: float | None = None


class SubtaskOut(ORMModel):
    id: UUID
    task_id: UUID
    title: str
    status: str
    assignee_id: UUID | None
    due_date: datetime | None
    position: float
    version: int
    created_at: datetime
    updated_at: datetime


class ChecklistCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)


class ChecklistOut(ORMModel):
    id: UUID
    task_id: UUID
    title: str
    position: float
    created_at: datetime


class ChecklistItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    assignee_id: UUID | None = None


class ChecklistItemPatch(BaseModel):
    version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=240)
    completed: bool | None = None
    assignee_id: UUID | None = None
    position: float | None = None


class ChecklistItemOut(ORMModel):
    id: UUID
    checklist_id: UUID
    title: str
    completed: bool
    assignee_id: UUID | None
    position: float
    version: int
    created_at: datetime
    updated_at: datetime


class DependencyCreate(BaseModel):
    blocker_task_id: UUID


class DependencyOut(ORMModel):
    id: UUID
    blocker_task_id: UUID
    blocked_task_id: UUID
    created_by_id: UUID
    created_at: datetime


class TaskDependenciesOut(BaseModel):
    blocked_by: list[DependencyOut]
    blocks: list[DependencyOut]


class CommentPatch(BaseModel):
    body: str = Field(min_length=1, max_length=20000)
