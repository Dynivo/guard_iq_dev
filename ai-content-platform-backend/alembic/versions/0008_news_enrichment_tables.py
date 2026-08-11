"""News enrichment tables — entities, events, trends, story timelines, source feedback (M8r).

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "article_entities",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("article_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("article_url", sa.String(length=2048), nullable=True),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("value", sa.String(length=500), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=True),
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
    op.create_index(
        "ix_article_entities_type_value",
        "article_entities",
        ["entity_type", "value"],
        unique=False,
    )

    op.create_table(
        "article_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("article_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("article_url", sa.String(length=2048), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=True),
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

    op.create_table(
        "news_topic_trends",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("topic_key", sa.String(length=255), nullable=False, index=True),
        sa.Column("window_label", sa.String(length=50), nullable=True),
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

    op.create_table(
        "story_timelines",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("story_id", sa.String(length=100), nullable=False, index=True),
        sa.Column("label", sa.String(length=500), nullable=False),
        sa.Column("article_urls", JSONB(), nullable=True),
        sa.Column("events", JSONB(), nullable=True),
        sa.Column("cohesion", sa.Float(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at_story", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=True),
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

    op.create_table(
        "source_feedback_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("source_id", sa.String(length=100), nullable=False, index=True),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("weight", sa.Float(), nullable=True),
        sa.Column("article_id", sa.String(length=100), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=True),
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

    op.add_column(
        "topic_clusters",
        sa.Column("timeline_json", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("topic_clusters", "timeline_json")
    op.drop_table("source_feedback_events")
    op.drop_table("story_timelines")
    op.drop_table("news_topic_trends")
    op.drop_table("article_events")
    op.drop_index("ix_article_entities_type_value", table_name="article_entities")
    op.drop_table("article_entities")
