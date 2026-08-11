"""Add source catalog columns and seed enterprise free news sources.

Revision ID: 0023
Revises: 0022
Create Date: 2026-08-07
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
import yaml
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CATALOG = (
    Path(__file__).resolve().parents[2]
    / "configs"
    / "news"
    / "sources"
    / "enterprise_free_sources.yaml"
)


def upgrade() -> None:
    op.add_column("news_sources", sa.Column("category", sa.String(length=100), nullable=True))
    op.add_column(
        "news_sources",
        sa.Column("credibility_score", sa.Integer(), nullable=True, server_default="70"),
    )
    op.add_column(
        "news_sources",
        sa.Column("priority", sa.Integer(), nullable=True, server_default="50"),
    )
    op.add_column(
        "news_sources",
        sa.Column("api_key_name", sa.String(length=100), nullable=True),
    )
    op.create_index("ix_news_sources_category", "news_sources", ["category"], unique=False)

    if not _CATALOG.exists():
        return

    raw = yaml.safe_load(_CATALOG.read_text(encoding="utf-8")) or {}
    entries = raw.get("sources") or []
    if not entries:
        return

    bind = op.get_bind()
    org_ids = [row[0] for row in bind.execute(sa.text("SELECT id FROM organizations")).fetchall()]
    if not org_ids:
        return

    for org_id in org_ids:
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name") or "").strip()
            connector = str(entry.get("connector_type") or "").strip()
            if not name or not connector:
                continue
            credibility = int(entry.get("credibility_score") or 70)
            credibility = max(0, min(100, credibility))
            authority = round(credibility / 100.0, 4)
            config = dict(entry.get("config") or {})
            api_key_name = (str(entry.get("api_key_name") or "").strip() or None)
            if api_key_name:
                config.setdefault("api_key_name", api_key_name)
            config.setdefault("catalog_id", str(entry.get("catalog_id") or ""))
            config.setdefault("category", str(entry.get("category") or "technology"))
            category = str(entry.get("category") or "technology").strip().lower()
            schedule = str(entry.get("schedule_cron") or "").strip() or None
            priority = int(entry.get("priority") or 50)
            enabled = bool(entry.get("enabled", True))

            existing = bind.execute(
                sa.text(
                    "SELECT id FROM news_sources "
                    "WHERE organization_id = :org AND name = :name LIMIT 1"
                ),
                {"org": org_id, "name": name},
            ).fetchone()
            if existing:
                bind.execute(
                    sa.text(
                        """
                        UPDATE news_sources SET
                          connector_type = :connector_type,
                          config_json = CAST(:config_json AS jsonb),
                          schedule_cron = :schedule_cron,
                          category = :category,
                          credibility_score = :credibility_score,
                          priority = :priority,
                          api_key_name = :api_key_name,
                          authority = :authority,
                          reliability = :reliability,
                          trust = :trust,
                          updated_at = now()
                        WHERE id = :id
                        """
                    ),
                    {
                        "id": existing[0],
                        "connector_type": connector,
                        "config_json": json.dumps(config),
                        "schedule_cron": schedule,
                        "category": category,
                        "credibility_score": credibility,
                        "priority": priority,
                        "api_key_name": api_key_name,
                        "authority": authority,
                        "reliability": authority,
                        "trust": authority,
                    },
                )
                continue

            bind.execute(
                sa.text(
                    """
                    INSERT INTO news_sources (
                      id, organization_id, name, connector_type, config_json,
                      schedule_cron, enabled, category, credibility_score, priority,
                      api_key_name, authority, reliability, trust,
                      created_at, updated_at
                    ) VALUES (
                      gen_random_uuid(), :org, :name, :connector_type, CAST(:config_json AS jsonb),
                      :schedule_cron, :enabled, :category, :credibility_score, :priority,
                      :api_key_name, :authority, :reliability, :trust,
                      now(), now()
                    )
                    """
                ),
                {
                    "org": org_id,
                    "name": name,
                    "connector_type": connector,
                    "config_json": json.dumps(config),
                    "schedule_cron": schedule,
                    "enabled": enabled,
                    "category": category,
                    "credibility_score": credibility,
                    "priority": priority,
                    "api_key_name": api_key_name,
                    "authority": authority,
                    "reliability": authority,
                    "trust": authority,
                },
            )


def downgrade() -> None:
    op.drop_index("ix_news_sources_category", table_name="news_sources")
    op.drop_column("news_sources", "api_key_name")
    op.drop_column("news_sources", "priority")
    op.drop_column("news_sources", "credibility_score")
    op.drop_column("news_sources", "category")
