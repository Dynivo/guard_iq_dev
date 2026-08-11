"""Source Manager + YAML Source Registry."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.modules.news.domain.models import SourceDefinition

_DEFAULT_DIR = Path(__file__).resolve().parents[4] / "configs" / "news"


class YamlSourceRegistry:
    def __init__(self, config_dir: Path | None = None) -> None:
        self._dir = config_dir or _DEFAULT_DIR
        self._sources: dict[str, SourceDefinition] = {}
        self._load()

    def _load(self) -> None:
        sources_dir = self._dir / "sources"
        if not sources_dir.exists():
            return
        for path in sorted(sources_dir.glob("*.yaml")):
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if not isinstance(raw, dict):
                continue
            items = raw.get("sources") if "sources" in raw else [raw]
            if not isinstance(items, list):
                items = [raw]
            for item in items:
                if not isinstance(item, dict):
                    continue
                sid = str(item.get("source_id") or item.get("id") or path.stem)
                defn = SourceDefinition(
                    source_id=sid,
                    name=str(item.get("name") or sid),
                    connector_type=str(item.get("connector_type") or "rss"),
                    config=dict(item.get("config") or {}),
                    schedule_cron=str(item.get("schedule_cron") or ""),
                    enabled=bool(item.get("enabled", True)),
                    organization_id=str(item.get("organization_id") or ""),
                    authority=float(item.get("authority", 0.5)),
                    reliability=float(item.get("reliability", 0.5)),
                    trust=float(item.get("trust", 0.5)),
                )
                self._sources[sid] = defn

    def list_all(self) -> list[SourceDefinition]:
        return list(self._sources.values())

    def get(self, source_id: str) -> SourceDefinition | None:
        return self._sources.get(source_id)

    def register(self, definition: SourceDefinition) -> None:
        self._sources[definition.source_id] = definition


class DefaultSourceManager:
    def __init__(self, registry: YamlSourceRegistry) -> None:
        self._registry = registry

    def list_enabled(self, organization_id: str | None = None) -> list[SourceDefinition]:
        out = []
        for s in self._registry.list_all():
            if not s.enabled:
                continue
            if organization_id and s.organization_id and s.organization_id != organization_id:
                continue
            out.append(s)
        return out

    def get(self, source_id: str) -> SourceDefinition | None:
        return self._registry.get(source_id)


def load_news_policy(config_dir: Path | None = None) -> Any:
    from app.modules.news.domain.models import NewsPolicy

    root = config_dir or _DEFAULT_DIR
    path = root / "default_policy.yaml"
    raw: dict[str, Any] = {}
    if path.exists():
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if isinstance(loaded, dict):
            raw = loaded
    weights = raw.get("score_weights") or {}
    return NewsPolicy(
        policy_id=str(raw.get("policy_id") or "default"),
        title_similarity_threshold=float(
            raw.get("title_similarity_threshold", 0.85)
        ),
        cluster_similarity_threshold=float(
            raw.get("cluster_similarity_threshold", 0.55)
        ),
        cluster_time_window_hours=int(raw.get("cluster_time_window_hours", 72)),
        max_cluster_size=int(raw.get("max_cluster_size", 20)),
        min_authority=float(raw.get("min_authority", 0.0)),
        score_weights={
            "relevance": float(weights.get("relevance", 0.20)),
            "importance": float(weights.get("importance", 0.12)),
            "authority": float(weights.get("authority", 0.12)),
            "novelty": float(weights.get("novelty", 0.10)),
            "trend": float(weights.get("trend", 0.10)),
            "business_impact": float(weights.get("business_impact", 0.12)),
            "organization_relevance": float(
                weights.get("organization_relevance", 0.14)
            ),
            "freshness": float(weights.get("freshness", 0.10)),
        },
        relevant_composite_threshold=float(
            raw.get("relevant_composite_threshold", 0.45)
        ),
    )
