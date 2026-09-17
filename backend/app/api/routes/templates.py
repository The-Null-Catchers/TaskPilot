from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, require_project, require_workspace
from app.collaboration_models import Checklist, ChecklistItem, ProjectMember
from app.db import get_db
from app.models import BoardColumn, Label, Project, Task, TaskLabel, User
from app.realtime import publish

router = APIRouter(prefix="/templates", tags=["templates"])

TASK_TEMPLATES = {
    "bug-report": {
        "name": "Bug Report",
        "description": "## Summary\nDescribe the problem.\n\n## Steps to reproduce\n1. \n2. \n3. \n\n## Expected behavior\n\n## Actual behavior\n\n## Environment\n",
        "priority": "high",
        "labels": [("Bug", "#ef4444")],
        "checklists": [("Verification", ["Reproduce the issue", "Add or update tests", "Verify the fix"])],
    },
    "feature-request": {
        "name": "Feature Request",
        "description": "## Problem\nWhat user problem are we solving?\n\n## Proposal\n\n## Acceptance criteria\n\n## Notes\n",
        "priority": "medium",
        "labels": [("Feature", "#6366f1")],
        "checklists": [("Delivery", ["Confirm scope", "Implement", "Test", "Document"])],
    },
    "code-review": {
        "name": "Code Review",
        "description": "## Change summary\n\n## Review focus\n\n## Risks\n\n## Validation\n",
        "priority": "medium",
        "labels": [("Review", "#8b5cf6")],
        "checklists": [("Review", ["Read linked context", "Check tests", "Review security/edge cases", "Approve or request changes"])],
    },
    "marketing-task": {
        "name": "Marketing Task",
        "description": "## Goal\n\n## Audience\n\n## Message\n\n## Channel\n\n## Success metric\n",
        "priority": "medium",
        "labels": [("Marketing", "#ec4899")],
        "checklists": [("Campaign", ["Draft assets", "Review copy", "Schedule/publish", "Measure results"])],
    },
}

PROJECT_TEMPLATES = {
    "software-development": {
        "name": "Software Development",
        "description": "Plan and ship a software product through discovery, implementation, review, and release.",
        "columns": ["Backlog", "Ready", "In Progress", "Review", "Done"],
        "labels": [("Bug", "#ef4444"), ("Feature", "#6366f1"), ("Tech Debt", "#f59e0b")],
        "tasks": [
            ("Define product scope", "Ready", "high", "Feature"),
            ("Set up implementation plan", "Backlog", "medium", "Feature"),
            ("Prepare release checklist", "Backlog", "medium", None),
        ],
    },
    "product-launch": {
        "name": "Product Launch",
        "description": "Coordinate positioning, readiness, launch assets, release, and post-launch follow-up.",
        "columns": ["Ideas", "Planned", "In Progress", "Approval", "Launched"],
        "labels": [("Launch", "#0ea5e9"), ("Marketing", "#ec4899"), ("Product", "#6366f1")],
        "tasks": [
            ("Finalize launch goals", "Planned", "high", "Launch"),
            ("Prepare launch messaging", "Planned", "medium", "Marketing"),
            ("Create launch readiness checklist", "Ideas", "medium", "Product"),
        ],
    },
    "marketing-campaign": {
        "name": "Marketing Campaign",
        "description": "Manage a campaign from brief and creative production through distribution and reporting.",
        "columns": ["Brief", "Planned", "Creating", "Review", "Published"],
        "labels": [("Marketing", "#ec4899"), ("Content", "#14b8a6"), ("Analytics", "#f59e0b")],
        "tasks": [
            ("Write campaign brief", "Brief", "high", "Marketing"),
            ("Produce campaign assets", "Planned", "medium", "Content"),
            ("Define reporting metrics", "Planned", "medium", "Analytics"),
        ],
    },
    "university-project": {
        "name": "University Project",
        "description": "Organize research, deliverables, reviews, and submission milestones for academic projects.",
        "columns": ["Ideas", "To Do", "Doing", "Review", "Submitted"],
        "labels": [("Research", "#0ea5e9"), ("Writing", "#8b5cf6"), ("Presentation", "#f97316")],
        "tasks": [
            ("Confirm project requirements", "To Do", "high", "Research"),
            ("Create research plan", "To Do", "medium", "Research"),
            ("Draft final presentation", "Ideas", "medium", "Presentation"),
        ],
    },
}


class TaskTemplateApply(BaseModel):
    project_id: UUID
    column_id: UUID
    template_key: str
    title: str | None = Field(default=None, max_length=240)


class ProjectTemplateApply(BaseModel):
    workspace_id: UUID
    template_key: str
    name: str = Field(min_length=1, max_length=160)
    key: str = Field(min_length=2, max_length=12, pattern=r"^[A-Za-z][A-Za-z0-9]*$")


