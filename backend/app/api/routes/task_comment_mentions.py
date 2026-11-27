from uuid import UUID

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.api.routes.task_collaboration import add_comment_with_mentions
from app.db import get_db
from app.models import User
from app.schemas import CommentOut
from app.task_collaboration_schemas import MentionedCommentCreate

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("/{task_id}/comments", response_model=CommentOut, status_code=201)
async def add_comment(
    task_id: UUID,
    data: MentionedCommentCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=64),
):
    return await add_comment_with_mentions(task_id, data, user, db, idempotency_key)
