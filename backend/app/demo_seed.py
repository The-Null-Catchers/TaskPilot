import argparse
import asyncio
import os
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.account_models import AccountSecurity
from app.collaboration_models import (
    Checklist,
    ChecklistItem,
    ProjectMember,
    Subtask,
    TaskDependency,
    TaskWatcher,
)
from app.core.config import settings
from app.core.security import hash_password
from app.db import SessionLocal
from app.models import (
    ActivityLog,
    BoardColumn,
    Comment,
    Label,
    Project,
    Task,
    TaskAssignee,
    TaskLabel,
    User,
    Workspace,
    WorkspaceMember,
)
from app.planning_models import Milestone

DEMO_SLUG = "taskpilot-demo"
DEMO_EMAILS = (
    "alex.demo@taskpilot.local",
    "maya.demo@taskpilot.local",
    "sam.demo@taskpilot.local",
)
DEFAULT_PASSWORD = "TaskPilot-Demo-2026!"


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a realistic local TaskPilot demo dataset.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete the previous TaskPilot demo workspace/users and recreate them.",
    )
    return parser.parse_args()


async def _reset_demo(db) -> None:
    workspace = await db.scalar(select(Workspace).where(Workspace.slug == DEMO_SLUG))
    if workspace is not None:
        await db.delete(workspace)
        await db.flush()

    users = list((await db.scalars(select(User).where(User.email.in_(DEMO_EMAILS)))).all())
    for user in users:
        await db.delete(user)
    await db.flush()


def _activity(
    *,
    workspace_id,
    project_id,
    task_id,
    actor_id,
    action: str,
    summary: str,
    created_at: datetime,
) -> ActivityLog:
    return ActivityLog(
        workspace_id=workspace_id,
        project_id=project_id,
        task_id=task_id,
        actor_id=actor_id,
        action=action,
        summary=summary,
        created_at=created_at,
    )


