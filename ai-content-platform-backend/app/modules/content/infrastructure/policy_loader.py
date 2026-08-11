"""YAML Planner Policy loader."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.modules.content.domain.models import PlannerPolicy

_DEFAULT_DIR = Path(__file__).resolve().parents[4] / "configs" / "planner"


class YamlPlannerPolicyLoader:
    def __init__(self, config_dir: Path | None = None) -> None:
        self._dir = config_dir or _DEFAULT_DIR

    def load(self, policy_id: str = "default") -> PlannerPolicy:
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
    def _from_dict(policy_id: str, raw: dict[str, Any]) -> PlannerPolicy:
        return PlannerPolicy(
            policy_id=str(raw.get("policy_id") or policy_id or "default"),
            min_relevance=float(raw.get("min_relevance", 0.3)),
            max_duplicate_score=float(raw.get("max_duplicate_score", 0.85)),
            min_confidence=float(raw.get("min_confidence", 0.4)),
            preferred_audiences=tuple(
                str(x) for x in (raw.get("preferred_audiences") or [])
            ),
            preferred_content_types=tuple(
                str(x) for x in (raw.get("preferred_content_types") or [])
            ),
            force_carousel_types=tuple(
                str(x)
                for x in (
                    raw.get("force_carousel_types")
                    or ["checklist", "best_practices", "faq", "weekly_roundup"]
                )
            ),
            default_tone=str(raw.get("default_tone") or "professional"),
            default_goal=str(raw.get("default_goal") or "educate"),
            default_cta=str(raw.get("default_cta") or "comment"),
            default_audience=str(raw.get("default_audience") or "business_owners"),
            min_slide_count=int(raw.get("min_slide_count", 5)),
            max_slide_count=int(raw.get("max_slide_count", 10)),
            default_slide_count=int(raw.get("default_slide_count", 7)),
            max_reading_time_minutes=int(raw.get("max_reading_time_minutes", 3)),
            industry_rules=dict(raw.get("industry_rules") or {}),
            organization_rules=dict(raw.get("organization_rules") or {}),
            brand_rules=dict(raw.get("brand_rules") or {}),
            priorities=dict(raw.get("priorities") or {}),
            require_image_style=bool(raw.get("require_image_style", True)),
            require_visual_direction=bool(raw.get("require_visual_direction", True)),
            allowed_ctas=tuple(
                str(x)
                for x in (
                    raw.get("allowed_ctas")
                    or [
                        "follow",
                        "comment",
                        "download",
                        "visit_website",
                        "book_demo",
                        "read_guide",
                    ]
                )
            ),
            diversity_max_type_share=float(raw.get("diversity_max_type_share", 0.5)),
            diversity_max_audience_share=float(
                raw.get("diversity_max_audience_share", 0.6)
            ),
            diversity_max_cta_share=float(raw.get("diversity_max_cta_share", 0.6)),
        )
