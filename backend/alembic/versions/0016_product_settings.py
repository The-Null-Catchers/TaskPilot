"""Add persistent user, workspace, and project settings.

Revision ID: 0016_product_settings
Revises: 0015_task_planning_fields
"""

from alembic import op
import sqlalchemy as sa

revision = "0016_product_settings"
down_revision = "0015_task_planning_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_settings",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("theme", sa.String(length=16), nullable=False),
        sa.Column("density", sa.String(length=16), nullable=False),
        sa.Column("week_start", sa.Integer(), nullable=False),
        sa.Column("default_home", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "workspace_settings",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("default_project_status", sa.String(length=24), nullable=False),
        sa.Column("default_task_priority", sa.String(length=16), nullable=False),
        sa.Column("time_tracking_enabled", sa.Boolean(), nullable=False),
        sa.Column("guest_access_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("workspace_id"),
    )
    op.create_table(
        "project_settings",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("default_task_priority", sa.String(length=16), nullable=False),
        sa.Column("time_tracking_enabled", sa.Boolean(), nullable=False),
        sa.Column("auto_complete_on_done_column", sa.Boolean(), nullable=False),
        sa.Column("show_completed_tasks", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("project_id"),
    )


def downgrade() -> None:
    op.drop_table("project_settings")
    op.drop_table("workspace_settings")
    op.drop_table("user_settings")