async def seed(reset: bool) -> None:
    if settings.app_env == "production":
        raise SystemExit("Refusing to seed demo data while APP_ENV=production.")

    password = os.getenv("TASKPILOT_DEMO_PASSWORD", DEFAULT_PASSWORD)
    if len(password) < 10:
        raise SystemExit("TASKPILOT_DEMO_PASSWORD must be at least 10 characters.")

    now = datetime.now(UTC).replace(microsecond=0)

    async with SessionLocal() as db:
        existing = await db.scalar(select(Workspace).where(Workspace.slug == DEMO_SLUG))
        if existing is not None and not reset:
            print("TaskPilot demo data already exists.")
            print("Run with --reset to recreate it.")
            print(f"Demo workspace: {DEMO_SLUG}")
            print(f"Login: {DEMO_EMAILS[0]}")
            return

        if reset:
            await _reset_demo(db)

        alex = User(
            email=DEMO_EMAILS[0],
            name="Alex Morgan",
            password_hash=hash_password(password),
        )
        maya = User(
            email=DEMO_EMAILS[1],
            name="Maya Chen",
            password_hash=hash_password(password),
        )
        sam = User(
            email=DEMO_EMAILS[2],
            name="Sam Rivera",
            password_hash=hash_password(password),
        )
        db.add_all([alex, maya, sam])
        await db.flush()

        db.add_all(
            [
                AccountSecurity(user_id=alex.id, email_verified_at=now - timedelta(days=90)),
                AccountSecurity(user_id=maya.id, email_verified_at=now - timedelta(days=60)),
                AccountSecurity(user_id=sam.id, email_verified_at=now - timedelta(days=30)),
            ]
        )

        workspace = Workspace(
            name="Northstar Product Team",
            slug=DEMO_SLUG,
            owner_id=alex.id,
        )
        db.add(workspace)
        await db.flush()
        db.add_all(
            [
                WorkspaceMember(workspace_id=workspace.id, user_id=alex.id, role="owner"),
                WorkspaceMember(workspace_id=workspace.id, user_id=maya.id, role="admin"),
                WorkspaceMember(workspace_id=workspace.id, user_id=sam.id, role="member"),
            ]
        )

        product = Project(
            workspace_id=workspace.id,
            owner_id=alex.id,
            name="Mobile App 2.0",
            key="NSTAR",
            description="Launch the next version of the customer mobile experience.",
            status="active",
            task_counter=8,
            start_date=(now - timedelta(days=35)).date(),
            due_date=(now + timedelta(days=28)).date(),
        )
        growth = Project(
            workspace_id=workspace.id,
            owner_id=maya.id,
            name="Growth Experiments",
            key="GROW",
            description="Activation, referral, and onboarding experiments for Q4.",
            status="active",
            task_counter=5,
            start_date=(now - timedelta(days=14)).date(),
            due_date=(now + timedelta(days=42)).date(),
        )
        db.add_all([product, growth])
        await db.flush()

        db.add_all(
            [
                ProjectMember(project_id=product.id, user_id=alex.id, role="owner"),
                ProjectMember(project_id=product.id, user_id=maya.id, role="member"),
                ProjectMember(project_id=product.id, user_id=sam.id, role="member"),
                ProjectMember(project_id=growth.id, user_id=maya.id, role="owner"),
                ProjectMember(project_id=growth.id, user_id=alex.id, role="member"),
                ProjectMember(project_id=growth.id, user_id=sam.id, role="member"),
            ]
        )

        column_names = ["Backlog", "To Do", "In Progress", "Review", "Done"]
        product_columns = [
            BoardColumn(project_id=product.id, name=name, position=index)
            for index, name in enumerate(column_names)
        ]
        growth_columns = [
            BoardColumn(project_id=growth.id, name=name, position=index)
            for index, name in enumerate(column_names)
        ]
        db.add_all(product_columns + growth_columns)
        await db.flush()

        p = {column.name: column for column in product_columns}
        g = {column.name: column for column in growth_columns}

        product_tasks = [
            Task(
                workspace_id=workspace.id,
                project_id=product.id,
                column_id=p["Done"].id,
                reporter_id=alex.id,
                number=1,
                identifier="NSTAR-1",
                title="Define mobile launch success metrics",
                description="Agree on activation, retention, crash-free sessions, and adoption targets.",
                priority="high",
                status="done",
                position=1000,
                start_date=now - timedelta(days=30),
                due_date=now - timedelta(days=22),
                completed_at=now - timedelta(days=23),
                created_at=now - timedelta(days=34),
                updated_at=now - timedelta(days=23),
            ),
            Task(
                workspace_id=workspace.id,
                project_id=product.id,
                column_id=p["Done"].id,
                reporter_id=maya.id,
                number=2,
                identifier="NSTAR-2",
                title="Finalize navigation information architecture",
                description="Validate the new tab structure against top customer journeys.",
                priority="medium",
                status="done",
                position=2000,
                due_date=now - timedelta(days=14),
                completed_at=now - timedelta(days=15),
                created_at=now - timedelta(days=29),
                updated_at=now - timedelta(days=15),
            ),
            Task(
                workspace_id=workspace.id,
                project_id=product.id,
                column_id=p["In Progress"].id,
                reporter_id=alex.id,
                number=3,
                identifier="NSTAR-3",
                title="Implement offline-first task detail",
                description="Cache reads, queue edits, and surface sync conflicts without data loss.",
                priority="urgent",
                status="in_progress",
                position=1000,
                start_date=now - timedelta(days=6),
                due_date=now + timedelta(days=3),
                created_at=now - timedelta(days=12),
                updated_at=now - timedelta(hours=4),
            ),
            Task(
                workspace_id=workspace.id,
                project_id=product.id,
                column_id=p["Review"].id,
                reporter_id=sam.id,
                number=4,
                identifier="NSTAR-4",
                title="Accessibility pass for task detail",
                description="Verify keyboard order, semantics, text scaling, and contrast.",
                priority="high",
                status="review",
                position=1000,
                start_date=now - timedelta(days=5),
                due_date=now + timedelta(days=2),
                created_at=now - timedelta(days=9),
                updated_at=now - timedelta(hours=9),
            ),
            Task(
                workspace_id=workspace.id,
                project_id=product.id,
                column_id=p["To Do"].id,
                reporter_id=maya.id,
                number=5,
                identifier="NSTAR-5",
                title="Run TestFlight release checklist",
                description="Validate auth, push, attachments, offline replay, and deep links on device.",
                priority="high",
                status="open",
                position=1000,
                due_date=now + timedelta(days=8),
                created_at=now - timedelta(days=5),
                updated_at=now - timedelta(days=1),
            ),
            Task(
                workspace_id=workspace.id,
                project_id=product.id,
                column_id=p["Backlog"].id,
                reporter_id=alex.id,
                number=6,
                identifier="NSTAR-6",
                title="Add performance budget dashboard",
                description="Track API p95, board load time, app startup, and cache size.",
                priority="medium",
                status="open",
                position=1000,
                due_date=now + timedelta(days=18),
                created_at=now - timedelta(days=4),
                updated_at=now - timedelta(days=2),
            ),
            Task(
                workspace_id=workspace.id,
                project_id=product.id,
                column_id=p["To Do"].id,
                reporter_id=sam.id,
                number=7,
                identifier="NSTAR-7",
                title="Polish empty and error states",
                description="Make offline, empty, permission, and provider failure states actionable.",
                priority="medium",
                status="open",
                position=2000,
                due_date=now + timedelta(days=11),
                created_at=now - timedelta(days=3),
                updated_at=now - timedelta(hours=18),
            ),
            Task(
                workspace_id=workspace.id,
                project_id=product.id,
                column_id=p["Backlog"].id,
                reporter_id=maya.id,
                number=8,
                identifier="NSTAR-8",
                title="Prepare launch retrospective template",
                description="Capture launch outcomes, incidents, learnings, and follow-up actions.",
                priority="low",
                status="open",
                position=2000,
                due_date=now + timedelta(days=31),
                created_at=now - timedelta(days=2),
                updated_at=now - timedelta(days=2),
            ),
        ]

        growth_tasks = [
            Task(
                workspace_id=workspace.id,
                project_id=growth.id,
                column_id=g["Done"].id,
                reporter_id=maya.id,
                number=1,
                identifier="GROW-1",
                title="Baseline onboarding funnel",
                description="Establish current conversion from signup through first completed task.",
                priority="high",
                status="done",
                position=1000,
                due_date=now - timedelta(days=7),
                completed_at=now - timedelta(days=8),
                created_at=now - timedelta(days=14),
                updated_at=now - timedelta(days=8),
            ),
            Task(
                workspace_id=workspace.id,
                project_id=growth.id,
                column_id=g["In Progress"].id,
                reporter_id=maya.id,
                number=2,
                identifier="GROW-2",
                title="Experiment with guided project templates",
                description="Compare blank-workspace onboarding against role-based project templates.",
                priority="high",
                status="in_progress",
                position=1000,
                due_date=now + timedelta(days=5),
                created_at=now - timedelta(days=10),
                updated_at=now - timedelta(hours=3),
            ),
            Task(
                workspace_id=workspace.id,
                project_id=growth.id,
                column_id=g["Review"].id,
                reporter_id=sam.id,
                number=3,
                identifier="GROW-3",
                title="Review referral landing page copy",
                description="Tighten value proposition and proof points before the next traffic cohort.",
                priority="medium",
                status="review",
                position=1000,
                due_date=now + timedelta(days=2),
                created_at=now - timedelta(days=8),
                updated_at=now - timedelta(hours=12),
            ),
            Task(
                workspace_id=workspace.id,
                project_id=growth.id,
                column_id=g["To Do"].id,
                reporter_id=alex.id,
                number=4,
                identifier="GROW-4",
                title="Add experiment guardrail metrics",
                description="Track support contacts, unsubscribe rate, and failed onboarding attempts.",
                priority="medium",
                status="open",
                position=1000,
                due_date=now + timedelta(days=9),
                created_at=now - timedelta(days=6),
                updated_at=now - timedelta(days=1),
            ),
            Task(
                workspace_id=workspace.id,
                project_id=growth.id,
                column_id=g["Backlog"].id,
                reporter_id=maya.id,
                number=5,
                identifier="GROW-5",
                title="Plan reactivation email experiment",
                description="Draft audience, success metric, holdout group, and message variants.",
                priority="low",
                status="open",
                position=1000,
                due_date=now + timedelta(days=21),
                created_at=now - timedelta(days=3),
                updated_at=now - timedelta(days=2),
            ),
        ]
        db.add_all(product_tasks + growth_tasks)
        await db.flush()

        by_identifier = {task.identifier: task for task in product_tasks + growth_tasks}

        db.add_all(
            [
                TaskAssignee(task_id=by_identifier["NSTAR-3"].id, user_id=alex.id),
                TaskAssignee(task_id=by_identifier["NSTAR-3"].id, user_id=sam.id),
                TaskAssignee(task_id=by_identifier["NSTAR-4"].id, user_id=sam.id),
                TaskAssignee(task_id=by_identifier["NSTAR-5"].id, user_id=maya.id),
                TaskAssignee(task_id=by_identifier["NSTAR-7"].id, user_id=sam.id),
                TaskAssignee(task_id=by_identifier["GROW-2"].id, user_id=maya.id),
                TaskAssignee(task_id=by_identifier["GROW-3"].id, user_id=sam.id),
                TaskAssignee(task_id=by_identifier["GROW-4"].id, user_id=alex.id),
                TaskWatcher(task_id=by_identifier["NSTAR-3"].id, user_id=maya.id),
                TaskWatcher(task_id=by_identifier["GROW-2"].id, user_id=alex.id),
            ]
        )

        bug = Label(workspace_id=workspace.id, name="bug", color="#DC2626")
        mobile = Label(workspace_id=workspace.id, name="mobile", color="#4F46E5")
        launch = Label(workspace_id=workspace.id, name="launch", color="#059669")
        experiment = Label(workspace_id=workspace.id, name="experiment", color="#D97706")
        db.add_all([bug, mobile, launch, experiment])
        await db.flush()
        db.add_all(
            [
                TaskLabel(task_id=by_identifier["NSTAR-3"].id, label_id=mobile.id),
                TaskLabel(task_id=by_identifier["NSTAR-4"].id, label_id=mobile.id),
                TaskLabel(task_id=by_identifier["NSTAR-5"].id, label_id=launch.id),
                TaskLabel(task_id=by_identifier["NSTAR-7"].id, label_id=bug.id),
                TaskLabel(task_id=by_identifier["GROW-2"].id, label_id=experiment.id),
                TaskLabel(task_id=by_identifier["GROW-3"].id, label_id=experiment.id),
            ]
        )

        checklist = Checklist(
            task_id=by_identifier["NSTAR-5"].id,
            title="Release validation",
            position=1000,
        )
        db.add(checklist)
        await db.flush()
        db.add_all(
            [
                ChecklistItem(
                    checklist_id=checklist.id,
                    title="Validate login and refresh rotation",
                    completed=True,
                    assignee_id=maya.id,
                    position=1000,
                ),
                ChecklistItem(
                    checklist_id=checklist.id,
                    title="Verify push deep links on a real device",
                    completed=False,
                    assignee_id=sam.id,
                    position=2000,
                ),
                ChecklistItem(
                    checklist_id=checklist.id,
                    title="Test offline replay after reconnect",
                    completed=False,
                    assignee_id=alex.id,
                    position=3000,
                ),
            ]
        )

        db.add_all(
            [
                Subtask(
                    task_id=by_identifier["NSTAR-3"].id,
                    title="Cache task detail payload",
                    status="done",
                    assignee_id=alex.id,
                    position=1000,
                ),
                Subtask(
                    task_id=by_identifier["NSTAR-3"].id,
                    title="Surface 409 conflicts in Sync Center",
                    status="done",
                    assignee_id=sam.id,
                    position=2000,
                ),
                Subtask(
                    task_id=by_identifier["NSTAR-3"].id,
                    title="Preserve queued edits on auth expiry",
                    status="open",
                    assignee_id=alex.id,
                    due_date=now + timedelta(days=2),
                    position=3000,
                ),
            ]
        )

        db.add(
            TaskDependency(
                blocker_task_id=by_identifier["NSTAR-3"].id,
                blocked_task_id=by_identifier["NSTAR-5"].id,
                created_by_id=alex.id,
            )
        )

        db.add_all(
            [
                Comment(
                    task_id=by_identifier["NSTAR-3"].id,
                    author_id=maya.id,
                    body="The reconnect flow looks solid. Please keep the conflict copy visible until the user resolves it.",
                    created_at=now - timedelta(days=2, hours=3),
                ),
                Comment(
                    task_id=by_identifier["NSTAR-3"].id,
                    author_id=sam.id,
                    body="I’ll cover large text and offline banners in the accessibility pass.",
                    created_at=now - timedelta(days=1, hours=6),
                ),
                Comment(
                    task_id=by_identifier["GROW-2"].id,
                    author_id=alex.id,
                    body="Let’s keep the experiment instrumentation in the same release so we can trust the funnel.",
                    created_at=now - timedelta(hours=20),
                ),
            ]
        )

        db.add_all(
            [
                Milestone(
                    workspace_id=workspace.id,
                    project_id=product.id,
                    title="Release candidate",
                    description="Signed builds ready for stakeholder validation.",
                    due_date=now + timedelta(days=12),
                    status="open",
                    created_by=alex.id,
                ),
                Milestone(
                    workspace_id=workspace.id,
                    project_id=product.id,
                    title="Mobile 2.0 launch",
                    description="Production rollout with monitoring and rollback plan ready.",
                    due_date=now + timedelta(days=28),
                    status="open",
                    created_by=alex.id,
                ),
                Milestone(
                    workspace_id=workspace.id,
                    project_id=growth.id,
                    title="Experiment readout",
                    description="Publish onboarding-template experiment results and decision.",
                    due_date=now + timedelta(days=16),
                    status="open",
                    created_by=maya.id,
                ),
            ]
        )

        activity_specs = [
            ("NSTAR-1", alex, "task.created", "Created NSTAR-1", 34),
            ("NSTAR-1", alex, "task.completed", "Completed success metrics definition", 23),
            ("NSTAR-2", maya, "task.completed", "Finalized navigation information architecture", 15),
            ("NSTAR-3", alex, "task.created", "Created offline-first task detail work", 12),
            ("NSTAR-3", sam, "comment.created", "Added implementation feedback to NSTAR-3", 2),
            ("NSTAR-4", sam, "task.moved", "Moved NSTAR-4 to Review", 1),
            ("NSTAR-5", maya, "checklist.created", "Added release validation checklist", 1),
            ("GROW-1", maya, "task.completed", "Completed onboarding funnel baseline", 8),
            ("GROW-2", maya, "task.moved", "Started guided template experiment", 5),
            ("GROW-3", sam, "task.moved", "Moved referral copy to Review", 1),
        ]
        for identifier, actor, action, summary, days_ago in activity_specs:
            task = by_identifier[identifier]
            db.add(
                _activity(
                    workspace_id=workspace.id,
                    project_id=task.project_id,
                    task_id=task.id,
                    actor_id=actor.id,
                    action=action,
                    summary=summary,
                    created_at=now - timedelta(days=days_ago),
                )
            )

        await db.commit()

    print("TaskPilot demo dataset is ready.")
    print(f"Workspace: Northstar Product Team ({DEMO_SLUG})")
    print("Demo users:")
    for email in DEMO_EMAILS:
        print(f"  - {email}")
    print(
        "Password: "
        + ("value from TASKPILOT_DEMO_PASSWORD" if "TASKPILOT_DEMO_PASSWORD" in os.environ else DEFAULT_PASSWORD)
    )
    print("For local/demo use only. The seeder refuses APP_ENV=production.")


if __name__ == "__main__":
    asyncio.run(seed(_args().reset))
