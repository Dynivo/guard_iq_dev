"""Image pipeline metrics collector."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ImageMetricsSnapshot:
    generation_time_ms: int = 0
    queue_time_ms: int = 0
    retries: int = 0
    failures: int = 0
    image_quality: float = 0.0
    validation_results: dict[str, Any] = field(default_factory=dict)
    provider_usage: dict[str, int] = field(default_factory=dict)
    workflow_version: str = ""


class InMemoryImageMetrics:
    def __init__(self) -> None:
        self.last = ImageMetricsSnapshot()
        self.history: list[ImageMetricsSnapshot] = []

    def record(self, snapshot: ImageMetricsSnapshot) -> None:
        self.last = snapshot
        self.history.append(snapshot)
        if len(self.history) > 500:
            self.history = self.history[-500:]
