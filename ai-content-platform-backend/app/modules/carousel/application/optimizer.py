"""Deck optimizer — density / whitespace / consistency / balance / reading order."""

from __future__ import annotations

from pathlib import Path

from app.modules.carousel.domain.models import DeckDefinition, DeckOptimizationResult


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


class DefaultDeckOptimizer:
    def __init__(self, config_dir: Path | None = None) -> None:
        _ = config_dir

    def optimize(self, definition: DeckDefinition) -> DeckOptimizationResult:
        slide_count = max(len(definition.slides), 1)
        layer_counts = [len(s.layer_refs) for s in definition.slides]
        avg_layers = sum(layer_counts) / slide_count if layer_counts else 0.0

        # Visual density: moderate layer count preferred
        visual_density = _clamp(1.0 - abs(avg_layers - 5.0) / 8.0)

        # Whitespace from layout constraints margins
        m = definition.layout_constraints.margins
        avg_m = (
            float(m.get("top") or 0)
            + float(m.get("right") or 0)
            + float(m.get("bottom") or 0)
            + float(m.get("left") or 0)
        ) / 4.0
        whitespace = _clamp(0.4 + avg_m * 5.0)
        if definition.layout_constraints.safe_areas:
            whitespace = _clamp(whitespace + 0.08)

        # Consistency: similar layer counts across slides
        if len(layer_counts) > 1:
            spread = max(layer_counts) - min(layer_counts)
            consistency = _clamp(1.0 - spread / 10.0)
        else:
            consistency = 0.85

        # Balance: presence of constraints + navigation
        nav_ok = all(
            (s.prev_slide_id is not None or s.index == 0)
            and (s.next_slide_id is not None or s.index == slide_count - 1)
            for s in definition.slides
        )
        balance = 0.7 if nav_ok else 0.5
        if definition.layout_constraints.grid_columns >= 8:
            balance = _clamp(balance + 0.15)

        # Reading order: hook early, cta/summary late
        purposes = [s.purpose for s in definition.slides]
        reading_order = 0.6
        if purposes and purposes[0] in ("hook", "hero"):
            reading_order = _clamp(reading_order + 0.2)
        if purposes and purposes[-1] in ("cta", "summary"):
            reading_order = _clamp(reading_order + 0.15)

        return DeckOptimizationResult(
            visual_density=round(visual_density, 4),
            whitespace=round(whitespace, 4),
            consistency=round(consistency, 4),
            balance=round(balance, 4),
            reading_order=round(reading_order, 4),
        )
