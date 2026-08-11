"""M12r Carousel refinements — DeckDefinition, dependency graph, optimization, profiles.

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("carousel_assets", sa.Column("deck_definition_json", JSONB(), nullable=True))
    op.add_column("carousel_assets", sa.Column("dependency_graph_json", JSONB(), nullable=True))
    op.add_column("carousel_assets", sa.Column("optimization_json", JSONB(), nullable=True))
    op.add_column(
        "carousel_assets", sa.Column("export_profile", sa.String(length=50), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("carousel_assets", "export_profile")
    op.drop_column("carousel_assets", "optimization_json")
    op.drop_column("carousel_assets", "dependency_graph_json")
    op.drop_column("carousel_assets", "deck_definition_json")
