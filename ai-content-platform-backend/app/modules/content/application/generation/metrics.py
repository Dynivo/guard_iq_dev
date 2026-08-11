"""Generation metrics recorder."""

from __future__ import annotations


class GenerationMetricsRecorder:
    def __init__(self) -> None:
        self.generation_time_ms: float = 0.0
        self.validation_time_ms: float = 0.0
        self.accepted: int = 0
        self.rejected: int = 0
        self.last_scores: dict[str, float] = {}

    def record_generation(self, ms: float) -> None:
        self.generation_time_ms = ms

    def record_validation(self, ms: float) -> None:
        self.validation_time_ms = ms

    def record_outcome(self, *, accepted: bool, scores: dict[str, float]) -> None:
        if accepted:
            self.accepted += 1
        else:
            self.rejected += 1
        self.last_scores = dict(scores)

    def snapshot(self) -> dict:
        total = self.accepted + self.rejected
        return {
            "generation_time_ms": self.generation_time_ms,
            "validation_time_ms": self.validation_time_ms,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "acceptance_rate": (self.accepted / total) if total else 0.0,
            "rejection_rate": (self.rejected / total) if total else 0.0,
            "scores": dict(self.last_scores),
        }
