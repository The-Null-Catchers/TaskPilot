import hashlib
import logging
import unicodedata
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, require_project, require_workspace
from app.attachment_models import Attachment
from app.attachment_schemas import AttachmentOut, AttachmentUrlOut, StorageUsageOut
from app.attachment_security import detect_mime, safe_filename
from app.core.config import settings
from app.db import get_db
from app.models import Comment, Task, User, Workspace
from app.storage import delete_keys, make_thumbnail, presigned_download_url, presigned_preview_url, put_bytes

router = APIRouter(prefix="/attachments", tags=["attachments"])
logger = logging.getLogger("taskpilot.attachments")
EntityType = Literal["task", "comment", "project"]


def attachment_out(item: Attachment) -> AttachmentOut:
    result = AttachmentOut.model_validate(item)
    return result.model_copy(update={"has_thumbnail": item.thumbnail_key is not None})


async def _resolve_entity(
    db: AsyncSession,
    entity_type: EntityType,
    entity_id: UUID,
    user_id: UUID,
    *,
    write: bool,
) -> tuple[UUID, UUID]:
    if entity_type == "project":
        project, _ = await require_project(db, entity_id, user_id, write=write)
        return project.workspace_id, project.id

    if entity_type == "task":
        task = await db.get(Task, entity_id)
        if not task or (write and task.deleted_at is not None):
            raise HTTPException(status_code=404, detail="Task not found")
        project, _ = await require_project(db, task.project_id, user_id, write=write)
        if project.workspace_id != task.workspace_id:
            raise HTTPException(status_code=409, detail="Task workspace mismatch")
        return task.workspace_id, task.project_id

    comment = await db.get(Comment, entity_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    task = await db.get(Task, comment.task_id)
    if not task or (write and task.deleted_at is not None):
        raise HTTPException(status_code=404, detail="Task not found")
    project, _ = await require_project(db, task.project_id, user_id, write=write)
    if project.workspace_id != task.workspace_id:
        raise HTTPException(status_code=409, detail="Task workspace mismatch")
    return task.workspace_id, task.project_id


async def _authorize_attachment(
    db: AsyncSession, item: Attachment, user_id: UUID, *, write: bool
) -> None:
    if item.task_id:
        await _resolve_entity(db, "task", item.task_id, user_id, write=write)
    elif item.comment_id:
        await _resolve_entity(db, "comment", item.comment_id, user_id, write=write)
    elif item.project_id:
        await _resolve_entity(db, "project", item.project_id, user_id, write=write)
    else:
        raise HTTPException(status_code=409, detail="Attachment has no valid parent")


@router.post("", response_model=AttachmentOut, status_code=201)
async def upload_attachment(
    entity_type: EntityType = Form(...),
    entity_id: UUID = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    workspace_id, _ = await _resolve_entity(db, entity_type, entity_id, user.id, write=True)

    workspace = await db.scalar(
        select(Workspace).where(Workspace.id == workspace_id).with_for_update()
    )
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    raw_name = unicodedata.normalize("NFKC", Path(file.filename or "attachment").name)[:255]
    try:
        clean_name = safe_filename(raw_name)
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc

    data = await file.read(settings.storage_max_file_bytes + 1)
    await file.close()
    if len(data) > settings.storage_max_file_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Attachment exceeds {settings.storage_max_file_bytes} bytes",
        )
    try:
        mime_type = detect_mime(data, clean_name)
        thumbnail = make_thumbnail(data, mime_type)
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc

    used = await db.scalar(
        select(func.coalesce(func.sum(Attachment.size_bytes), 0)).where(
            Attachment.workspace_id == workspace_id
        )
    )
    used_bytes = int(used or 0)
    if used_bytes + len(data) > settings.storage_workspace_quota_bytes:
        raise HTTPException(status_code=413, detail="Workspace storage quota exceeded")

    attachment_id = uuid4()
    suffix = Path(clean_name).suffix.lower()
    base_key = f"workspaces/{workspace_id}/attachments/{attachment_id}"
    object_key = f"{base_key}/original{suffix}"
    thumbnail_key = f"{base_key}/thumbnail.jpg" if thumbnail else None

    try:
        await put_bytes(object_key, data, mime_type)
        if thumbnail and thumbnail_key:
            await put_bytes(thumbnail_key, thumbnail, "image/jpeg")
    except Exception as exc:
        logger.exception("Object storage upload failed for workspace %s", workspace_id)
        try:
            await delete_keys(object_key, thumbnail_key)
        except Exception:
            logger.exception("Failed to clean up partial attachment upload")
        raise HTTPException(status_code=503, detail="Attachment storage is unavailable") from exc

    item = Attachment(
        id=attachment_id,
        workspace_id=workspace_id,
        uploader_id=user.id,
        task_id=entity_id if entity_type == "task" else None,
        comment_id=entity_id if entity_type == "comment" else None,
        project_id=entity_id if entity_type == "project" else None,
        object_key=object_key,
        thumbnail_key=thumbnail_key,
        original_name=raw_name or clean_name,
        safe_name=clean_name,
        mime_type=mime_type,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )
    db.add(item)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        try:
            await delete_keys(object_key, thumbnail_key)
        except Exception:
            logger.exception("Failed to clean up attachment after database rollback")
        raise
    await db.refresh(item)
    return attachment_out(item)


@router.get("", response_model=list[AttachmentOut])
async def list_attachments(
    entity_type: EntityType = Query(...),
    entity_id: UUID = Query(...),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await _resolve_entity(db, entity_type, entity_id, user.id, write=False)
    column = {
        "task": Attachment.task_id,
        "comment": Attachment.comment_id,
        "project": Attachment.project_id,
    }[entity_type]
    items = list(
        (await db.scalars(select(Attachment).where(column == entity_id).order_by(Attachment.created_at))).all()
    )
    return [attachment_out(item) for item in items]


@router.get("/{attachment_id}/download", response_model=AttachmentUrlOut)
async def attachment_download(
    attachment_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(Attachment, attachment_id)
    if not item:
        raise HTTPException(status_code=404, detail="Attachment not found")
    await _authorize_attachment(db, item, user.id, write=False)
    try:
        url = await presigned_download_url(item.object_key, item.safe_name, item.mime_type)
    except Exception as exc:
        logger.exception("Could not create attachment download URL")
        raise HTTPException(status_code=503, detail="Attachment storage is unavailable") from exc
    return AttachmentUrlOut(url=url, expires_in=settings.storage_presign_seconds)


@router.get("/{attachment_id}/thumbnail", response_model=AttachmentUrlOut)
async def attachment_thumbnail(
    attachment_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(Attachment, attachment_id)
    if not item or not item.thumbnail_key:
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    await _authorize_attachment(db, item, user.id, write=False)
    try:
        url = await presigned_preview_url(item.thumbnail_key, "image/jpeg")
    except Exception as exc:
        logger.exception("Could not create attachment thumbnail URL")
        raise HTTPException(status_code=503, detail="Attachment storage is unavailable") from exc
    return AttachmentUrlOut(url=url, expires_in=settings.storage_presign_seconds)


@router.delete("/{attachment_id}", status_code=204)
async def delete_attachment(
    attachment_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(Attachment, attachment_id)
    if not item:
        raise HTTPException(status_code=404, detail="Attachment not found")
    await _authorize_attachment(db, item, user.id, write=True)
    try:
        await delete_keys(item.object_key, item.thumbnail_key)
    except Exception as exc:
        logger.exception("Could not delete attachment objects")
        raise HTTPException(status_code=503, detail="Attachment storage is unavailable") from exc
    await db.delete(item)
    await db.commit()


@router.get("/workspace/{workspace_id}/usage", response_model=StorageUsageOut)
async def workspace_storage_usage(
    workspace_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace(db, workspace_id, user.id)
    used = await db.scalar(
        select(func.coalesce(func.sum(Attachment.size_bytes), 0)).where(
            Attachment.workspace_id == workspace_id
        )
    )
    used_bytes = int(used or 0)
    quota = settings.storage_workspace_quota_bytes
    return StorageUsageOut(
        workspace_id=workspace_id,
        used_bytes=used_bytes,
        quota_bytes=quota,
        remaining_bytes=max(0, quota - used_bytes),
    )
