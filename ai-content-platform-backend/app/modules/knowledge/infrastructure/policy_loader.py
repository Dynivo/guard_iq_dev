"""YAML Knowledge Policy loader."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.modules.knowledge.domain.models import KnowledgePolicy, RankingWeights

_DEFAULT_DIR = Path(__file__).resolve().parents[4] / "configs" / "knowledge"


class YamlKnowledgePolicyLoader:
    def __init__(self, config_dir: Path | None = None) -> None:
        self._dir = config_dir or _DEFAULT_DIR

    def load(self, policy_id: str = "default") -> KnowledgePolicy:
        path = self._resolve_path(policy_id)
        raw: dict[str, Any] = {}
        if path.exists():
            loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(loaded, dict):
                raw = loaded
        return self._from_dict(policy_id, raw)

    def _resolve_path(self, policy_id: str) -> Path:
        if policy_id and policy_id != "default":
            org = self._dir / "orgs" / f"{policy_id}.yaml"
            if org.exists():
                return org
            named = self._dir / f"{policy_id}.yaml"
            if named.exists():
                return named
        return self._dir / "default_policy.yaml"

    @staticmethod
    def _from_dict(policy_id: str, raw: dict[str, Any]) -> KnowledgePolicy:
        freshness = raw.get("freshness") or {}
        organization = raw.get("organization") or {}
        language = raw.get("language") or {}
        category = raw.get("category") or {}
        compliance = raw.get("compliance") or {}
        weights_raw = raw.get("ranking_weights") or {}
        weights = RankingWeights(
            similarity=float(weights_raw.get("similarity", 0.35)),
            keyword=float(weights_raw.get("keyword", 0.15)),
            reliability=float(weights_raw.get("reliability", 0.12)),
            freshness=float(weights_raw.get("freshness", 0.10)),
            authority=float(weights_raw.get("authority", 0.08)),
            organization_relevance=float(
                weights_raw.get("organization_relevance", 0.08)
            ),
            confidence=float(weights_raw.get("confidence", 0.07)),
            feedback=float(weights_raw.get("feedback", 0.05)),
        )
        source_priority = tuple(str(x) for x in (raw.get("source_priority") or []))
        allowed_langs = tuple(str(x) for x in (language.get("allowed") or ["en"]))
        deny_langs = tuple(str(x) for x in (language.get("deny") or []))
        allowed_types = tuple(str(x) for x in (category.get("allowed_types") or []))
        return KnowledgePolicy(
            policy_id=str(raw.get("policy_id") or policy_id or "default"),
            source_priority=source_priority,
            max_age_days=int(freshness.get("max_age_days", 365)),
            stale_below_score=float(freshness.get("stale_below_score", 0.2)),
            require_org_match=bool(organization.get("require_match", True)),
            allowed_languages=allowed_langs,
            deny_languages=deny_langs,
            allowed_types=allowed_types,
            min_confidence=float(compliance.get("min_confidence", 0.05)),
            min_reliability=float(compliance.get("min_reliability", 0.1)),
            drop_duplicate_claims=bool(compliance.get("drop_duplicate_claims", True)),
            drop_content_duplicates=bool(
                compliance.get("drop_content_duplicates", True)
            ),
            min_rank_score=float(compliance.get("min_rank_score", 0.05)),
            ranking_weights=weights,
        )
