import re
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, require_project, require_workspace
from app.collaboration_models import Checklist, ChecklistItem, Subtask, TaskDependency, TaskWatcher
from app.db import get_db
from app.models import (
    ActivityLog,
    BoardColumn,
    Comment,
    Label,
    Notification,
    Project,
    Task,
    TaskAssignee,
    TaskLabel,
    User,
    WorkspaceMember,
)
from app.realtime import publish
from app.schemas import CommentOut, TaskOut
from app.task_collaboration_models import CommentReaction
from app.task_collaboration_schemas import (
    ActivityItemOut,
    CommentReactionIn,
    CommentReactionOut,
    ConvertSubtaskIn,
    DuplicateTaskOut,
    LabelCreate,
    LabelOut,
    MentionedCommentCreate,
    TaskCollaborationState,
    TaskDuplicateIn,
    TaskLabelIn,
    UserSummary,
)

router = APIRouter(tags=["task-collaboration"])
MENTION_RE = re.compile(r"@\[([0-9a-fA-F-]{36})\]")
ALLOWED_REACTIONS = {"👍", "👎", "❤️", "🎉", "😄", "🚀", "👀"}


async def _task_access(db: AsyncSession, task_id: UUID, user_id: UUID, *, write: bool = False, include_archived: bool = False) -> Task:
    task = await db.get(Task, task_id)
    if not task or (task.deleted_at is not None and not include_archived):
        raise HTTPException(status_code=404, detail="Task not found")
    await require_project(db, task.project_id, user_id, write=write)
    return task


async def _workspace_user(db: AsyncSession, workspace_id: UUID, user_id: UUID) -> User:
    member = await db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    user = await db.get(User, user_id)
    if not member or not user or not user.is_active:
        raise HTTPException(status_code=400, detail="User must be an active workspace member")
    return user


def _activity(db: AsyncSession, task: Task, actor_id: UUID, action: str, summary: str) -> None:
    db.add(
        ActivityLog(
            workspace_id=task.workspace_id,
            project_id=task.project_id,
            task_id=task.id,
            actor_id=actor_id,
            action=action,
            summary=summary,
        )
    )


def extract_mention_ids(body: str) -> set[UUID]:
    ids: set[UUID] = set()
    for value in MENTION_RE.findall(body):
        try:
            ids.add(UUID(value))
        except ValueError:
            continue
    return ids


async def _notify_mentions(db: AsyncSession, task: Task, author: User, body: str) -> None:
    for mentioned_id in extract_mention_ids(body):
        if mentioned_id == author.id:
            continue
        try:
            mentioned = await _workspace_user(db, task.workspace_id, mentioned_id)
        except HTTPException:
            continue
        db.add(
            Notification(
                user_id=mentioned.id,
                kind="task.mention",
                title=f"{author.name} mentioned you in {task.identifier}",
                body=body[:500],
                entity_type="task",
                entity_id=task.id,
            )
        )


