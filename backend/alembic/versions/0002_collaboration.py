"""Collaboration, project isolation, and audit schema."""

import uuid

import sqlalchemy as sa
from alembic import op

revision = "0002_collaboration"
down_revision = "0001_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_members",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_member"),
    )
    op.create_index("ix_project_members_project_id", "project_members", ["project_id"])
    op.create_index("ix_project_members_user_id", "project_members", ["user_id"])
    op.create_index("ix_project_members_role", "project_members", ["role"])

    bind = op.get_bind()
    projects = bind.execute(sa.text("SELECT id, owner_id, created_at FROM projects")).mappings().all()
    for project in projects:
        bind.execute(
            sa.text(
                "INSERT INTO project_members (id, project_id, user_id, role, created_at) "
                "VALUES (:id, :project_id, :user_id, 'owner', :created_at)"
            ),
            {
                "id": str(uuid.uuid4()),
                "project_id": str(project["id"]),
                "user_id": str(project["owner_id"]),
                "created_at": project["created_at"],
            },
        )

    op.create_table(
        "task_watchers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("task_id", sa.Uuid(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("task_id", "user_id", name="uq_task_watcher"),
    )
    op.create_index("ix_task_watchers_task_id", "task_watchers", ["task_id"])
    op.create_index("ix_task_watchers_user_id", "task_watchers", ["user_id"])

    op.create_table(
        "subtasks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("task_id", sa.Uuid(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="open"),
        sa.Column("assignee_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("position", sa.Float(), nullable=False, server_default="1000"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_subtasks_task_id", "subtasks", ["task_id"])
    op.create_index("ix_subtasks_status", "subtasks", ["status"])
    op.create_index("ix_subtasks_assignee_id", "subtasks", ["assignee_id"])
    op.create_index("ix_subtasks_due_date", "subtasks", ["due_date"])

    op.create_table(
        "checklists",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("task_id", sa.Uuid(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("position", sa.Float(), nullable=False, server_default="1000"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_checklists_task_id", "checklists", ["task_id"])

    op.create_table(
        "checklist_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("checklist_id", sa.Uuid(), sa.ForeignKey("checklists.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("assignee_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("position", sa.Float(), nullable=False, server_default="1000"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_checklist_items_checklist_id", "checklist_items", ["checklist_id"])
    op.create_index("ix_checklist_items_completed", "checklist_items", ["completed"])
    op.create_index("ix_checklist_items_assignee_id", "checklist_items", ["assignee_id"])

    op.create_table(
        "task_dependencies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("blocker_task_id", sa.Uuid(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("blocked_task_id", sa.Uuid(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("blocker_task_id <> blocked_task_id", name="ck_task_dependency_not_self"),
        sa.UniqueConstraint("blocker_task_id", "blocked_task_id", name="uq_task_dependency"),
    )
    op.create_index("ix_task_dependencies_blocker_task_id", "task_dependencies", ["blocker_task_id"])
    op.create_index("ix_task_dependencies_blocked_task_id", "task_dependencies", ["blocked_task_id"])
    op.create_index("ix_task_dependencies_created_by_id", "task_dependencies", ["created_by_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_workspace_id", "audit_logs", ["workspace_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("task_dependencies")
    op.drop_table("checklist_items")
    op.drop_table("checklists")
    op.drop_table("subtasks")
    op.drop_table("task_watchers")
    op.drop_table("project_members")
