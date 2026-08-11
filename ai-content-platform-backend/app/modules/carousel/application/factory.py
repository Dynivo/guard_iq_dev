"""Factory for Carousel Composition & Rendering Engine."""

from __future__ import annotations

from pathlib import Path

from app.modules.carousel.application.engine import DefaultCarouselEngine


class CarouselFactory:
    @staticmethod
    def create_memory(
        *,
        config_dir: Path | None = None,
        use_mock_renderer: bool = True,
    ) -> DefaultCarouselEngine:
        return DefaultCarouselEngine(
            config_dir=config_dir,
            use_mock_renderer=use_mock_renderer,
        )
