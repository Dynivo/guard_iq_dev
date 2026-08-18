"""Prioritize the three original GuardIQ news sources.

Revision ID: 0027
Revises: 0026
Create Date: 2026-08-18
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0027"
down_revision: Union[str, None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE news_sources
        SET priority = 300,
            config_json = jsonb_set(
                COALESCE(config_json, '{}'::jsonb),
                '{feed_url}',
                '"https://www.ncsc.gov.uk/api/1/services/v1/all-rss-feed.xml"'::jsonb,
                true
            ),
            updated_at = now()
        WHERE name IN ('NCSC', 'NCSC UK')
           OR config_json ->> 'catalog_id' = 'ncsc_uk'
        """
    )
    op.execute(
        """
        UPDATE news_sources
        SET priority = 290,
            connector_type = 'msrc',
            updated_at = now()
        WHERE name IN ('Microsoft Security Response Center', 'Microsoft Security (MSRC)')
           OR config_json ->> 'catalog_id' = 'msrc_security'
        """
    )
    op.execute(
        """
        UPDATE news_sources
        SET priority = 280,
            updated_at = now()
        WHERE name = 'The Hacker News'
           OR config_json ->> 'catalog_id' = 'the_hacker_news'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE news_sources
        SET priority = 100,
            config_json = jsonb_set(
                COALESCE(config_json, '{}'::jsonb),
                '{feed_url}',
                '"https://www.ncsc.gov.uk/api/1/services/v1/report-rss-feed.xml"'::jsonb,
                true
            ),
            updated_at = now()
        WHERE name IN ('NCSC', 'NCSC UK')
           OR config_json ->> 'catalog_id' = 'ncsc_uk'
        """
    )
    op.execute(
        """
        UPDATE news_sources
        SET priority = 95,
            connector_type = 'rss',
            updated_at = now()
        WHERE name IN ('Microsoft Security Response Center', 'Microsoft Security (MSRC)')
           OR config_json ->> 'catalog_id' = 'msrc_security'
        """
    )
    op.execute(
        """
        UPDATE news_sources
        SET priority = 80,
            updated_at = now()
        WHERE name = 'The Hacker News'
           OR config_json ->> 'catalog_id' = 'the_hacker_news'
        """
    )
