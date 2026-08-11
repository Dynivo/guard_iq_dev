"""M10r Visual Intelligence refinements — layout, asset intel, quality, embeddings, replay.

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("image_jobs", sa.Column("layout_plan_json", JSONB(), nullable=True))
    op.add_column("image_jobs", sa.Column("asset_intelligence_json", JSONB(), nullable=True))
    op.add_column("image_jobs", sa.Column("quality_breakdown_json", JSONB(), nullable=True))
    op.add_column("image_jobs", sa.Column("embedding_json", JSONB(), nullable=True))
    op.add_column("image_jobs", sa.Column("seed", sa.Integer(), nullable=True))
    op.add_column("image_jobs", sa.Column("brief_json", JSONB(), nullable=True))
    op.add_column("image_jobs", sa.Column("replay_record_json", JSONB(), nullable=True))


def downgrade() -> None:
    for col in (
        "replay_record_json",
        "brief_json",
        "seed",
        "embedding_json",
        "quality_breakdown_json",
        "asset_intelligence_json",
        "layout_plan_json",
    ):
        op.drop_column("image_jobs", col)
