"""Scope task identifiers to their workspace.

Revision ID: 0012_task_identifier_scope
Revises: 0011_invitation_delivery
"""

from alembic import op

revision = "0012_task_identifier_scope"
down_revision = "0011_invitation_delivery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_tasks_identifier", table_name="tasks")
    op.create_index("ix_tasks_identifier", "tasks", ["identifier"], unique=False)
    op.create_unique_constraint(
        "uq_task_identifier_workspace",
        "tasks",
        ["workspace_id", "identifier"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_task_identifier_workspace",
        "tasks",
        type_="unique",
    )
    op.drop_index("ix_tasks_identifier", table_name="tasks")
    op.create_index("ix_tasks_identifier", "tasks", ["identifier"], unique=True)
