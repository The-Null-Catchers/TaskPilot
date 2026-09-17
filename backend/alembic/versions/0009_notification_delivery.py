"""Add notification preferences, subscriptions, and delivery tracking.

Revision ID: 0009_notification_delivery
Revises: 0008_account_lifecycle
"""

import sqlalchemy as sa
from alembic import op

revision = "0009_notification_delivery"
down_revision = "0008_account_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_preferences",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("in_app_enabled", sa.Boolean(), nullable=False),
        sa.Column("email_enabled", sa.Boolean(), nullable=False),
        sa.Column("browser_enabled", sa.Boolean(), nullable=False),
        sa.Column("mobile_enabled", sa.Boolean(), nullable=False),
        sa.Column("digest_frequency", sa.String(length=16), nullable=False),
        sa.Column("assignments_enabled", sa.Boolean(), nullable=False),
        sa.Column("mentions_enabled", sa.Boolean(), nullable=False),
        sa.Column("comments_enabled", sa.Boolean(), nullable=False),
        sa.Column("deadlines_enabled", sa.Boolean(), nullable=False),
        sa.Column("dependencies_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("target_hash", sa.String(length=64), nullable=False),
        sa.Column("target_ciphertext", sa.Text(), nullable=False),
        sa.Column("config_ciphertext", sa.Text(), nullable=False),
        sa.Column("device_name", sa.String(length=160), nullable=True),
        sa.Column("platform", sa.String(length=40), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "channel", "target_hash", name="uq_push_subscription_target"),
    )
    op.create_index("ix_push_subscriptions_user_id", "push_subscriptions", ["user_id"])
    op.create_index("ix_push_subscriptions_channel", "push_subscriptions", ["channel"])
    op.create_index("ix_push_subscriptions_target_hash", "push_subscriptions", ["target_hash"])
    op.create_index("ix_push_subscriptions_last_used_at", "push_subscriptions", ["last_used_at"])
    op.create_index("ix_push_subscriptions_revoked_at", "push_subscriptions", ["revoked_at"])

    op.create_table(
        "notification_dispatches",
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["notification_id"], ["notifications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("notification_id"),
    )
    op.create_index("ix_notification_dispatches_processed_at", "notification_dispatches", ["processed_at"])

    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=True),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("target_key", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["notification_id"], ["notifications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subscription_id"], ["push_subscriptions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "notification_id",
            "channel",
            "target_key",
            name="uq_notification_delivery_target",
        ),
    )
    op.create_index("ix_notification_deliveries_notification_id", "notification_deliveries", ["notification_id"])
    op.create_index("ix_notification_deliveries_subscription_id", "notification_deliveries", ["subscription_id"])
    op.create_index("ix_notification_deliveries_channel", "notification_deliveries", ["channel"])
    op.create_index("ix_notification_deliveries_status", "notification_deliveries", ["status"])
    op.create_index("ix_notification_deliveries_next_attempt_at", "notification_deliveries", ["next_attempt_at"])
    op.create_index("ix_notification_deliveries_sent_at", "notification_deliveries", ["sent_at"])
    op.create_index("ix_notification_deliveries_created_at", "notification_deliveries", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_notification_deliveries_created_at", table_name="notification_deliveries")
    op.drop_index("ix_notification_deliveries_sent_at", table_name="notification_deliveries")
    op.drop_index("ix_notification_deliveries_next_attempt_at", table_name="notification_deliveries")
    op.drop_index("ix_notification_deliveries_status", table_name="notification_deliveries")
    op.drop_index("ix_notification_deliveries_channel", table_name="notification_deliveries")
    op.drop_index("ix_notification_deliveries_subscription_id", table_name="notification_deliveries")
    op.drop_index("ix_notification_deliveries_notification_id", table_name="notification_deliveries")
    op.drop_table("notification_deliveries")
    op.drop_index("ix_notification_dispatches_processed_at", table_name="notification_dispatches")
    op.drop_table("notification_dispatches")
    op.drop_index("ix_push_subscriptions_revoked_at", table_name="push_subscriptions")
    op.drop_index("ix_push_subscriptions_last_used_at", table_name="push_subscriptions")
    op.drop_index("ix_push_subscriptions_target_hash", table_name="push_subscriptions")
    op.drop_index("ix_push_subscriptions_channel", table_name="push_subscriptions")
    op.drop_index("ix_push_subscriptions_user_id", table_name="push_subscriptions")
    op.drop_table("push_subscriptions")
    op.drop_table("notification_preferences")
