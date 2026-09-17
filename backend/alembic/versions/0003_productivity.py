"""Saved views, favorites, recents, time tracking, and custom fields."""

import sqlalchemy as sa
from alembic import op

revision = "0003_productivity"
down_revision = "0002_collaboration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saved_views",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("filters_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("sort_by", sa.String(length=32), nullable=False, server_default="updated_at"),
        sa.Column("sort_direction", sa.String(length=4), nullable=False, server_default="desc"),
        sa.Column("display_mode", sa.String(length=16), nullable=False, server_default="list"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("user_id", "workspace_id", "name", name="uq_saved_view_user_workspace_name"),
    )
    op.create_index("ix_saved_views_user_id", "saved_views", ["user_id"])
    op.create_index("ix_saved_views_workspace_id", "saved_views", ["workspace_id"])
    op.create_index("ix_saved_views_project_id", "saved_views", ["project_id"])

    op.create_table(
        "favorites",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_type", sa.String(length=24), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("user_id", "entity_type", "entity_id", name="uq_favorite_user_entity"),
    )
    op.create_index("ix_favorites_user_id", "favorites", ["user_id"])
    op.create_index("ix_favorites_workspace_id", "favorites", ["workspace_id"])
    op.create_index("ix_favorites_entity_type", "favorites", ["entity_type"])
    op.create_index("ix_favorites_entity_id", "favorites", ["entity_id"])

    op.create_table(
        "recent_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_type", sa.String(length=24), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("user_id", "entity_type", "entity_id", name="uq_recent_item_user_entity"),
    )
    op.create_index("ix_recent_items_user_id", "recent_items", ["user_id"])
    op.create_index("ix_recent_items_workspace_id", "recent_items", ["workspace_id"])
    op.create_index("ix_recent_items_entity_type", "recent_items", ["entity_type"])
    op.create_index("ix_recent_items_entity_id", "recent_items", ["entity_id"])
    op.create_index("ix_recent_items_viewed_at", "recent_items", ["viewed_at"])

    op.create_table(
        "time_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("task_id", sa.Uuid(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_time_entries_task_id", "time_entries", ["task_id"])
    op.create_index("ix_time_entries_user_id", "time_entries", ["user_id"])
    op.create_index("ix_time_entries_started_at", "time_entries", ["started_at"])
    op.create_index("ix_time_entries_ended_at", "time_entries", ["ended_at"])
    op.create_index(
        "uq_time_entries_one_running_per_user",
        "time_entries",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("ended_at IS NULL"),
    )

    op.create_table(
        "custom_fields",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("field_type", sa.String(length=24), nullable=False),
        sa.Column("options_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("workspace_id", "name", name="uq_custom_field_workspace_name"),
    )
    op.create_index("ix_custom_fields_workspace_id", "custom_fields", ["workspace_id"])
    op.create_index("ix_custom_fields_field_type", "custom_fields", ["field_type"])

    op.create_table(
        "custom_field_values",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("custom_field_id", sa.Uuid(), sa.ForeignKey("custom_fields.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.Uuid(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("value_json", sa.Text(), nullable=False, server_default="null"),
        sa.Column("updated_by_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("custom_field_id", "task_id", name="uq_custom_field_value_task"),
    )
    op.create_index("ix_custom_field_values_custom_field_id", "custom_field_values", ["custom_field_id"])
    op.create_index("ix_custom_field_values_task_id", "custom_field_values", ["task_id"])
    op.create_index("ix_custom_field_values_updated_by_id", "custom_field_values", ["updated_by_id"])


def downgrade() -> None:
    op.drop_table("custom_field_values")
    op.drop_table("custom_fields")
    op.drop_table("time_entries")
    op.drop_table("recent_items")
    op.drop_table("favorites")
    op.drop_table("saved_views")
