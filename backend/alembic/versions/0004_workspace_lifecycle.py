"""Add workspace archive lifecycle state."""

import sqlalchemy as sa
from alembic import op

revision = "0004_workspace_lifecycle"
down_revision = "0003_productivity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace_archives",
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "archived_by_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "archived_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_workspace_archives_archived_by_id",
        "workspace_archives",
        ["archived_by_id"],
    )
    op.create_index(
        "ix_workspace_archives_archived_at",
        "workspace_archives",
        ["archived_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_workspace_archives_archived_at", table_name="workspace_archives")
    op.drop_index("ix_workspace_archives_archived_by_id", table_name="workspace_archives")
    op.drop_table("workspace_archives")
