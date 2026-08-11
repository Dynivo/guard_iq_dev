"""Add workflow_execution_events for Workflow Engine history (hardening).

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflow_execution_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("execution_id", sa.String(length=64), nullable=False),
        sa.Column("event", sa.String(length=64), nullable=False),
        sa.Column("node_id", sa.String(length=128), nullable=True),
        sa.Column("detail_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_workflow_execution_events_execution_id",
        "workflow_execution_events",
        ["execution_id"],
    )
    op.create_index(
        "ix_workflow_execution_events_event",
        "workflow_execution_events",
        ["event"],
    )
    op.create_index(
        "ix_workflow_execution_events_occurred_at",
        "workflow_execution_events",
        ["occurred_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workflow_execution_events_occurred_at",
        table_name="workflow_execution_events",
    )
    op.drop_index(
        "ix_workflow_execution_events_event",
        table_name="workflow_execution_events",
    )
    op.drop_index(
        "ix_workflow_execution_events_execution_id",
        table_name="workflow_execution_events",
    )
    op.drop_table("workflow_execution_events")
