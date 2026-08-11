"""Additive news intelligence columns (M8).

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "news_sources",
        sa.Column("authority", sa.Float(), nullable=True, server_default="0.5"),
    )
    op.add_column(
        "news_sources",
        sa.Column("reliability", sa.Float(), nullable=True, server_default="0.5"),
    )
    op.add_column(
        "news_sources",
        sa.Column("trust", sa.Float(), nullable=True, server_default="0.5"),
    )
    op.add_column(
        "news_sources",
        sa.Column("failure_rate", sa.Float(), nullable=True, server_default="0"),
    )
    op.add_column(
        "news_sources",
        sa.Column("circuit_state", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "news_sources",
        sa.Column("last_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "news_sources",
        sa.Column("health_json", JSONB(), nullable=True),
    )

    op.add_column(
        "articles",
        sa.Column("language", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "articles",
        sa.Column("category", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "articles",
        sa.Column("canonical_url", sa.String(length=2048), nullable=True),
    )
    op.add_column(
        "articles",
        sa.Column("tags", JSONB(), nullable=True),
    )
    op.add_column(
        "articles",
        sa.Column("topic_json", JSONB(), nullable=True),
    )
    op.add_column(
        "articles",
        sa.Column("score_json", JSONB(), nullable=True),
    )

    op.add_column(
        "topic_clusters",
        sa.Column("cohesion_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "topic_clusters",
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "topic_clusters",
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "topic_clusters",
        sa.Column("metadata_json", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("topic_clusters", "metadata_json")
    op.drop_column("topic_clusters", "window_end")
    op.drop_column("topic_clusters", "window_start")
    op.drop_column("topic_clusters", "cohesion_score")
    op.drop_column("articles", "score_json")
    op.drop_column("articles", "topic_json")
    op.drop_column("articles", "tags")
    op.drop_column("articles", "canonical_url")
    op.drop_column("articles", "category")
    op.drop_column("articles", "language")
    op.drop_column("news_sources", "health_json")
    op.drop_column("news_sources", "last_error")
    op.drop_column("news_sources", "circuit_state")
    op.drop_column("news_sources", "failure_rate")
    op.drop_column("news_sources", "trust")
    op.drop_column("news_sources", "reliability")
    op.drop_column("news_sources", "authority")
