"""Add task planning estimate field.

Revision ID: 0015_task_planning_fields
Revises: 0014_project_lifecycle
"""

from alembic import op
import sqlalchemy as sa

revision = "0015_task_planning_fields"
down_revision = "0014_project_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("estimate_minutes", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "estimate_minutes")
