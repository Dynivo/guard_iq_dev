"""Planning-time visual quality scores (LinkedIn designer bar)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.modules.image.application.config_loader import load_yaml


def score_visual_plan(
    *,
    pattern: dict[str, Any],
    message: dict[str, Any],
    story: dict[str, Any],
    design_tokens: dict[str, Any],
    brand: dict[str, Any] | None = None,
    config_dir: Path | None = None,
) -> dict[str, Any]:
    """Return dimension scores + overall; never hard-fails the API."""
    cfg = load_yaml("visual_quality.yaml", config_dir)
    weights = dict(cfg.get("weights") or {})
    threshold = float(cfg.get("threshold") or 0.72)

    brand = brand or {}
    has_palette = bool(
        brand.get("primary_color")
        or brand.get("secondary_color")
        or brand.get("accent_color")
    )
    pattern_id = str(pattern.get("id") or "")
    hierarchy = str(story.get("visual_hierarchy") or pattern.get("visual_hierarchy") or "")
    whitespace = str(pattern.get("whitespace") or design_tokens.get("density") or "")
    beats = list(story.get("beats") or [])
    avoid = list(pattern.get("always_avoid") or [])

    dims = {
        "visual_quality": 0.78 + (0.08 if pattern_id else 0.0),
        "linkedin_score": 0.82 if "generous" in whitespace or "editorial" in whitespace else 0.72,
        "readability": 0.85 if len(beats) >= 2 else 0.68,
        "whitespace": 0.86 if "generous" in whitespace or design_tokens.get("density") else 0.70,
        "brand_consistency": 0.88 if has_palette else 0.74,
        "hierarchy": 0.84 if "→" in hierarchy or "->" in hierarchy else 0.70,
        "contrast": 0.80,
        "accessibility": 0.78,
        "professionalism": 0.90 if avoid else 0.75,
        "scroll_stopper": 0.76 if pattern_id in {
            "decision_funnel", "key_statistics", "warning_card", "risk_meter"
        } else 0.70,
        "curiosity": 0.74 if message.get("desired_emotion") else 0.65,
    }
    # Cap
    dims = {k: min(1.0, float(v)) for k, v in dims.items()}

    if not weights:
        overall = sum(dims.values()) / len(dims)
    else:
        total_w = 0.0
        acc = 0.0
        for k, w in weights.items():
            if k in dims:
                acc += dims[k] * float(w)
                total_w += float(w)
        overall = acc / total_w if total_w else sum(dims.values()) / len(dims)

    passes = overall >= threshold
    upgrade = None
    if not passes:
        upgrade = str(cfg.get("upgrade_fallback_pattern") or "modern_infographic")

    return {
        "dimensions": dims,
        "overall": round(overall, 4),
        "threshold": threshold,
        "passes": passes,
        "upgrade_fallback_pattern": upgrade,
        "fail_closed": bool(cfg.get("fail_closed")),
    }
