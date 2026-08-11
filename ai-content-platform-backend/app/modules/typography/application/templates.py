"""Layout template registry — YAML templates select structure for planner/renderer."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.modules.typography.application.config_loader import load_yaml

_TEMPLATE_IDS = (
    "default",
    "hero",
    "split",
    "timeline",
    "checklist",
    "quote",
    "comparison",
    "statistics",
    "problem_solution",
    "before_after",
)


@dataclass(slots=True)
class LayoutTemplate:
    template_id: str
    name: str
    layer_order: tuple[str, ...] = ()
    region_bias: dict[str, Any] = field(default_factory=dict)
    preferred_slide_type: str = "single"
    preferred_layout: str = "default"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "name": self.name,
            "layer_order": list(self.layer_order),
            "region_bias": dict(self.region_bias),
            "preferred_slide_type": self.preferred_slide_type,
            "preferred_layout": self.preferred_layout,
            "metadata": dict(self.metadata),
        }


class LayoutTemplateRegistry:
    def __init__(self, config_dir: Path | None = None) -> None:
        if config_dir is not None:
            self._root = Path(config_dir) / "templates"
        else:
            self._root = (
                Path(__file__).resolve().parents[4] / "configs" / "typography" / "templates"
            )
        self._cache: dict[str, LayoutTemplate] = {}
        for tid in _TEMPLATE_IDS:
            self._cache[tid] = self._load(tid)

    def list_ids(self) -> tuple[str, ...]:
        return _TEMPLATE_IDS

    def get(self, template_id: str) -> LayoutTemplate:
        key = template_id if template_id in self._cache else "default"
        return self._cache[key]

    def _load(self, template_id: str) -> LayoutTemplate:
        path = self._root / f"{template_id}.yaml"
        raw = load_yaml(path) if path.exists() else {}
        order = raw.get("layer_order") or raw.get("layers_order") or raw.get("layers") or []
        if isinstance(order, list) and order and isinstance(order[0], dict):
            layer_order = tuple(str(item.get("role") or item.get("id") or "") for item in order)
        else:
            layer_order = tuple(str(x) for x in order)
        return LayoutTemplate(
            template_id=template_id,
            name=str(raw.get("name") or template_id.replace("_", " ").title()),
            layer_order=layer_order,
            region_bias=dict(raw.get("region_bias") or raw.get("regions") or {}),
            preferred_slide_type=str(raw.get("preferred_slide_type") or "single"),
            preferred_layout=str(raw.get("preferred_layout") or template_id),
            metadata={
                "source": str(path.name) if path.exists() else "fallback",
                **dict(raw.get("metadata") or {}),
            },
        )
