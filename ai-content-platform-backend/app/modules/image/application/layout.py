"""Layout Intelligence — region geometry only; never renders text."""

from __future__ import annotations

from pathlib import Path

from app.modules.image.application.config_loader import load_yaml
from app.modules.image.domain.models import (
    CompositionPlan,
    EnrichedVisualBrief,
    LayoutPlan,
    LayoutRegion,
    ScenePlan,
)


class DefaultLayoutPlanner:
    """Produces LayoutPlan for M11 typography handoff — no text pixels."""

    def __init__(self, config_dir: Path | None = None) -> None:
        self._cfg = load_yaml("layout.yaml", config_dir)

    def plan(
        self,
        *,
        brief: EnrichedVisualBrief,
        scene: ScenePlan,
        composition: CompositionPlan,
        image_width: int,
        image_height: int,
    ) -> LayoutPlan:
        defaults = self._cfg.get("defaults") or {}
        presets = defaults.get("safe_area_presets") or {}
        key = brief.typography_safe_area or "bottom_third"
        preset = presets.get(key) or presets.get("bottom_third") or {}

        def _region(role: str, raw: dict | None) -> LayoutRegion | None:
            if not isinstance(raw, dict):
                return None
            return LayoutRegion(
                role=role,
                x=float(raw.get("x") or 0.0),
                y=float(raw.get("y") or 0.0),
                width=float(raw.get("width") or 0.0),
                height=float(raw.get("height") or 0.0),
                unit="normalized",
            )

        icons: list[LayoutRegion] = []
        slot = defaults.get("icon_slot") or {}
        gap = float(slot.get("gap") or 0.02)
        base_x = float(slot.get("x") or 0.08)
        for i, _name in enumerate(scene.icons[:4]):
            icons.append(
                LayoutRegion(
                    role=f"icon_{i}",
                    x=base_x + i * (float(slot.get("width") or 0.12) + gap),
                    y=float(slot.get("y") or 0.58),
                    width=float(slot.get("width") or 0.12),
                    height=float(slot.get("height") or 0.08),
                )
            )

        ws = tuple(
            LayoutRegion(
                role=str(item.get("role") or "whitespace"),
                x=float(item.get("x") or 0.0),
                y=float(item.get("y") or 0.0),
                width=float(item.get("width") or 0.0),
                height=float(item.get("height") or 0.0),
            )
            for item in (defaults.get("whitespace") or [])
            if isinstance(item, dict)
        )
        guides = tuple(float(x) for x in (defaults.get("alignment_guides") or (0.08, 0.5, 0.92)))

        return LayoutPlan(
            title=_region("title", preset.get("title")),
            subtitle=_region("subtitle", preset.get("subtitle")),
            cta=_region("cta", preset.get("cta")),
            logo=_region("logo", preset.get("logo")),
            footer=_region("footer", preset.get("footer")),
            icon_regions=tuple(icons),
            illustration_safe=_region("illustration_safe", preset.get("illustration_safe")),
            whitespace_map=ws,
            reading_direction=str(
                scene.reading_direction or defaults.get("reading_direction") or "ltr_top_to_bottom"
            ),
            alignment_guides=guides,
            image_width=image_width or composition.width,
            image_height=image_height or composition.height,
            metadata={
                "never_renders_text": True,
                "safe_area_preset": key,
                "scene_layout": scene.layout,
            },
        )
