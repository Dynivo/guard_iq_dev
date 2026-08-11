"""In-memory workflow metrics sink (no Prometheus)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class _ExecutionMetrics:
    workflow_name: str = ""
    started: bool = False
    finished_outcome: str | None = None
    total_duration_ms: int = 0
    nodes: list[dict] = field(default_factory=list)
    queue_wait_ms: int = 0  # reserved for M8


class InMemoryWorkflowMetrics:
    def __init__(self) -> None:
        self._by_execution: dict[str, _ExecutionMetrics] = {}

    def record_workflow_started(self, execution_id: str, workflow_name: str) -> None:
        self._by_execution[execution_id] = _ExecutionMetrics(
            workflow_name=workflow_name, started=True
        )

    def record_node_timing(
        self,
        execution_id: str,
        node_id: str,
        duration_ms: int,
        retries: int,
        outcome: str,
    ) -> None:
        metrics = self._by_execution.setdefault(execution_id, _ExecutionMetrics())
        metrics.nodes.append(
            {
                "node_id": node_id,
                "duration_ms": duration_ms,
                "retries": retries,
                "outcome": outcome,
            }
        )

    def record_workflow_finished(
        self,
        execution_id: str,
        outcome: str,
        duration_ms: int,
    ) -> None:
        metrics = self._by_execution.setdefault(execution_id, _ExecutionMetrics())
        metrics.finished_outcome = outcome
        metrics.total_duration_ms = duration_ms

    def summary(self, execution_id: str) -> dict:
        metrics = self._by_execution.get(execution_id)
        if metrics is None:
            return {}
        return {
            "workflow_name": metrics.workflow_name,
            "outcome": metrics.finished_outcome,
            "total_duration_ms": metrics.total_duration_ms,
            "queue_wait_ms": metrics.queue_wait_ms,
            "node_count": len(metrics.nodes),
            "retries_total": sum(n["retries"] for n in metrics.nodes),
            "failures": sum(1 for n in metrics.nodes if n["outcome"] == "failure"),
            "nodes": list(metrics.nodes),
        }
