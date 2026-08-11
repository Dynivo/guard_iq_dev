"""Add capture_sessions and capture_assets tables.

Revision ID: 0022
Revises: 0021
Create Date: 2026-08-07
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "capture_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_type", sa.String(length=50), nullable=False),
        sa.Column("photo_mode", sa.String(length=30), nullable=False, server_default="none"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="intake"),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("follow_up_questions_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("follow_up_answers_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("shot_list_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("draft_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["draft_id"], ["drafts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_capture_sessions_organization_id", "capture_sessions", ["organization_id"])
    op.create_index("ix_capture_sessions_draft_id", "capture_sessions", ["draft_id"])

    op.create_table(
        "capture_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["capture_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_capture_assets_organization_id", "capture_assets", ["organization_id"])
    op.create_index("ix_capture_assets_session_id", "capture_assets", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_capture_assets_session_id", table_name="capture_assets")
    op.drop_index("ix_capture_assets_organization_id", table_name="capture_assets")
    op.drop_table("capture_assets")
    op.drop_index("ix_capture_sessions_draft_id", table_name="capture_sessions")
    op.drop_index("ix_capture_sessions_organization_id", table_name="capture_sessions")
    op.drop_table("capture_sessions")
