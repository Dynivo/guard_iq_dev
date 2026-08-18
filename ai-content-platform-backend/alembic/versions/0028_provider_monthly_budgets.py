"""Add enforceable aggregate monthly per-provider budgets.

Revision ID: 0028
Revises: 0027
Create Date: 2026-08-18
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0028"
down_revision: Union[str, None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "provider_budgets",
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("monthly_limit_usd", sa.Numeric(12, 6), nullable=False, server_default="10.000000"),
        sa.Column("month_start", sa.Date(), nullable=False),
        sa.Column("spent_usd", sa.Numeric(12, 6), nullable=False, server_default="0.000000"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "provider", name="uq_provider_budgets_org_provider"
        ),
    )
    op.create_index("ix_provider_budgets_organization_id", "provider_budgets", ["organization_id"])

    op.create_table(
        "provider_budget_reservations",
        sa.Column("budget_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["budget_id"], ["provider_budgets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_provider_budget_reservations_budget_id", "provider_budget_reservations", ["budget_id"]
    )
    op.create_index(
        "ix_provider_budget_reservations_expires_at", "provider_budget_reservations", ["expires_at"]
    )

    # Seed every currently configured provider at the requested $10 monthly limit.
    op.execute(
        """
        INSERT INTO provider_budgets
            (id, organization_id, provider, monthly_limit_usd, month_start,
             spent_usd, is_enabled, created_at, updated_at)
        SELECT gen_random_uuid(), organization_id, lower(provider), 10.000000,
               date_trunc('month', now())::date, 0.000000, true, now(), now()
        FROM provider_configs
        GROUP BY organization_id, lower(provider)
        ON CONFLICT (organization_id, provider) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("ix_provider_budget_reservations_expires_at", table_name="provider_budget_reservations")
    op.drop_index("ix_provider_budget_reservations_budget_id", table_name="provider_budget_reservations")
    op.drop_table("provider_budget_reservations")
    op.drop_index("ix_provider_budgets_organization_id", table_name="provider_budgets")
    op.drop_table("provider_budgets")
