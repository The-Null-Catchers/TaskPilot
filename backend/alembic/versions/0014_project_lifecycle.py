"""Add project visual identity and archive lifecycle.

Revision ID: 0014_project_lifecycle
Revises: 0013_user_profiles
"""

from alembic import op
import sqlalchemy as sa

revision = "0014_project_lifecycle"
down_revision = "0013_user_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("icon", sa.String(length=32), nullable=True))
    op.add_column(
        "projects",
        sa.Column("color", sa.String(length=16), nullable=False, server_default="#6366f1"),
    )
    op.add_column("projects", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_projects_archived_at", "projects", ["archived_at"], unique=False)
    op.alter_column("projects", "color", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_projects_archived_at", table_name="projects")
    op.drop_column("projects", "archived_at")
    op.drop_column("projects", "color")
    op.drop_column("projects", "icon")
