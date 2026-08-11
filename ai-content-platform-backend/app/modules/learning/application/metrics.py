"""Learning metrics — growth of examples/rules/preferences."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class LearningMetricsSnapshot:
    captures: int = 0
    processed_artifacts: int = 0
    stored_artifacts: int = 0
    examples_grown: int = 0
    rules_grown: int = 0
    preferences_grown: int = 0


@dataclass
class InMemoryLearningMetrics:
    snap: LearningMetricsSnapshot = field(default_factory=LearningMetricsSnapshot)

    def record_capture(self) -> None:
        self.snap.captures += 1

    def record_process(self, count: int) -> None:
        self.snap.processed_artifacts += count

    def record_store(self, count: int) -> None:
        self.snap.stored_artifacts += count

    def record_example(self) -> None:
        self.snap.examples_grown += 1

    def record_rule(self) -> None:
        self.snap.rules_grown += 1

    def record_preference(self) -> None:
        self.snap.preferences_grown += 1
