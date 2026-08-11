"""Factory for Brand & Typography Engine."""

from __future__ import annotations

from pathlib import Path

from app.modules.typography.application.engine import DefaultBrandTypographyEngine


class TypographyFactory:
    @staticmethod
    def create_memory(
        *,
        config_dir: Path | None = None,
        brand_config_dir: Path | None = None,
    ) -> DefaultBrandTypographyEngine:
        return DefaultBrandTypographyEngine(
            config_dir=config_dir,
            brand_config_dir=brand_config_dir,
        )
