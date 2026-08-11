"""M13 Human Review, Approval & Learning Platform — additive tables and columns.

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("examples", "rules", "writing_preferences"):
        op.add_column(table, sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        op.add_column(table, sa.Column("supersedes_id", UUID(as_uuid=True), nullable=True))

    op.create_table(
        "review_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("draft_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("content_type", sa.String(length=50), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version_refs_json", JSONB(), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=True),
    )
    op.create_table(
        "review_assignments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("reviewer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("escalated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_table(
        "review_comments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("author_id", UUID(as_uuid=True), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("parent_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_table(
        "review_decisions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("decision_type", sa.String(length=40), nullable=False),
        sa.Column("actor_id", UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("reason_codes_json", JSONB(), nullable=True),
        sa.Column("categories_json", JSONB(), nullable=True),
        sa.Column("policy_snapshot_json", JSONB(), nullable=True),
    )
    op.create_table(
        "review_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("kind", sa.String(length=60), nullable=False),
        sa.Column("payload_json", JSONB(), nullable=True),
        sa.Column("actor_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_table(
        "learning_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_event_type", sa.String(length=80), nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=False),
        sa.Column("draft_id", UUID(as_uuid=True), nullable=True),
        sa.Column("review_session_id", UUID(as_uuid=True), nullable=True),
        sa.Column("feedback_event_id", UUID(as_uuid=True), nullable=True),
        sa.Column("payload_json", JSONB(), nullable=True),
    )
    op.create_table(
        "preference_updates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("preference_id", UUID(as_uuid=True), nullable=True),
        sa.Column("previous_text", sa.Text(), nullable=True),
        sa.Column("new_text", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("source_learning_event_id", UUID(as_uuid=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("preference_updates")
    op.drop_table("learning_events")
    op.drop_table("review_history")
    op.drop_table("review_decisions")
    op.drop_table("review_comments")
    op.drop_table("review_assignments")
    op.drop_table("review_sessions")
    for table in ("writing_preferences", "rules", "examples"):
        op.drop_column(table, "supersedes_id")
        op.drop_column(table, "version")
