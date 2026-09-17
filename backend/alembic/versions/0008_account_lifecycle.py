"""Add account lifecycle security state.

Revision ID: 0008_account_lifecycle
Revises: 0007_planning_analytics
"""

import sqlalchemy as sa
from alembic import op

revision = "0008_account_lifecycle"
down_revision = "0007_planning_analytics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_security",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_index(
        "ix_account_security_email_verified_at",
        "account_security",
        ["email_verified_at"],
    )
    op.create_table(
        "session_metadata",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index("ix_session_metadata_ip_address", "session_metadata", ["ip_address"])
    op.create_index("ix_session_metadata_last_used_at", "session_metadata", ["last_used_at"])
    op.create_table(
        "account_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=40), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_account_tokens_user_id", "account_tokens", ["user_id"])
    op.create_index("ix_account_tokens_purpose", "account_tokens", ["purpose"])
    op.create_index("ix_account_tokens_token_hash", "account_tokens", ["token_hash"])
    op.create_index("ix_account_tokens_expires_at", "account_tokens", ["expires_at"])
    op.create_index("ix_account_tokens_used_at", "account_tokens", ["used_at"])
    op.create_index("ix_account_tokens_created_at", "account_tokens", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_account_tokens_created_at", table_name="account_tokens")
    op.drop_index("ix_account_tokens_used_at", table_name="account_tokens")
    op.drop_index("ix_account_tokens_expires_at", table_name="account_tokens")
    op.drop_index("ix_account_tokens_token_hash", table_name="account_tokens")
    op.drop_index("ix_account_tokens_purpose", table_name="account_tokens")
    op.drop_index("ix_account_tokens_user_id", table_name="account_tokens")
    op.drop_table("account_tokens")
    op.drop_index("ix_session_metadata_last_used_at", table_name="session_metadata")
    op.drop_index("ix_session_metadata_ip_address", table_name="session_metadata")
    op.drop_table("session_metadata")
    op.drop_index("ix_account_security_email_verified_at", table_name="account_security")
    op.drop_table("account_security")
