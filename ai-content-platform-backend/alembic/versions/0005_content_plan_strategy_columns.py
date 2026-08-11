"""Add ContentPlan strategy columns (M6).

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("content_plans", sa.Column("confidence", sa.Float(), nullable=True))
    op.add_column(
        "content_plans", sa.Column("strategy_action", sa.String(length=30), nullable=True)
    )
    op.add_column("content_plans", sa.Column("rejected_reason", sa.Text(), nullable=True))
    op.add_column(
        "content_plans",
        sa.Column("correlation_id", sa.String(length=100), nullable=True),
    )
    op.create_index(
        "ix_content_plans_correlation_id",
        "content_plans",
        ["correlation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_content_plans_correlation_id", table_name="content_plans")
    op.drop_column("content_plans", "correlation_id")
    op.drop_column("content_plans", "rejected_reason")
    op.drop_column("content_plans", "strategy_action")
    op.drop_column("content_plans", "confidence")
