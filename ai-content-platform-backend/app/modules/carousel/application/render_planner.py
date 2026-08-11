"""Render planner — strategy and sizes from export profile; no pixels."""

from __future__ import annotations

from pathlib import Path

from app.modules.carousel.application.config_loader import load_carousel
from app.modules.carousel.application.export_profiles import ExportProfileRegistry
from app.modules.carousel.domain.models import Deck, DeckDefinition, RenderPlan


class DefaultRenderPlanner:
    def __init__(self, config_dir: Path | None = None) -> None:
        self._cfg = load_carousel("render.yaml", config_dir)
        self._profiles = ExportProfileRegistry(config_dir)

    def prepare(
        self,
        deck: Deck,
        *,
        width: int = 1080,
        height: int = 1350,
        export_formats: tuple[str, ...] = ("png", "pdf", "zip"),
        export_profile_id: str = "linkedin",
        definition: DeckDefinition | None = None,
    ) -> RenderPlan:
        profile = self._profiles.get(export_profile_id)
        # Prefer explicit request sizes when they differ from defaults; else profile
        if width == 1080 and height == 1350:
            width, height = profile.width, profile.height
        if definition is not None:
            width, height = definition.width, definition.height

        formats = tuple(export_formats) or tuple(profile.formats) or ("svg", "png", "pdf")
        if "svg" not in formats:
            formats = ("svg",) + formats

        strategy = profile.render_strategy or str(
            self._cfg.get("strategy") or "svg_html_playwright"
        )

        return RenderPlan(
            width=width,
            height=height,
            strategy=strategy,
            optimize=bool(self._cfg.get("optimize", True)),
            scale=1.0,
            formats=formats,
            metadata={
                "slide_count": len(deck.slides),
                "renders_pixels": False,
                "deck_id": deck.deck_id,
                "export_profile_id": profile.profile_id,
                "definition_id": definition.definition_id if definition else None,
            },
        )
