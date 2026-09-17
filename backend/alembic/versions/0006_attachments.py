"""Add production attachment metadata.

Revision ID: 0006_attachments
Revises: 0005_task_collaboration
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_attachments"
down_revision = "0005_task_collaboration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("uploader_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("comment_id", sa.Uuid(), nullable=True),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("object_key", sa.String(length=700), nullable=False),
        sa.Column("thumbnail_key", sa.String(length=700), nullable=True),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("safe_name", sa.String(length=160), nullable=False),
        sa.Column("mime_type", sa.String(length=160), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(CASE WHEN task_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN comment_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN project_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_attachment_exactly_one_parent",
        ),
        sa.ForeignKeyConstraint(["comment_id"], ["comments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploader_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key"),
    )
    op.create_index("ix_attachments_comment_id", "attachments", ["comment_id"])
    op.create_index("ix_attachments_created_at", "attachments", ["created_at"])
    op.create_index("ix_attachments_project_id", "attachments", ["project_id"])
    op.create_index("ix_attachments_sha256", "attachments", ["sha256"])
    op.create_index("ix_attachments_task_id", "attachments", ["task_id"])
    op.create_index("ix_attachments_uploader_id", "attachments", ["uploader_id"])
    op.create_index("ix_attachments_workspace_id", "attachments", ["workspace_id"])
    op.create_index(
        "ix_attachments_workspace_created", "attachments", ["workspace_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_attachments_workspace_created", table_name="attachments")
    op.drop_index("ix_attachments_workspace_id", table_name="attachments")
    op.drop_index("ix_attachments_uploader_id", table_name="attachments")
    op.drop_index("ix_attachments_task_id", table_name="attachments")
    op.drop_index("ix_attachments_sha256", table_name="attachments")
    op.drop_index("ix_attachments_project_id", table_name="attachments")
    op.drop_index("ix_attachments_created_at", table_name="attachments")
    op.drop_index("ix_attachments_comment_id", table_name="attachments")
    op.drop_table("attachments")
