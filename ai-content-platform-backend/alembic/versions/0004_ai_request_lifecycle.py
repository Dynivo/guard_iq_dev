"""Add AI request lifecycle table (M5).

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_request_lifecycle",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("correlation_id", sa.String(length=255), nullable=False),
        sa.Column("capability", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("prompt_hash", sa.String(length=64), nullable=True),
        sa.Column("output_hash", sa.String(length=64), nullable=True),
        sa.Column("cache_hit", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("cost_estimate", sa.Float(), nullable=True),
        sa.Column("evaluation_status", sa.String(length=32), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("history_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_request_lifecycle_request_id", "ai_request_lifecycle", ["request_id"])
    op.create_index(
        "ix_ai_request_lifecycle_correlation_id", "ai_request_lifecycle", ["correlation_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_ai_request_lifecycle_correlation_id", table_name="ai_request_lifecycle")
    op.drop_index("ix_ai_request_lifecycle_request_id", table_name="ai_request_lifecycle")
    op.drop_table("ai_request_lifecycle")
