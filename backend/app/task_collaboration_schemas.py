from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.collaboration_schemas import UserSummary
from app.schemas import ORMModel, TaskOut


class LabelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    color: str = Field(default="#64748b", pattern=r"^#[0-9A-Fa-f]{6}$")


class LabelOut(ORMModel):
    id: UUID
    workspace_id: UUID
    name: str
    color: str


class TaskLabelIn(BaseModel):
    label_id: UUID


class CommentReactionIn(BaseModel):
    emoji: str = Field(min_length=1, max_length=16)


class CommentReactionOut(ORMModel):
    id: UUID
    comment_id: UUID
    user_id: UUID
    emoji: str
    created_at: datetime


class MentionedCommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=20000)


class TaskDuplicateIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    include_subtasks: bool = True
    include_checklists: bool = True
    include_assignees: bool = True
    include_labels: bool = True


class ConvertSubtaskIn(BaseModel):
    column_id: UUID | None = None


class TaskCollaborationState(BaseModel):
    blocked: bool
    blocking_task_ids: list[UUID]
    watching: bool
    watcher_count: int


class ActivityItemOut(ORMModel):
    id: UUID
    actor_id: UUID
    action: str
    summary: str
    created_at: datetime


class DuplicateTaskOut(BaseModel):
    task: TaskOut
    copied_subtasks: int
    copied_checklists: int


AllowedReaction = Literal["👍", "👎", "❤️", "🎉", "😄", "🚀", "👀"]
