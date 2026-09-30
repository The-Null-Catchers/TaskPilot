"""Add first-class user profiles.

Revision ID: 0013_user_profiles
Revises: 0012_task_identifier_scope
"""

from alembic import op
import sqlalchemy as sa

revision = "0013_user_profiles"
down_revision = "0012_task_identifier_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(length=40), nullable=True),
        sa.Column("avatar_url", sa.String(length=500), nullable=True),
        sa.Column("job_title", sa.String(length=120), nullable=True),
        sa.Column("bio", sa.Text(), nullable=False, server_default=""),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"),
        sa.Column("language", sa.String(length=16), nullable=False, server_default="en"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("username", name="uq_user_profiles_username"),
    )
    op.create_index("ix_user_profiles_username", "user_profiles", ["username"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_profiles_username", table_name="user_profiles")
    op.drop_table("user_profiles")
