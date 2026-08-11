"""Enterprise free news source catalog — URLs live here, not in business logic."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_CATALOG_PATH = (
    Path(__file__).resolve().parents[4] / "configs" / "news" / "sources" / "enterprise_free_sources.yaml"
)


@lru_cache(maxsize=1)
def load_enterprise_source_catalog() -> list[dict[str, Any]]:
    """Return catalog entries from YAML (empty list if missing)."""
    if not _CATALOG_PATH.exists():
        return []
    raw = yaml.safe_load(_CATALOG_PATH.read_text(encoding="utf-8")) or {}
    items = raw.get("sources") or []
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        connector = str(item.get("connector_type") or "").strip()
        if not name or not connector:
            continue
        credibility = int(item.get("credibility_score") or 70)
        credibility = max(0, min(100, credibility))
        authority = round(credibility / 100.0, 4)
        out.append(
            {
                "catalog_id": str(item.get("catalog_id") or name).strip().lower().replace(" ", "_"),
                "name": name,
                "category": str(item.get("category") or "technology").strip().lower(),
                "connector_type": connector,
                "schedule_cron": str(item.get("schedule_cron") or "").strip() or None,
                "enabled": bool(item.get("enabled", True)),
                "credibility_score": credibility,
                "priority": int(item.get("priority") or 50),
                "api_key_name": (str(item.get("api_key_name") or "").strip() or None),
                "authority": authority,
                "reliability": authority,
                "trust": authority,
                "config": dict(item.get("config") or {}),
            }
        )
    return out


def catalog_by_category() -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in load_enterprise_source_catalog():
        grouped.setdefault(entry["category"], []).append(entry)
    return grouped
