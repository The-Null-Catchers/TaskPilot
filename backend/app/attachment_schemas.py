from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    uploader_id: UUID
    task_id: UUID | None
    comment_id: UUID | None
    project_id: UUID | None
    original_name: str
    safe_name: str
    mime_type: str
    size_bytes: int
    sha256: str
    has_thumbnail: bool = False
    created_at: datetime


class AttachmentUrlOut(BaseModel):
    url: str
    expires_in: int


class StorageUsageOut(BaseModel):
    workspace_id: UUID
    used_bytes: int
    quota_bytes: int
    remaining_bytes: int
