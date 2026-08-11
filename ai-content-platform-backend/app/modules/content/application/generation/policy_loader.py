"""Load generation policy / brand / tone YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.modules.content.domain.models import GenerationPolicy

_DEFAULT = Path(__file__).resolve().parents[5] / "configs" / "content" / "generation"


def load_generation_policy(config_dir: Path | None = None) -> GenerationPolicy:
    root = config_dir or _DEFAULT
    policy_raw = _load(root / "policy.yaml")
    brand_raw = _load(root / "brand.yaml")
    tone_raw = _load(root / "tone.yaml")
    return GenerationPolicy(
        max_hook_chars=int(policy_raw.get("max_hook_chars", 200)),
        max_body_chars=int(policy_raw.get("max_body_chars", 3000)),
        max_cta_chars=int(policy_raw.get("max_cta_chars", 300)),
        min_hook_chars=int(policy_raw.get("min_hook_chars", 10)),
        min_body_chars=int(policy_raw.get("min_body_chars", 40)),
        require_cta=bool(policy_raw.get("require_cta", True)),
        require_hashtags=bool(policy_raw.get("require_hashtags", False)),
        max_hashtags=int(policy_raw.get("max_hashtags", 8)),
        min_carousel_slides=int(policy_raw.get("min_carousel_slides", 3)),
        max_carousel_slides=int(policy_raw.get("max_carousel_slides", 12)),
        min_quality_score=float(policy_raw.get("min_quality_score", 0.45)),
        forbidden_phrases=tuple(brand_raw.get("forbidden_phrases") or ()),
        preferred_vocabulary=tuple(brand_raw.get("preferred_vocabulary") or ()),
        tone_profiles=dict(tone_raw.get("profiles") or {}),
        max_avg_sentence_words=int(policy_raw.get("max_avg_sentence_words", 28)),
        max_passive_ratio=float(policy_raw.get("max_passive_ratio", 0.45)),
    )


def load_brand_config(config_dir: Path | None = None) -> dict[str, Any]:
    root = config_dir or _DEFAULT
    return _load(root / "brand.yaml")


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return raw if isinstance(raw, dict) else {}
