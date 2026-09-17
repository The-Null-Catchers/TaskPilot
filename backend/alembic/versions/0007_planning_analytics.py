"""Add milestones and task planning timestamps.

Revision ID: 0007_planning_analytics
Revises: 0006_attachments
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_planning_analytics"
down_revision = "0006_attachments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("start_date", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tasks", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_tasks_start_date", "tasks", ["start_date"])
    op.create_index("ix_tasks_completed_at", "tasks", ["completed_at"])
    op.execute("UPDATE tasks SET completed_at = updated_at WHERE status = 'done' AND completed_at IS NULL")

    op.create_table(
        "milestones",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_milestones_created_by", "milestones", ["created_by"])
    op.create_index("ix_milestones_due_date", "milestones", ["due_date"])
    op.create_index("ix_milestones_project_id", "milestones", ["project_id"])
    op.create_index("ix_milestones_status", "milestones", ["status"])
    op.create_index("ix_milestones_workspace_id", "milestones", ["workspace_id"])
    op.create_index("ix_milestones_project_due", "milestones", ["project_id", "due_date"])


def downgrade() -> None:
    op.drop_index("ix_milestones_project_due", table_name="milestones")
    op.drop_index("ix_milestones_workspace_id", table_name="milestones")
    op.drop_index("ix_milestones_status", table_name="milestones")
    op.drop_index("ix_milestones_project_id", table_name="milestones")
    op.drop_index("ix_milestones_due_date", table_name="milestones")
    op.drop_index("ix_milestones_created_by", table_name="milestones")
    op.drop_table("milestones")
    op.drop_index("ix_tasks_completed_at", table_name="tasks")
    op.drop_index("ix_tasks_start_date", table_name="tasks")
    op.drop_column("tasks", "completed_at")
    op.drop_column("tasks", "start_date")
