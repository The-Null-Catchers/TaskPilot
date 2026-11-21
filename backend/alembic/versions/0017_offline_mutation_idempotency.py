"""Add idempotency metadata for offline mutations.

Revision ID: 0017_offline_idempotency
Revises: 0016_product_settings
"""

from alembic import op
import sqlalchemy as sa

revision = "0017_offline_idempotency"
down_revision = "0016_product_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("last_mutation_id", sa.String(length=64), nullable=True))
    op.add_column("subtasks", sa.Column("client_mutation_id", sa.String(length=64), nullable=True))
    op.add_column("subtasks", sa.Column("last_mutation_id", sa.String(length=64), nullable=True))
    op.add_column("checklists", sa.Column("client_mutation_id", sa.String(length=64), nullable=True))
    op.add_column("checklist_items", sa.Column("client_mutation_id", sa.String(length=64), nullable=True))
    op.add_column("checklist_items", sa.Column("last_mutation_id", sa.String(length=64), nullable=True))
    op.add_column("comments", sa.Column("client_mutation_id", sa.String(length=64), nullable=True))
    op.create_unique_constraint(
        "uq_subtask_task_client_mutation",
        "subtasks",
        ["task_id", "client_mutation_id"],
    )
    op.create_unique_constraint(
        "uq_checklist_task_client_mutation",
        "checklists",
        ["task_id", "client_mutation_id"],
    )
    op.create_unique_constraint(
        "uq_checklist_item_client_mutation",
        "checklist_items",
        ["checklist_id", "client_mutation_id"],
    )
    op.create_unique_constraint(
        "uq_comment_author_client_mutation",
        "comments",
        ["author_id", "client_mutation_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_comment_author_client_mutation", "comments", type_="unique")
    op.drop_constraint("uq_checklist_item_client_mutation", "checklist_items", type_="unique")
    op.drop_constraint("uq_checklist_task_client_mutation", "checklists", type_="unique")
    op.drop_constraint("uq_subtask_task_client_mutation", "subtasks", type_="unique")
    op.drop_column("comments", "client_mutation_id")
    op.drop_column("checklist_items", "last_mutation_id")
    op.drop_column("checklist_items", "client_mutation_id")
    op.drop_column("checklists", "client_mutation_id")
    op.drop_column("subtasks", "last_mutation_id")
    op.drop_column("subtasks", "client_mutation_id")
    op.drop_column("tasks", "last_mutation_id")
