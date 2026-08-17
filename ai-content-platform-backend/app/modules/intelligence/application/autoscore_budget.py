"""Process-wide rolling-window budget for auto-relevance-scoring dispatches.

Shared between the inline path (news.application.post_ingest) and the
Dramatiq path (workers.ingest) so a burst spread across many sources — or
many separate ingest runs close together — still shares one LLM-spend
budget, instead of each ingest call getting its own fresh cap (which let a
fresh install's many-small-sources-at-once burst slip past a per-batch cap
entirely).
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import get_settings


class _RollingWindowBudget:
    def __init__(self) -> None:
        self._window_start: datetime | None = None
        self._dispatched = 0

    def reserve(self, requested: int) -> int:
        """Grant up to `requested` slots from the current window's remaining
        budget, resetting the window first if it has expired. Returns the
        number actually granted — may be less than requested, including 0."""
        if requested <= 0:
            return 0
        settings = get_settings()
        cap = settings.RELEVANCE_AUTOSCORE_MAX_PER_WINDOW
        if cap <= 0:
            return requested

        now = datetime.now(timezone.utc)
        window_seconds = settings.RELEVANCE_AUTOSCORE_WINDOW_SECONDS
        if (
            self._window_start is None
            or (now - self._window_start).total_seconds() >= window_seconds
        ):
            self._window_start = now
            self._dispatched = 0

        remaining = max(0, cap - self._dispatched)
        granted = min(requested, remaining)
        self._dispatched += granted
        return granted


# Module-level singleton — one budget per process. Note: under
# JOB_BACKEND=dramatiq with multiple worker processes, each process gets its
# own budget (no cross-process coordination); the default inline backend
# runs as a single process, so the budget is truly global there.
autoscore_budget = _RollingWindowBudget()