async def _workspace_label(db: AsyncSession, workspace_id: UUID, name: str, color: str) -> Label:
    label = await db.scalar(select(Label).where(Label.workspace_id == workspace_id, func.lower(Label.name) == name.lower()))
    if label:
        return label
    label = Label(workspace_id=workspace_id, name=name, color=color)
    db.add(label)
    await db.flush()
    return label


async def _attach_template_checklists(db: AsyncSession, task: Task, template: dict) -> None:
    for checklist_index, (title, items) in enumerate(template.get("checklists", [])):
        checklist = Checklist(task_id=task.id, title=title, position=(checklist_index + 1) * 1000)
        db.add(checklist)
        await db.flush()
        db.add_all([
            ChecklistItem(checklist_id=checklist.id, title=item_title, position=(item_index + 1) * 1000)
            for item_index, item_title in enumerate(items)
        ])


@router.get("")
async def list_templates(user: User = Depends(current_user)):
    _ = user
    return {
        "task_templates": [{"key": key, "name": value["name"]} for key, value in TASK_TEMPLATES.items()],
        "project_templates": [{"key": key, "name": value["name"], "description": value["description"]} for key, value in PROJECT_TEMPLATES.items()],
    }


@router.post("/tasks/apply", status_code=201)
async def apply_task_template(data: TaskTemplateApply, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    template = TASK_TEMPLATES.get(data.template_key)
    if not template:
        raise HTTPException(status_code=404, detail="Task template not found")
    project = await db.scalar(select(Project).where(Project.id == data.project_id).with_for_update())
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    await require_project(db, project.id, user.id, write=True)
    column = await db.get(BoardColumn, data.column_id)
    if not column or column.project_id != project.id:
        raise HTTPException(status_code=400, detail="Column does not belong to project")
    project.task_counter += 1
    max_position = await db.scalar(select(func.max(Task.position)).where(Task.column_id == column.id, Task.deleted_at.is_(None)))
    task = Task(
        workspace_id=project.workspace_id,
        project_id=project.id,
        column_id=column.id,
        reporter_id=user.id,
        number=project.task_counter,
        identifier=f"{project.key}-{project.task_counter}",
        title=(data.title or template["name"]).strip(),
        description=template["description"],
        priority=template["priority"],
        position=(max_position or 0) + 1000,
    )
    db.add(task)
    await db.flush()
    for label_name, color in template["labels"]:
        label = await _workspace_label(db, project.workspace_id, label_name, color)
        db.add(TaskLabel(task_id=task.id, label_id=label.id))
    await _attach_template_checklists(db, task, template)
    await db.commit()
    await db.refresh(task)
    await publish(project.workspace_id, "task.created", {"id": str(task.id), "project_id": str(project.id), "identifier": task.identifier, "title": task.title})
    return {"id": task.id, "identifier": task.identifier, "title": task.title}


@router.post("/projects/apply", status_code=201)
async def apply_project_template(data: ProjectTemplateApply, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    template = PROJECT_TEMPLATES.get(data.template_key)
    if not template:
        raise HTTPException(status_code=404, detail="Project template not found")
    await require_workspace(db, data.workspace_id, user.id, write=True)
    key = data.key.upper()
    if await db.scalar(select(Project.id).where(Project.workspace_id == data.workspace_id, Project.key == key)):
        raise HTTPException(status_code=409, detail="Project key already exists in this workspace")
    project = Project(
        workspace_id=data.workspace_id,
        owner_id=user.id,
        name=data.name.strip(),
        key=key,
        description=template["description"],
    )
    db.add(project)
    await db.flush()
    db.add(ProjectMember(project_id=project.id, user_id=user.id, role="owner"))
    columns = {}
    for index, column_name in enumerate(template["columns"]):
        column = BoardColumn(project_id=project.id, name=column_name, position=index)
        db.add(column)
        await db.flush()
        columns[column_name] = column
    labels = {}
    for label_name, color in template["labels"]:
        labels[label_name] = await _workspace_label(db, data.workspace_id, label_name, color)
    for index, (title, column_name, priority, label_name) in enumerate(template["tasks"]):
        project.task_counter += 1
        task = Task(
            workspace_id=data.workspace_id,
            project_id=project.id,
            column_id=columns[column_name].id,
            reporter_id=user.id,
            number=project.task_counter,
            identifier=f"{key}-{project.task_counter}",
            title=title,
            description="",
            priority=priority,
            position=(index + 1) * 1000,
        )
        db.add(task)
        await db.flush()
        if label_name:
            db.add(TaskLabel(task_id=task.id, label_id=labels[label_name].id))
    await db.commit()
    await db.refresh(project)
    return {"id": project.id, "workspace_id": project.workspace_id, "name": project.name, "key": project.key, "template_key": data.template_key}
