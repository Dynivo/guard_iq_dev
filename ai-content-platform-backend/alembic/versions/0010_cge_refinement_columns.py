"""CGE refinements — quality breakdown, visual brief, safety, draft metadata (M9r).

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("drafts", sa.Column("quality_breakdown_json", JSONB(), nullable=True))
    op.add_column("drafts", sa.Column("visual_brief_json", JSONB(), nullable=True))
    op.add_column("drafts", sa.Column("safety_json", JSONB(), nullable=True))
    op.add_column("drafts", sa.Column("draft_metadata_json", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("drafts", "draft_metadata_json")
    op.drop_column("drafts", "safety_json")
    op.drop_column("drafts", "visual_brief_json")
    op.drop_column("drafts", "quality_breakdown_json")
