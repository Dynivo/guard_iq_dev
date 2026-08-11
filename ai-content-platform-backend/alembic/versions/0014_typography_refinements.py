"""M11r Typography refinements — slide composition, intelligence, design tokens.

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("typography_assets", sa.Column("slide_composition_json", JSONB(), nullable=True))
    op.add_column(
        "typography_assets", sa.Column("typography_intelligence_json", JSONB(), nullable=True)
    )
    op.add_column("typography_assets", sa.Column("design_tokens_json", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("typography_assets", "design_tokens_json")
    op.drop_column("typography_assets", "typography_intelligence_json")
    op.drop_column("typography_assets", "slide_composition_json")
