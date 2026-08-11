"""In-memory consensus run repository (Postgres adapter planned with Alembic 0020)."""

from __future__ import annotations

import copy
from typing import Any

from app.core.logging import get_logger
from app.modules.consensus.domain.models import ConsensusRun

logger = get_logger(__name__)


class InMemoryCandidateRepository:
    """Process-local store for ConsensusRun + replay snapshots.

    Note: Replace with a PostgresCandidateRepository (Alembic migration 0020)
    when multi-process / durable persistence is required.
    """

    def __init__(self) -> None:
        self._runs: dict[str, ConsensusRun] = {}
        self._replay: dict[str, dict[str, Any]] = {}

    async def save_run(self, run: ConsensusRun) -> None:
        self._runs[run.run_id] = run
        self._replay[run.run_id] = self._snapshot(run)
        logger.info(
            "consensus.run_saved",
            extra={
                "app_module": "consensus",
                "operation": "save_run",
                "run_id": run.run_id,
                "correlation_id": run.correlation_id,
                "outcome": "success",
            },
        )

    async def get_run(self, run_id: str) -> ConsensusRun | None:
        return self.get_run_sync(run_id)

    def get_run_sync(self, run_id: str) -> ConsensusRun | None:
        return self._runs.get(run_id)

    async def list_runs(
        self, organization_id: Any = None, *, limit: int = 50
    ) -> list[ConsensusRun]:
        runs = list(self._runs.values())
        if organization_id is not None:
            org_str = str(organization_id)
            runs = [
                r
                for r in runs
                if r.organization_id is not None and str(r.organization_id) == org_str
            ]
        runs.sort(key=lambda r: r.created_at, reverse=True)
        return runs[: max(0, int(limit))]

    def get_replay_snapshot(self, run_id: str) -> dict[str, Any] | None:
        snap = self._replay.get(run_id)
        return copy.deepcopy(snap) if snap is not None else None

    @staticmethod
    def _snapshot(run: ConsensusRun) -> dict[str, Any]:
        """Developer replay payload — mirrors to_report plus merged text hash keys."""
        report = run.to_report()
        report["final_text"] = run.final_text
        report["replay"] = {
            "panel": list(run.panel),
            "candidate_ids": [c.candidate_id for c in run.candidates],
            "anonymous_ids": [c.anonymous_id for c in run.candidates],
            "section_sources": dict(run.merge.section_sources) if run.merge else {},
            "total_cost": run.total_cost,
            "total_latency_ms": run.total_latency_ms,
            "status": run.status,
        }
        return report
