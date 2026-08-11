"""In-memory observability store + Prometheus-compatible metrics exporter."""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any

from app.modules.analytics.domain.models import (
    AITrace,
    CostRecord,
    EvaluationResult,
    OptimizationSignal,
    WorkflowTrace,
)


class InMemoryObservabilityStore:
    def __init__(self) -> None:
        self.ai_traces: list[AITrace] = []
        self.workflow_traces: list[WorkflowTrace] = []
        self.evaluations: list[EvaluationResult] = []
        self.costs: list[CostRecord] = []
        self.signals: list[OptimizationSignal] = []
        self.org_usage: dict[str, dict[str, float]] = defaultdict(
            lambda: defaultdict(float)
        )
        self.workflow_stats: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"runs": 0, "failures": 0, "total_duration_ms": 0}
        )

    async def store_ai_trace(self, trace: AITrace) -> None:
        self.ai_traces.append(trace)

    async def store_workflow_trace(self, trace: WorkflowTrace) -> None:
        self.workflow_traces.append(trace)
        stats = self.workflow_stats[trace.workflow_name]
        if trace.phase == "finish":
            stats["runs"] += 1
            stats["total_duration_ms"] += trace.duration_ms
            if trace.failure:
                stats["failures"] += 1

    async def store_evaluation(self, result: EvaluationResult) -> None:
        self.evaluations.append(result)

    async def store_cost(self, record: CostRecord) -> None:
        self.costs.append(record)
        key = str(record.organization_id)
        self.org_usage[key][str(record.category)] += record.amount_usd
        self.org_usage[key]["total"] += record.amount_usd

    def list_ai_traces(
        self, org_id: uuid.UUID, *, correlation_id: str | None = None
    ) -> list[dict[str, Any]]:
        rows = [t for t in self.ai_traces if t.organization_id == org_id]
        if correlation_id:
            rows = [t for t in rows if t.correlation_id == correlation_id]
        return [t.to_dict() for t in rows]

    def list_workflow_traces(
        self, org_id: uuid.UUID, *, correlation_id: str | None = None
    ) -> list[dict[str, Any]]:
        rows = [t for t in self.workflow_traces if t.organization_id == org_id]
        if correlation_id:
            rows = [t for t in rows if t.correlation_id == correlation_id]
        return [t.to_dict() for t in rows]

    def status(self) -> dict[str, Any]:
        return {
            "ai_traces": len(self.ai_traces),
            "workflow_traces": len(self.workflow_traces),
            "evaluations": len(self.evaluations),
            "costs": len(self.costs),
            "signals": len(self.signals),
        }


class InMemoryMetricsExporter:
    """Prometheus-compatible counters/histograms in memory (export port)."""

    def __init__(self, namespace: str = "aicp") -> None:
        self.namespace = namespace
        self.counters: dict[str, float] = defaultdict(float)
        self.histograms: dict[str, list[float]] = defaultdict(list)

    def _key(self, name: str, labels: dict[str, str] | None) -> str:
        if not labels:
            return f"{self.namespace}_{name}"
        parts = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{self.namespace}_{name}{{{parts}}}"

    def inc(self, name: str, labels: dict[str, str] | None = None, value: float = 1.0) -> None:
        self.counters[self._key(name, labels)] += value

    def observe(
        self, name: str, value: float, labels: dict[str, str] | None = None
    ) -> None:
        self.histograms[self._key(name, labels)].append(value)

    def snapshot(self) -> dict[str, Any]:
        hist = {
            k: {
                "count": len(v),
                "sum": sum(v),
                "avg": (sum(v) / len(v)) if v else 0.0,
            }
            for k, v in self.histograms.items()
        }
        return {"counters": dict(self.counters), "histograms": hist}
