"""Carousel metrics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CarouselMetricsSnapshot:
    render_time_ms: int = 0
    export_time_ms: int = 0
    slide_count: int = 0
    export_size_bytes: int = 0
    pdf_size_bytes: int = 0
    png_size_bytes: int = 0
    render_failures: int = 0


class InMemoryCarouselMetrics:
    def __init__(self) -> None:
        self.records: list[CarouselMetricsSnapshot] = []

    def record(self, snap: CarouselMetricsSnapshot) -> None:
        self.records.append(snap)
