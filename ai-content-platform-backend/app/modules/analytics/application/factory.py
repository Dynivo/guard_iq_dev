"""Factory for ObservabilityEngine."""

from __future__ import annotations

from pathlib import Path

from app.modules.analytics.application.engine import ObservabilityEngine


class AnalyticsFactory:
    @staticmethod
    def create_memory(*, config_dir: Path | str | None = None) -> ObservabilityEngine:
        return ObservabilityEngine(config_dir=str(config_dir) if config_dir else None)
