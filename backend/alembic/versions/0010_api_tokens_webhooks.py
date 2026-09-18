"""Add personal API tokens and workspace webhooks.

Revision ID: 0010_api_tokens_webhooks
Revises: 0009_notification_delivery
"""

import sqlalchemy as sa
from alembic import op

revision = "0010_api_tokens_webhooks"
down_revision = "0009_notification_delivery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "personal_api_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("token_prefix", sa.String(length=24), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("scopes", sa.String(length=200), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    for name in ("user_id", "token_prefix", "token_hash", "expires_at", "last_used_at", "revoked_at", "created_at"):
        op.create_index(f"ix_personal_api_tokens_{name}", "personal_api_tokens", [name])

    op.create_table(
        "workspace_webhooks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("secret_hash", sa.String(length=64), nullable=False),
        sa.Column("secret_ciphertext", sa.Text(), nullable=False),
        sa.Column("events", sa.String(length=1000), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for name in ("workspace_id", "created_by", "active", "created_at"):
        op.create_index(f"ix_workspace_webhooks_{name}", "workspace_webhooks", [name])

    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("webhook_id", sa.Uuid(), nullable=False),
        sa.Column("activity_id", sa.Uuid(), nullable=False),
        sa.Column("event", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["webhook_id"], ["workspace_webhooks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["activity_id"], ["activity_logs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("webhook_id", "activity_id", name="uq_webhook_delivery_activity"),
    )
    for name in ("webhook_id", "activity_id", "event", "status", "next_attempt_at", "delivered_at", "created_at"):
        op.create_index(f"ix_webhook_deliveries_{name}", "webhook_deliveries", [name])


def downgrade() -> None:
    for name in ("created_at", "delivered_at", "next_attempt_at", "status", "event", "activity_id", "webhook_id"):
        op.drop_index(f"ix_webhook_deliveries_{name}", table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")
    for name in ("created_at", "active", "created_by", "workspace_id"):
        op.drop_index(f"ix_workspace_webhooks_{name}", table_name="workspace_webhooks")
    op.drop_table("workspace_webhooks")
    for name in ("created_at", "revoked_at", "last_used_at", "expires_at", "token_hash", "token_prefix", "user_id"):
        op.drop_index(f"ix_personal_api_tokens_{name}", table_name="personal_api_tokens")
    op.drop_table("personal_api_tokens")
