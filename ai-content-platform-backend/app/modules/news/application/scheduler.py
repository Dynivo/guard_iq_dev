"""News Scheduler — cron/manual/webhook/periodic/priority queue (in-process)."""

from __future__ import annotations

import uuid
from collections import deque
from dataclasses import dataclass, field

from app.modules.news.domain.models import ScheduleTrigger, SourceDefinition
from app.modules.news.domain.ports import SourceManager


@dataclass
class _QueueItem:
    source: SourceDefinition
    priority: int = 0
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))


class InProcessNewsScheduler:
    """Distributed-ready interface; default is in-process priority queue."""

    def __init__(self, source_manager: SourceManager) -> None:
        self._sources = source_manager
        self._queue: deque[_QueueItem] = deque()
        self._jobs: dict[str, _QueueItem] = {}

    def due_sources(self, *, trigger: str = "periodic") -> list[SourceDefinition]:
        enabled = self._sources.list_enabled()
        trig = ScheduleTrigger(trigger) if trigger in ScheduleTrigger._value2member_map_ else ScheduleTrigger.PERIODIC
        if trig == ScheduleTrigger.MANUAL:
            return []
        # Cron/periodic: return sources that have a schedule or all enabled for periodic
        if trig == ScheduleTrigger.CRON:
            return [s for s in enabled if s.schedule_cron]
        if trig == ScheduleTrigger.WEBHOOK:
            return []
        if trig == ScheduleTrigger.PRIORITY:
            return sorted(enabled, key=lambda s: s.authority, reverse=True)
        return enabled

    async def enqueue(self, source: SourceDefinition, *, priority: int = 0) -> str:
        item = _QueueItem(source=source, priority=priority)
        # Higher priority first
        if not self._queue:
            self._queue.append(item)
        else:
            inserted = False
            for i, existing in enumerate(self._queue):
                if priority > existing.priority:
                    self._queue.insert(i, item)
                    inserted = True
                    break
            if not inserted:
                self._queue.append(item)
        self._jobs[item.job_id] = item
        return item.job_id

    def pop_next(self) -> _QueueItem | None:
        if not self._queue:
            return None
        return self._queue.popleft()

    def health(self) -> dict:
        return {
            "queue_depth": len(self._queue),
            "jobs_tracked": len(self._jobs),
            "status": "healthy",
        }
