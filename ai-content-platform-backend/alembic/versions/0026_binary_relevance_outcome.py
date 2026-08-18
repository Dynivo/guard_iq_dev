"""Collapse the legacy reference outcome into rejected.

Revision ID: 0026
Revises: 0025
Create Date: 2026-08-18
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0026"
down_revision: Union[str, None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE articles
        SET status = 'irrelevant',
            score_json = jsonb_set(
                jsonb_set(
                    jsonb_set(
                        COALESCE(score_json, '{}'::jsonb),
                        '{decision}', '"rejected"'::jsonb, true
                    ),
                    '{article_type}', '"reject"'::jsonb, true
                ),
                '{binary_outcome_migrated}', 'true'::jsonb, true
            ),
            updated_at = now()
        WHERE status = 'reference'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE articles
        SET status = 'reference',
            score_json = jsonb_set(
                jsonb_set(
                    COALESCE(score_json, '{}'::jsonb) - 'binary_outcome_migrated',
                    '{decision}', '"reference"'::jsonb, true
                ),
                '{article_type}', '"reference"'::jsonb, true
            ),
            updated_at = now()
        WHERE score_json ->> 'binary_outcome_migrated' = 'true'
        """
    )
