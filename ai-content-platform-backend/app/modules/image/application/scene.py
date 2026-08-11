"""Scene planner — deterministic layout from brief + plan cues."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.modules.image.application.config_loader import load_yaml
from app.modules.image.domain.models import EnrichedVisualBrief, ScenePlan


class DefaultScenePlanner:
    def __init__(self, config_dir: Path | None = None) -> None:
        self._cfg = load_yaml("scene.yaml", config_dir)

    def plan(
        self, brief: EnrichedVisualBrief, *, content_plan: dict[str, Any] | None = None
    ) -> ScenePlan:
        plan = content_plan or {}
        defaults = self._cfg.get("defaults") or {}
        layout_map = self._cfg.get("layout_by_style") or {}
        layout = str(
            layout_map.get(brief.illustration_style) or defaults.get("layout") or "centered_hero"
        )
        charts: tuple[str, ...] = ()
        if str(plan.get("format") or "") == "carousel":
            charts = tuple(self._cfg.get("carousel_charts") or ())
        icons = brief.icons or tuple(defaults.get("icons") or ())
        if isinstance(icons, list):
            icons = tuple(str(i) for i in icons)
        bg = tuple(str(x) for x in (defaults.get("background") or ()))
        meta = brief.metadata or {}
        visual_mode = str(meta.get("visual_mode") or "")
        charts_meta = tuple(
            x.strip() for x in str(meta.get("charts") or "").split(",") if x.strip()
        )
        graphs_meta = tuple(
            x.strip() for x in str(meta.get("graphs") or "").split(",") if x.strip()
        )
        # Prefer short subject labels — never dump the full hook sentence into the prompt
        style = (brief.illustration_style or "").lower()
        if "infographic" in style or visual_mode in {
            "connected_nodes",
            "stat_chart",
            "big_stat",
            "process_pictogram",
            "comparison",
            "flow_nodes",
            "access_control",
            "legal_context",
            "signal_filter",
        }:
            foreground = ("educational infographic focal layout matching post body",)
            layout = "educational_infographic"
        elif brief.focal_point and len(brief.focal_point) <= 48:
            foreground = (brief.focal_point,)
        else:
            foreground = (
                "professional subject with clear prop (chart, nodes, or device)",
            )
        objects = tuple(brief.infographic_suggestions[:4]) or tuple(
            str(x) for x in (defaults.get("objects") or ())
        )
        return ScenePlan(
            layout=layout,
            foreground=foreground,
            background=bg or ("soft gradient workspace", "clean negative space"),
            objects=objects,
            people=tuple(str(x) for x in (defaults.get("people") or ())),
            icons=icons,
            graphs=graphs_meta or tuple(str(x) for x in (defaults.get("graphs") or ())),
            charts=charts_meta or charts,
            white_space=str(defaults.get("white_space") or "generous"),
            reading_direction=str(defaults.get("reading_direction") or "ltr_top_to_bottom"),
            visual_hierarchy=brief.visual_hierarchy,
            metadata={
                "theme": brief.theme,
                "scene_hint": brief.scene_hint,
                "visual_mode": visual_mode,
            },
        )
