"""Resolve how many images to generate for a draft."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_CFG = Path(__file__).resolve().parents[3] / "configs" / "image" / "generation.yaml"


def load_image_generation_policy() -> dict[str, int]:
    raw: dict[str, Any] = {}
    if _CFG.exists():
        loaded = yaml.safe_load(_CFG.read_text(encoding="utf-8")) or {}
        if isinstance(loaded, dict):
            raw = loaded
    return {
        "default_count": int(raw.get("default_count") or 1),
        "min_count": int(raw.get("min_count") or 1),
        "max_count": int(raw.get("max_count") or 4),
    }


def resolve_image_count(
    requested: int | None,
    *,
    brand_extra: dict[str, Any] | None = None,
) -> int:
    """Priority: request override → brand kit extra_settings → yaml default."""
    policy = load_image_generation_policy()
    mn, mx = policy["min_count"], policy["max_count"]
    extra = brand_extra or {}
    default = int(extra.get("default_image_count") or policy["default_count"])
    value = int(requested) if requested is not None else default
    return max(mn, min(mx, value))
