"""Review metrics — approval/rejection rates, review time, edit distance."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ReviewMetricsSnapshot:
    approvals: int = 0
    rejections: int = 0
    edits: int = 0
    needs_changes: int = 0
    queue_depth: int = 0
    review_time_ms: int = 0
    edit_distance_total: int = 0
    assignments: int = 0


@dataclass
class InMemoryReviewMetrics:
    snap: ReviewMetricsSnapshot = field(default_factory=ReviewMetricsSnapshot)

    def record_approval(self, *, review_time_ms: int = 0) -> None:
        self.snap.approvals += 1
        self.snap.review_time_ms += review_time_ms

    def record_rejection(self, *, review_time_ms: int = 0) -> None:
        self.snap.rejections += 1
        self.snap.review_time_ms += review_time_ms

    def record_edit(self, *, edit_distance: int = 0) -> None:
        self.snap.edits += 1
        self.snap.edit_distance_total += edit_distance

    def record_needs_changes(self) -> None:
        self.snap.needs_changes += 1

    def set_queue_depth(self, depth: int) -> None:
        self.snap.queue_depth = depth

    def record_assignment(self, count: int = 1) -> None:
        self.snap.assignments += count

    def approval_rate(self) -> float:
        total = self.snap.approvals + self.snap.rejections
        if total == 0:
            return 0.0
        return self.snap.approvals / total
