"""In-memory news pipeline metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NewsMetricsRecorder:
    fetches: int = 0
    fetch_failures: int = 0
    articles_processed: int = 0
    duplicates_removed: int = 0
    clusters_formed: int = 0
    scores: list[float] = field(default_factory=list)
    latencies_ms: list[float] = field(default_factory=list)

    def record_fetch(self, *, ok: bool, latency_ms: float = 0.0) -> None:
        self.fetches += 1
        if not ok:
            self.fetch_failures += 1
        if latency_ms:
            self.latencies_ms.append(latency_ms)

    def record_processed(self, n: int) -> None:
        self.articles_processed += n

    def record_duplicates(self, n: int) -> None:
        self.duplicates_removed += n

    def record_clusters(self, n: int) -> None:
        self.clusters_formed += n

    def record_score(self, composite: float) -> None:
        self.scores.append(composite)

    def snapshot(self) -> dict[str, Any]:
        avg_score = sum(self.scores) / len(self.scores) if self.scores else 0.0
        avg_lat = (
            sum(self.latencies_ms) / len(self.latencies_ms) if self.latencies_ms else 0.0
        )
        return {
            "fetches": self.fetches,
            "fetch_success_rate": (
                (self.fetches - self.fetch_failures) / self.fetches if self.fetches else 0.0
            ),
            "articles_processed": self.articles_processed,
            "duplicates_removed": self.duplicates_removed,
            "clusters_formed": self.clusters_formed,
            "avg_score": avg_score,
            "avg_connector_latency_ms": avg_lat,
        }
