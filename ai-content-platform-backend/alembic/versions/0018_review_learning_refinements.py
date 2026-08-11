"""M13r Review & Learning refinements — lifecycle, confidence, signals, reviewer profiles.

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_knowledge_metrics(table: str) -> None:
    op.add_column(table, sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"))
    op.add_column(
        table, sa.Column("approval_count", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(
        table, sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(
        table, sa.Column("success_rate", sa.Float(), nullable=False, server_default="0")
    )
    op.add_column(
        table,
        sa.Column("created_from_review", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(table, sa.Column("last_used", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        table,
        sa.Column("lifecycle", sa.String(length=40), nullable=False, server_default="candidate"),
    )


def _drop_knowledge_metrics(table: str) -> None:
    for col in (
        "lifecycle",
        "last_used",
        "created_from_review",
        "success_rate",
        "usage_count",
        "approval_count",
        "confidence",
    ):
        op.drop_column(table, col)


def upgrade() -> None:
    # examples / rules — add metrics (writing_preferences already has confidence)
    _add_knowledge_metrics("examples")
    _add_knowledge_metrics("rules")
    for col, coltype, default in (
        ("approval_count", sa.Integer(), "0"),
        ("usage_count", sa.Integer(), "0"),
        ("success_rate", sa.Float(), "0"),
        ("created_from_review", sa.Boolean(), None),
        ("last_used", sa.DateTime(timezone=True), None),
        ("lifecycle", sa.String(length=40), "candidate"),
    ):
        if col == "created_from_review":
            op.add_column(
                "writing_preferences",
                sa.Column(col, sa.Boolean(), nullable=False, server_default=sa.text("true")),
            )
        elif col == "last_used":
            op.add_column("writing_preferences", sa.Column(col, coltype, nullable=True))
        elif col == "lifecycle":
            op.add_column(
                "writing_preferences",
                sa.Column(col, coltype, nullable=False, server_default=default),
            )
        else:
            op.add_column(
                "writing_preferences",
                sa.Column(col, coltype, nullable=False, server_default=default),
            )

    op.create_table(
        "knowledge_signals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("signal_type", sa.String(length=80), nullable=False),
        sa.Column("metadata_json", JSONB(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("supersedes_id", UUID(as_uuid=True), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("approval_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "created_from_review", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("last_used", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lifecycle", sa.String(length=40), nullable=False, server_default="candidate"),
    )

    op.create_table(
        "reviewer_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewer_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("review_accuracy", sa.Float(), nullable=False, server_default="0"),
        sa.Column("average_edit_distance", sa.Float(), nullable=False, server_default="0"),
        sa.Column("approval_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("rejection_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("specializations_json", JSONB(), nullable=True),
        sa.Column("recommendation_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("approvals", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejections", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("edits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("edit_distance_total", sa.Float(), nullable=False, server_default="0"),
        sa.Column("metadata_json", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("reviewer_profiles")
    op.drop_table("knowledge_signals")
    for col in (
        "lifecycle",
        "last_used",
        "created_from_review",
        "success_rate",
        "usage_count",
        "approval_count",
    ):
        op.drop_column("writing_preferences", col)
    _drop_knowledge_metrics("rules")
    _drop_knowledge_metrics("examples")
