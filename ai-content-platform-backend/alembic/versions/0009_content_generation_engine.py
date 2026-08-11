"""Content Generation Engine tables/columns (M9).

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "drafts",
        sa.Column("lifecycle_status", sa.String(length=30), nullable=True),
    )
    op.add_column("drafts", sa.Column("quality_score", sa.Float(), nullable=True))
    op.add_column("drafts", sa.Column("confidence_score", sa.Float(), nullable=True))
    op.add_column(
        "drafts",
        sa.Column("prompt_version", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "drafts",
        sa.Column("provider_metadata_json", JSONB(), nullable=True),
    )
    op.add_column("drafts", sa.Column("draft_json", JSONB(), nullable=True))
    op.add_column("drafts", sa.Column("validation_json", JSONB(), nullable=True))

    op.add_column(
        "draft_versions",
        sa.Column("draft_json", JSONB(), nullable=True),
    )

    op.create_table(
        "generation_replays",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("draft_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("correlation_id", sa.String(length=100), nullable=True, index=True),
        sa.Column("prompt_request_json", JSONB(), nullable=True),
        sa.Column("raw_output", sa.Text(), nullable=True),
        sa.Column("draft_json", JSONB(), nullable=True),
        sa.Column("metrics_json", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("generation_replays")
    op.drop_column("draft_versions", "draft_json")
    op.drop_column("drafts", "validation_json")
    op.drop_column("drafts", "draft_json")
    op.drop_column("drafts", "provider_metadata_json")
    op.drop_column("drafts", "prompt_version")
    op.drop_column("drafts", "confidence_score")
    op.drop_column("drafts", "quality_score")
    op.drop_column("drafts", "lifecycle_status")
