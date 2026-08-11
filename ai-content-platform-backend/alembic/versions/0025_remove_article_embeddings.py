"""Remove article_embeddings table (Qdrant/embeddings feature removed).

Revision ID: 0025
Revises: 0024
Create Date: 2026-08-11
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_article_embeddings_article_id", table_name="article_embeddings")
    op.drop_table("article_embeddings")


def downgrade() -> None:
    op.create_table(
        "article_embeddings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("article_id", UUID(as_uuid=True), nullable=False),
        sa.Column("model_version", sa.String(100), nullable=False),
        sa.Column("qdrant_id", sa.String(255), nullable=True),
        sa.Column("dimensions", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_article_embeddings_article_id", "article_embeddings", ["article_id"])
