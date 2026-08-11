"""Composition planner — camera, aspect, depth."""

from __future__ import annotations

from pathlib import Path

from app.modules.image.application.config_loader import load_yaml
from app.modules.image.domain.models import CompositionPlan, EnrichedVisualBrief, ScenePlan


class DefaultCompositionPlanner:
    def __init__(self, config_dir: Path | None = None) -> None:
        self._cfg = load_yaml("composition.yaml", config_dir)

    def plan(self, brief: EnrichedVisualBrief, scene: ScenePlan) -> CompositionPlan:
        defaults = self._cfg.get("defaults") or {}
        presets = self._cfg.get("aspect_presets") or {}
        aspect = str(defaults.get("aspect_ratio") or "4:5")
        preset = presets.get(aspect) or {}
        camera = brief.camera_angle or str(defaults.get("camera") or "eye_level")
        balance = brief.composition_hint or str(defaults.get("balance") or "rule_of_thirds")
        return CompositionPlan(
            camera=camera,
            perspective=str(defaults.get("perspective") or "mild_depth"),
            balance=balance,
            spacing=str(defaults.get("spacing") or "generous"),
            aspect_ratio=aspect,
            width=int(preset.get("width") or defaults.get("width") or 1080),
            height=int(preset.get("height") or defaults.get("height") or 1350),
            focus=str(defaults.get("focus") or "center_subject"),
            contrast=str(defaults.get("contrast") or "moderate"),
            depth=str(defaults.get("depth") or "layered"),
            metadata={"layout": scene.layout, "safe_area": brief.typography_safe_area},
        )
