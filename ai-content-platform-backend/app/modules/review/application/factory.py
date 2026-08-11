"""Factory for ReviewEngine."""

from __future__ import annotations

from pathlib import Path

from app.modules.review.application.engine import ReviewEngine
from app.shared.events.ports import EventBus


class ReviewFactory:
    @staticmethod
    def create_memory(
        *,
        config_dir: Path | str | None = None,
        event_bus: EventBus | None = None,
    ) -> ReviewEngine:
        return ReviewEngine(
            config_dir=str(config_dir) if config_dir else None,
            event_bus=event_bus,
        )
