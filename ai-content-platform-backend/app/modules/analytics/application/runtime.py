"""Process-wide ObservabilityEngine singleton.

EventBus subscribers and HTTP analytics routes MUST share one engine —
otherwise metrics land in memory A while APIs read empty memory B.
"""

from __future__ import annotations

from app.modules.analytics.application.engine import ObservabilityEngine
from app.modules.analytics.application.factory import AnalyticsFactory

_engine: ObservabilityEngine | None = None


def get_observability_engine() -> ObservabilityEngine:
    global _engine
    if _engine is None:
        _engine = AnalyticsFactory.create_memory()
    return _engine


def set_observability_engine(engine: ObservabilityEngine) -> None:
    global _engine
    _engine = engine
