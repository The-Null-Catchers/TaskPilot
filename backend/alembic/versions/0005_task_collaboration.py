"""task collaboration completion

Revision ID: 0005_task_collaboration
Revises: 0004_workspace_lifecycle
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_task_collaboration"
down_revision: str | None = "0004_workspace_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "comment_reactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("comment_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("emoji", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["comment_id"], ["comments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("comment_id", "user_id", "emoji", name="uq_comment_reaction_user_emoji"),
    )
    op.create_index("ix_comment_reactions_comment_id", "comment_reactions", ["comment_id"])
    op.create_index("ix_comment_reactions_user_id", "comment_reactions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_comment_reactions_user_id", table_name="comment_reactions")
    op.drop_index("ix_comment_reactions_comment_id", table_name="comment_reactions")
    op.drop_table("comment_reactions")
