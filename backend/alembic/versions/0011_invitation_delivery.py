"""Add secure workspace invitation email delivery state.

Revision ID: 0011_invitation_delivery
Revises: 0010_api_tokens_webhooks
"""

import sqlalchemy as sa
from alembic import op

revision = "0011_invitation_delivery"
down_revision = "0010_api_tokens_webhooks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workspace_invitations", sa.Column("delivery_token_ciphertext", sa.Text(), nullable=True))
    op.add_column(
        "workspace_invitations",
        sa.Column("delivery_status", sa.String(length=20), nullable=False, server_default="pending"),
    )
    op.add_column(
        "workspace_invitations",
        sa.Column("delivery_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("workspace_invitations", sa.Column("delivery_last_error", sa.String(length=200), nullable=True))
    op.add_column("workspace_invitations", sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_workspace_invitations_delivery_status",
        "workspace_invitations",
        ["delivery_status"],
    )
    op.alter_column("workspace_invitations", "delivery_status", server_default=None)
    op.alter_column("workspace_invitations", "delivery_attempts", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_workspace_invitations_delivery_status", table_name="workspace_invitations")
    op.drop_column("workspace_invitations", "delivered_at")
    op.drop_column("workspace_invitations", "delivery_last_error")
    op.drop_column("workspace_invitations", "delivery_attempts")
    op.drop_column("workspace_invitations", "delivery_status")
    op.drop_column("workspace_invitations", "delivery_token_ciphertext")