@router.get("/workspaces/{workspace_id}/labels", response_model=list[LabelOut])
async def list_workspace_labels(workspace_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await require_workspace(db, workspace_id, user.id)
    return list((await db.scalars(select(Label).where(Label.workspace_id == workspace_id).order_by(Label.name))).all())


@router.post("/workspaces/{workspace_id}/labels", response_model=LabelOut, status_code=201)
async def create_workspace_label(workspace_id: UUID, data: LabelCreate, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await require_workspace(db, workspace_id, user.id, write=True)
    existing = await db.scalar(
        select(Label).where(Label.workspace_id == workspace_id, func.lower(Label.name) == data.name.strip().lower())
    )
    if existing:
        return existing
    label = Label(workspace_id=workspace_id, name=data.name.strip(), color=data.color)
    db.add(label)
    await db.commit()
    await db.refresh(label)
    return label


@router.get("/tasks/{task_id}/labels", response_model=list[LabelOut])
async def list_task_labels(task_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await _task_access(db, task_id, user.id)
    query = select(Label).join(TaskLabel, TaskLabel.label_id == Label.id).where(TaskLabel.task_id == task_id).order_by(Label.name)
    return list((await db.scalars(query)).all())


@router.post("/tasks/{task_id}/labels", response_model=LabelOut)
async def add_task_label(task_id: UUID, data: TaskLabelIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    task = await _task_access(db, task_id, user.id, write=True)
    label = await db.get(Label, data.label_id)
    if not label or label.workspace_id != task.workspace_id:
        raise HTTPException(status_code=400, detail="Label does not belong to task workspace")
    existing = await db.scalar(select(TaskLabel.id).where(TaskLabel.task_id == task.id, TaskLabel.label_id == label.id))
    if existing is None:
        db.add(TaskLabel(task_id=task.id, label_id=label.id))
        _activity(db, task, user.id, "task.label.added", f"Added label {label.name} to {task.identifier}")
        await db.commit()
        await publish(task.workspace_id, "task.label.added", {"task_id": str(task.id), "label_id": str(label.id)})
    return label


@router.delete("/tasks/{task_id}/labels/{label_id}", status_code=204)
async def remove_task_label(task_id: UUID, label_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    task = await _task_access(db, task_id, user.id, write=True)
    row = await db.scalar(select(TaskLabel).where(TaskLabel.task_id == task.id, TaskLabel.label_id == label_id))
    if not row:
        raise HTTPException(status_code=404, detail="Task label not found")
    await db.delete(row)
    _activity(db, task, user.id, "task.label.removed", f"Removed a label from {task.identifier}")
    await db.commit()
    await publish(task.workspace_id, "task.label.removed", {"task_id": str(task.id), "label_id": str(label_id)})


@router.get("/tasks/{task_id}/watchers", response_model=list[UserSummary])
async def list_watchers(task_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await _task_access(db, task_id, user.id)
    query = select(User).join(TaskWatcher, TaskWatcher.user_id == User.id).where(TaskWatcher.task_id == task_id).order_by(User.name)
    return list((await db.scalars(query)).all())


@router.get("/tasks/{task_id}/collaboration-state", response_model=TaskCollaborationState)
async def collaboration_state(task_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    task = await _task_access(db, task_id, user.id)
    blocker_ids = list((await db.scalars(
        select(TaskDependency.blocker_task_id)
        .join(Task, Task.id == TaskDependency.blocker_task_id)
        .where(TaskDependency.blocked_task_id == task.id, Task.status != "done", Task.deleted_at.is_(None))
    )).all())
    watcher_count = await db.scalar(select(func.count(TaskWatcher.id)).where(TaskWatcher.task_id == task.id)) or 0
    watching = await db.scalar(select(TaskWatcher.id).where(TaskWatcher.task_id == task.id, TaskWatcher.user_id == user.id)) is not None
    return TaskCollaborationState(blocked=bool(blocker_ids), blocking_task_ids=blocker_ids, watching=watching, watcher_count=watcher_count)


@router.post("/tasks/{task_id}/comments/rich", response_model=CommentOut, status_code=201)
async def add_comment_with_mentions(task_id: UUID, data: MentionedCommentCreate, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    task = await _task_access(db, task_id, user.id)
    body = data.body.strip()
    comment = Comment(task_id=task.id, author_id=user.id, body=body)
    db.add(comment)
    await db.flush()
    await _notify_mentions(db, task, user, body)
    watcher_ids = set((await db.scalars(select(TaskWatcher.user_id).where(TaskWatcher.task_id == task.id, TaskWatcher.user_id != user.id))).all())
    mentioned_ids = extract_mention_ids(body)
    for watcher_id in watcher_ids - mentioned_ids:
        db.add(Notification(user_id=watcher_id, kind="task.comment", title=f"New comment on {task.identifier}", body=body[:500], entity_type="task", entity_id=task.id))
    _activity(db, task, user.id, "comment.created", f"Commented on {task.identifier}")
    await db.commit()
    await db.refresh(comment)
    payload = CommentOut.model_validate(comment).model_dump(mode="json")
    await publish(task.workspace_id, "comment.created", payload)
    return comment


@router.get("/tasks/{task_id}/comments/{comment_id}/reactions", response_model=list[CommentReactionOut])
async def list_comment_reactions(task_id: UUID, comment_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    task = await _task_access(db, task_id, user.id)
    comment = await db.scalar(select(Comment.id).where(Comment.id == comment_id, Comment.task_id == task.id))
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    return list((await db.scalars(select(CommentReaction).where(CommentReaction.comment_id == comment_id).order_by(CommentReaction.created_at))).all())


@router.post("/tasks/{task_id}/comments/{comment_id}/reactions", response_model=CommentReactionOut, status_code=201)
async def add_comment_reaction(task_id: UUID, comment_id: UUID, data: CommentReactionIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    task = await _task_access(db, task_id, user.id)
    comment = await db.scalar(select(Comment).where(Comment.id == comment_id, Comment.task_id == task.id))
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    if data.emoji not in ALLOWED_REACTIONS:
        raise HTTPException(status_code=400, detail="Unsupported reaction")
    existing = await db.scalar(select(CommentReaction).where(CommentReaction.comment_id == comment_id, CommentReaction.user_id == user.id, CommentReaction.emoji == data.emoji))
    if existing:
        return existing
    reaction = CommentReaction(comment_id=comment_id, user_id=user.id, emoji=data.emoji)
    db.add(reaction)
    await db.commit()
    await db.refresh(reaction)
    await publish(task.workspace_id, "comment.reaction.added", {"comment_id": str(comment_id), "user_id": str(user.id), "emoji": data.emoji})
    return reaction


@router.delete("/tasks/{task_id}/comments/{comment_id}/reactions/{reaction_id}", status_code=204)
async def delete_comment_reaction(task_id: UUID, comment_id: UUID, reaction_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    task = await _task_access(db, task_id, user.id)
    reaction = await db.scalar(select(CommentReaction).where(CommentReaction.id == reaction_id, CommentReaction.comment_id == comment_id))
    if not reaction:
        raise HTTPException(status_code=404, detail="Reaction not found")
    if reaction.user_id != user.id:
        raise HTTPException(status_code=403, detail="You can only remove your own reaction")
    await db.delete(reaction)
    await db.commit()
    await publish(task.workspace_id, "comment.reaction.removed", {"comment_id": str(comment_id), "reaction_id": str(reaction_id)})


@router.get("/tasks/{task_id}/activity", response_model=list[ActivityItemOut])
async def task_activity(task_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await _task_access(db, task_id, user.id, include_archived=True)
    query = select(ActivityLog).where(ActivityLog.task_id == task_id).order_by(ActivityLog.created_at.desc()).limit(200)
    return list((await db.scalars(query)).all())


@router.post("/tasks/{task_id}/archive", response_model=TaskOut)
async def archive_task(task_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    task = await _task_access(db, task_id, user.id, write=True)
    task.deleted_at = datetime.now(UTC)
    task.version += 1
    _activity(db, task, user.id, "task.archived", f"Archived {task.identifier}")
    await db.commit()
    await db.refresh(task)
    await publish(task.workspace_id, "task.archived", {"task_id": str(task.id)})
    return task


@router.post("/tasks/{task_id}/restore", response_model=TaskOut)
async def restore_task(task_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    task = await _task_access(db, task_id, user.id, write=True, include_archived=True)
    if task.deleted_at is None:
        return task
    task.deleted_at = None
    task.version += 1
    _activity(db, task, user.id, "task.restored", f"Restored {task.identifier}")
    await db.commit()
    await db.refresh(task)
    await publish(task.workspace_id, "task.restored", TaskOut.model_validate(task).model_dump(mode="json"))
    return task


@router.post("/tasks/{task_id}/duplicate", response_model=DuplicateTaskOut, status_code=201)
async def duplicate_task(task_id: UUID, data: TaskDuplicateIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    source = await _task_access(db, task_id, user.id, write=True)
    project = await db.scalar(select(Project).where(Project.id == source.project_id).with_for_update())
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project.task_counter += 1
    max_position = await db.scalar(select(func.max(Task.position)).where(Task.column_id == source.column_id, Task.deleted_at.is_(None))) or 0
    clone = Task(
        workspace_id=source.workspace_id,
        project_id=source.project_id,
        column_id=source.column_id,
        reporter_id=user.id,
        number=project.task_counter,
        identifier=f"{project.key}-{project.task_counter}",
        title=(data.title or f"{source.title} (copy)").strip(),
        description=source.description,
        priority=source.priority,
        status="open",
        position=max_position + 1000,
        due_date=source.due_date,
    )
    db.add(clone)
    await db.flush()
    if data.include_assignees:
        for uid in (await db.scalars(select(TaskAssignee.user_id).where(TaskAssignee.task_id == source.id))).all():
            db.add(TaskAssignee(task_id=clone.id, user_id=uid))
    if data.include_labels:
        for lid in (await db.scalars(select(TaskLabel.label_id).where(TaskLabel.task_id == source.id))).all():
            db.add(TaskLabel(task_id=clone.id, label_id=lid))
    copied_subtasks = 0
    if data.include_subtasks:
        subtasks = (await db.scalars(select(Subtask).where(Subtask.task_id == source.id).order_by(Subtask.position))).all()
        for item in subtasks:
            db.add(Subtask(task_id=clone.id, title=item.title, status="open", assignee_id=item.assignee_id, due_date=item.due_date, position=item.position))
            copied_subtasks += 1
    copied_checklists = 0
    if data.include_checklists:
        lists = (await db.scalars(select(Checklist).where(Checklist.task_id == source.id).order_by(Checklist.position))).all()
        for checklist in lists:
            new_list = Checklist(task_id=clone.id, title=checklist.title, position=checklist.position)
            db.add(new_list)
            await db.flush()
            items = (await db.scalars(select(ChecklistItem).where(ChecklistItem.checklist_id == checklist.id).order_by(ChecklistItem.position))).all()
            for item in items:
                db.add(ChecklistItem(checklist_id=new_list.id, title=item.title, completed=False, assignee_id=item.assignee_id, position=item.position))
            copied_checklists += 1
    _activity(db, clone, user.id, "task.duplicated", f"Duplicated {source.identifier} as {clone.identifier}")
    await db.commit()
    await db.refresh(clone)
    await publish(clone.workspace_id, "task.created", TaskOut.model_validate(clone).model_dump(mode="json"))
    return DuplicateTaskOut(task=TaskOut.model_validate(clone), copied_subtasks=copied_subtasks, copied_checklists=copied_checklists)


@router.post("/tasks/{task_id}/subtasks/{subtask_id}/convert", response_model=TaskOut, status_code=201)
async def convert_subtask(task_id: UUID, subtask_id: UUID, data: ConvertSubtaskIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    parent = await _task_access(db, task_id, user.id, write=True)
    subtask = await db.scalar(select(Subtask).where(Subtask.id == subtask_id, Subtask.task_id == parent.id))
    if not subtask:
        raise HTTPException(status_code=404, detail="Subtask not found")
    column_id = data.column_id or parent.column_id
    column = await db.get(BoardColumn, column_id)
    if not column or column.project_id != parent.project_id:
        raise HTTPException(status_code=400, detail="Column does not belong to project")
    project = await db.scalar(select(Project).where(Project.id == parent.project_id).with_for_update())
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project.task_counter += 1
    max_position = await db.scalar(select(func.max(Task.position)).where(Task.column_id == column.id, Task.deleted_at.is_(None))) or 0
    task = Task(
        workspace_id=parent.workspace_id,
        project_id=parent.project_id,
        column_id=column.id,
        reporter_id=user.id,
        number=project.task_counter,
        identifier=f"{project.key}-{project.task_counter}",
        title=subtask.title,
        description=f"Converted from subtask of {parent.identifier}.",
        priority=parent.priority,
        status="open",
        position=max_position + 1000,
        due_date=subtask.due_date,
    )
    db.add(task)
    await db.flush()
    if subtask.assignee_id:
        db.add(TaskAssignee(task_id=task.id, user_id=subtask.assignee_id))
    await db.delete(subtask)
    _activity(db, parent, user.id, "subtask.converted", f"Converted a subtask into {task.identifier}")
    _activity(db, task, user.id, "task.created", f"Created from subtask of {parent.identifier}")
    await db.commit()
    await db.refresh(task)
    await publish(task.workspace_id, "task.created", TaskOut.model_validate(task).model_dump(mode="json"))
    return task
