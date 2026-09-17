from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, require_project
from app.collaboration_models import ProjectMember
from app.db import get_db
from app.models import ActivityLog, Task, TaskAssignee, User
from app.planning_models import Milestone
from app.productivity_models import TimeEntry

router = APIRouter(tags=["project-insights"])


class MilestoneCreate(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    description: str = Field(default="", max_length=10000)
    due_date: datetime


class MilestonePatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=10000)
    due_date: datetime | None = None
    status: str | None = Field(default=None, pattern="^(open|completed)$")


def milestone_out(item: Milestone) -> dict:
    return {
        "id": item.id, "workspace_id": item.workspace_id, "project_id": item.project_id,
        "title": item.title, "description": item.description, "due_date": item.due_date,
        "status": item.status, "created_by": item.created_by,
        "created_at": item.created_at, "updated_at": item.updated_at,
    }


@router.get("/projects/{project_id}/milestones")
async def list_milestones(project_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await require_project(db, project_id, user.id)
    items = list((await db.scalars(select(Milestone).where(Milestone.project_id == project_id).order_by(Milestone.due_date))).all())
    return [milestone_out(item) for item in items]


@router.post("/projects/{project_id}/milestones", status_code=201)
async def create_milestone(project_id: UUID, data: MilestoneCreate, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    project, _ = await require_project(db, project_id, user.id, write=True)
    item = Milestone(workspace_id=project.workspace_id, project_id=project.id, title=data.title.strip(), description=data.description, due_date=data.due_date, created_by=user.id)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return milestone_out(item)


@router.patch("/projects/{project_id}/milestones/{milestone_id}")
async def patch_milestone(project_id: UUID, milestone_id: UUID, data: MilestonePatch, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await require_project(db, project_id, user.id, write=True)
    item = await db.get(Milestone, milestone_id)
    if not item or item.project_id != project_id:
        raise HTTPException(status_code=404, detail="Milestone not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        if key in {"title", "description"} and isinstance(value, str):
            value = value.strip()
        setattr(item, key, value)
    await db.commit()
    await db.refresh(item)
    return milestone_out(item)


@router.delete("/projects/{project_id}/milestones/{milestone_id}", status_code=204)
async def delete_milestone(project_id: UUID, milestone_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await require_project(db, project_id, user.id, write=True)
    item = await db.get(Milestone, milestone_id)
    if not item or item.project_id != project_id:
        raise HTTPException(status_code=404, detail="Milestone not found")
    await db.delete(item)
    await db.commit()


@router.get("/projects/{project_id}/overview")
async def project_overview(project_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    project, _ = await require_project(db, project_id, user.id)
    tasks = list((await db.scalars(select(Task).where(Task.project_id == project_id, Task.deleted_at.is_(None)))).all())
    now = datetime.now(UTC)
    completed = [task for task in tasks if task.status == "done"]
    open_tasks = [task for task in tasks if task.status != "done"]
    overdue = [task for task in open_tasks if task.due_date and task.due_date < now]
    upcoming = sorted([task for task in open_tasks if task.due_date and task.due_date >= now], key=lambda task: task.due_date)[:8]
    recent_completed = sorted(completed, key=lambda task: task.completed_at or task.updated_at, reverse=True)[:8]
    members = (await db.execute(select(ProjectMember, User).join(User, User.id == ProjectMember.user_id).where(ProjectMember.project_id == project_id))).all()
    milestones = list((await db.scalars(select(Milestone).where(Milestone.project_id == project_id).order_by(Milestone.due_date))).all())
    activity = list((await db.scalars(select(ActivityLog).where(ActivityLog.project_id == project_id).order_by(ActivityLog.created_at.desc()).limit(20))).all())
    return {
        "project": {"id": project.id, "name": project.name, "key": project.key, "status": project.status, "start_date": project.start_date, "due_date": project.due_date},
        "progress": round((len(completed) / len(tasks) * 100) if tasks else 0, 1),
        "counts": {"total": len(tasks), "completed": len(completed), "open": len(open_tasks), "overdue": len(overdue)},
        "members": [{"id": member_user.id, "name": member_user.name, "email": member_user.email, "role": membership.role} for membership, member_user in members],
        "upcoming_tasks": [{"id": task.id, "identifier": task.identifier, "title": task.title, "due_date": task.due_date, "priority": task.priority} for task in upcoming],
        "overdue_tasks": [{"id": task.id, "identifier": task.identifier, "title": task.title, "due_date": task.due_date, "priority": task.priority} for task in sorted(overdue, key=lambda task: task.due_date)[:8]],
        "recently_completed": [{"id": task.id, "identifier": task.identifier, "title": task.title, "completed_at": task.completed_at or task.updated_at} for task in recent_completed],
        "milestones": [milestone_out(item) for item in milestones],
        "activity": [{"id": item.id, "action": item.action, "summary": item.summary, "actor_id": item.actor_id, "created_at": item.created_at} for item in activity],
    }


@router.get("/analytics/projects/{project_id}/expanded")
async def expanded_project_analytics(project_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await require_project(db, project_id, user.id)
    tasks = list((await db.scalars(select(Task).where(Task.project_id == project_id, Task.deleted_at.is_(None)))).all())
    now = datetime.now(UTC)
    completed = [task for task in tasks if task.status == "done"]
    overdue = [task for task in tasks if task.status != "done" and task.due_date and task.due_date < now]
    task_ids = [task.id for task in tasks]
    assignee_rows = []
    time_rows = []
    if task_ids:
        assignee_rows = (await db.execute(select(TaskAssignee, User).join(User, User.id == TaskAssignee.user_id).where(TaskAssignee.task_id.in_(task_ids)))).all()
        time_rows = list((await db.scalars(select(TimeEntry).where(TimeEntry.task_id.in_(task_ids)))).all())
    per_user = Counter(member.name for _, member in assignee_rows)
    workload = Counter()
    task_by_id = {task.id: task for task in tasks}
    user_names = {member.id: member.name for _, member in assignee_rows}
    for assignment, member in assignee_rows:
        task = task_by_id.get(assignment.task_id)
        if task and task.status != "done":
            workload[member.name] += 1
    time_by_member: Counter[str] = Counter()
    for entry in time_rows:
        duration = entry.duration_seconds or 0
        if duration <= 0 and entry.ended_at:
            duration = max(0, int((entry.ended_at - entry.started_at).total_seconds()))
        time_by_member[user_names.get(entry.user_id, str(entry.user_id))] += duration
    completed_seconds = [max(0, ((task.completed_at or task.updated_at) - task.created_at).total_seconds()) for task in completed]
    days: dict[str, dict[str, int]] = defaultdict(lambda: {"created": 0, "completed": 0})
    for offset in range(29, -1, -1):
        days[(now - timedelta(days=offset)).date().isoformat()]
    for task in tasks:
        created_key = task.created_at.date().isoformat()
        if created_key in days:
            days[created_key]["created"] += 1
        if task.status == "done":
            completed_key = (task.completed_at or task.updated_at).date().isoformat()
            if completed_key in days:
                days[completed_key]["completed"] += 1
    return {
        "total_tasks": len(tasks), "completed_tasks": len(completed), "open_tasks": len(tasks) - len(completed),
        "overdue_tasks": len(overdue), "completion_percentage": round((len(completed) / len(tasks) * 100) if tasks else 0, 1),
        "by_status": dict(Counter(task.status for task in tasks)), "by_priority": dict(Counter(task.priority for task in tasks)),
        "tasks_per_user": dict(per_user), "workload_by_member": dict(workload),
        "created_vs_completed": [{"date": date, **counts} for date, counts in days.items()],
        "average_completion_hours": round(sum(completed_seconds) / len(completed_seconds) / 3600, 1) if completed_seconds else 0,
        "time_tracked_seconds": sum(time_by_member.values()), "time_tracked_by_member": dict(time_by_member),
    }
