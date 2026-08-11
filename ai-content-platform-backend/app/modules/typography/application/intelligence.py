"""Typography Intelligence — independent layout/copy scores (not overlay a11y)."""

from __future__ import annotations

from pathlib import Path

from app.modules.typography.application.config_loader import load_typography
from app.modules.typography.domain.models import (
    LayoutEnrichment,
    TypographyCopy,
    TypographyIntelligence,
    TypographyPlan,
)


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


class DefaultTypographyIntelligenceScorer:
    def __init__(self, config_dir: Path | None = None) -> None:
        self._cfg = load_typography("intelligence.yaml", config_dir)

    def score(
        self,
        *,
        plan: TypographyPlan,
        copy: TypographyCopy,
        layout: LayoutEnrichment,
        layer_count: int = 0,
    ) -> TypographyIntelligence:
        weights = self._cfg.get("weights") or {}
        headline_len = len(copy.headline or "")
        body_len = len(copy.subtitle or "") + len(copy.cta or "")
        title_style = next((s for s in plan.styles if s.role == "title"), None)
        body_style = next((s for s in plan.styles if s.role == "subtitle"), None)

        # Readability: prefer moderate headline length + adequate body size
        soft = int((self._cfg.get("headline_soft_chars") or 60))
        hard = int((self._cfg.get("headline_hard_chars") or 120))
        if headline_len <= soft:
            readability = 0.95
        elif headline_len <= hard:
            readability = 0.75
        else:
            readability = 0.45
        if body_style and body_style.font_size >= 18:
            readability = _clamp(readability + 0.05)

        # Scanability: hierarchy presence + short CTA
        hierarchy_roles = len(plan.hierarchy) if plan.hierarchy else len(plan.styles)
        scanability = _clamp(0.4 + 0.1 * min(hierarchy_roles, 5))
        if copy.cta and len(copy.cta) <= 40:
            scanability = _clamp(scanability + 0.15)

        # Density: layer count vs canvas (lower density = better score when sparse)
        area = max(plan.width * plan.height, 1)
        text_chars = headline_len + body_len + len(copy.footer or "")
        density_raw = (text_chars / 80.0) + (layer_count / 12.0)
        density = _clamp(1.0 - abs(density_raw - 1.0) * 0.35)

        # Hierarchy: title larger than body
        hierarchy = 0.6
        if title_style and body_style and title_style.font_size > body_style.font_size:
            hierarchy = _clamp(
                0.7 + min((title_style.font_size - body_style.font_size) / 80.0, 0.25)
            )
        elif title_style:
            hierarchy = 0.75

        # Whitespace: margins / safe zones from layout enrichment
        avg_m = (
            float(layout.margin_top)
            + float(layout.margin_right)
            + float(layout.margin_bottom)
            + float(layout.margin_left)
        ) / 4.0
        whitespace = _clamp(0.45 + avg_m * 4.0)
        if layout.safe_overlay_zones:
            whitespace = _clamp(whitespace + 0.08)

        _ = weights
        return TypographyIntelligence(
            readability=round(readability, 4),
            scanability=round(scanability, 4),
            density=round(density, 4),
            hierarchy=round(hierarchy, 4),
            whitespace=round(whitespace, 4),
        )
