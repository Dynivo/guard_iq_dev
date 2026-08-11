"""Slide Composition Metadata — structured hints for M12; never renders carousels."""

from __future__ import annotations

from pathlib import Path

from app.modules.typography.application.config_loader import load_typography
from app.modules.typography.domain.models import (
    LayoutEnrichment,
    SlideCompositionMetadata,
    TypographyAsset,
    TypographyCopy,
)


class DefaultSlideCompositionPlanner:
    def __init__(self, config_dir: Path | None = None) -> None:
        self._cfg = load_typography("slide_composition.yaml", config_dir)

    def plan(
        self,
        *,
        asset: TypographyAsset,
        layout: LayoutEnrichment,
        copy: TypographyCopy,
        template_id: str = "default",
    ) -> SlideCompositionMetadata:
        mappings = self._cfg.get("template_to_slide_type") or {}
        slide_type = str(mappings.get(template_id) or self._cfg.get("default_slide_type") or "single")
        layout_map = self._cfg.get("template_to_layout") or {}
        preferred_layout = str(layout_map.get(template_id) or template_id or "default")

        body_len = len(copy.subtitle or "") + len(copy.headline or "")
        continuation_threshold = int(self._cfg.get("continuation_char_threshold") or 180)
        continuation = (
            str(self._cfg.get("continuation_hint_long") or "continue_next")
            if body_len >= continuation_threshold
            else str(self._cfg.get("continuation_hint_default") or "none")
        )

        layer_count = len(asset.layers)
        visual_weight = min(1.0, 0.35 + layer_count * 0.08)
        emphasis = 0.55
        if copy.headline:
            title_layers = [L for L in asset.layers if L.role in ("title", "title_bg")]
            if title_layers:
                emphasis = min(1.0, 0.5 + len(copy.headline) / 120.0)

        reading = str(self._cfg.get("default_reading_flow") or "ltr_top_to_bottom")
        if preferred_layout in ("split", "comparison", "before_after"):
            reading = str(self._cfg.get("split_reading_flow") or "ltr_columns")

        transition = str(
            (self._cfg.get("transitions") or {}).get(template_id)
            or self._cfg.get("default_transition")
            or "none"
        )

        return SlideCompositionMetadata(
            preferred_slide_type=slide_type,
            preferred_layout=preferred_layout,
            visual_weight=round(visual_weight, 4),
            reading_flow=reading,
            emphasis_score=round(emphasis, 4),
            transition_hint=transition,
            continuation_hint=continuation,
            metadata={
                "template_id": template_id,
                "layer_count": layer_count,
                "body_chars": body_len,
                "layout_hierarchy": list(layout.visual_hierarchy or ()),
                "renders_carousel": False,
            },
        )
