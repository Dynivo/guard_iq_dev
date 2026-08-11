"""Typography pipeline metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TypographyMetricsSnapshot:
    render_time_ms: int = 0
    validation_time_ms: int = 0
    accessibility_score: float = 0.0
    brand_score: float = 0.0
    typography_score: float = 0.0
    contrast_score: float = 0.0
    overflow_rate: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class InMemoryTypographyMetrics:
    def __init__(self) -> None:
        self.last = TypographyMetricsSnapshot()
        self.history: list[TypographyMetricsSnapshot] = []

    def record(self, snapshot: TypographyMetricsSnapshot) -> None:
        self.last = snapshot
        self.history.append(snapshot)
        if len(self.history) > 500:
            self.history = self.history[-500:]
