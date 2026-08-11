"""Layout enricher — grid/margins/safe zones on M10 LayoutPlan; never renders text."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.modules.typography.application.config_loader import load_typography
from app.modules.typography.domain.models import LayoutEnrichment


class DefaultLayoutEnricher:
    def __init__(self, config_dir: Path | None = None) -> None:
        self._cfg = load_typography("layout.yaml", config_dir)

    def enrich(
        self,
        layout_plan: dict[str, Any],
        *,
        width: int,
        height: int,
    ) -> LayoutEnrichment:
        defaults = self._cfg.get("defaults") or {}
        margins = defaults.get("margins") or {}
        plan = dict(layout_plan or {})
        # Scale region hints when target size differs from plan size
        src_w = int(plan.get("image_width") or width or 1080)
        src_h = int(plan.get("image_height") or height or 1350)
        plan["image_width"] = width
        plan["image_height"] = height
        plan["metadata"] = {
            **dict(plan.get("metadata") or {}),
            "scaled_from": [src_w, src_h],
            "never_renders_text": True,
        }

        safe_zones: list[dict[str, Any]] = []
        for role in ("title", "subtitle", "cta", "footer", "logo"):
            region = plan.get(role)
            if isinstance(region, dict):
                safe_zones.append({**region, "role": role, "safe_overlay": True})
        illustration = plan.get("illustration_safe")
        if isinstance(illustration, dict):
            safe_zones.append({**illustration, "role": "illustration_safe", "safe_overlay": False})

        return LayoutEnrichment(
            layout_plan=plan,
            grid_columns=int(defaults.get("grid_columns") or 12),
            grid_gutter=float(defaults.get("grid_gutter") or 0.02),
            margin_top=float(margins.get("top") or 0.04),
            margin_right=float(margins.get("right") or 0.06),
            margin_bottom=float(margins.get("bottom") or 0.04),
            margin_left=float(margins.get("left") or 0.06),
            safe_overlay_zones=tuple(safe_zones),
            visual_hierarchy=tuple(str(x) for x in (defaults.get("hierarchy") or ())),
            width=width,
            height=height,
            metadata={"source": "layout_enricher", "never_renders_text": True},
        )
