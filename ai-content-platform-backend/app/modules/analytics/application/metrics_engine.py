"""Metrics Engine — counters/histograms via export port."""

from __future__ import annotations

from typing import Any

from app.modules.analytics.application.config_loader import load_analytics_config
from app.modules.analytics.application.store import InMemoryMetricsExporter


class MetricsEngine:
    def __init__(
        self,
        exporter: InMemoryMetricsExporter | None = None,
        config_dir: str | None = None,
    ) -> None:
        cfg = load_analytics_config(config_dir)
        ns = ((cfg.get("metrics") or {}).get("metrics") or {}).get("namespace") or "aicp"
        self.exporter = exporter or InMemoryMetricsExporter(namespace=str(ns))

    def capture_ai(self, *, status: str, latency_ms: int, provider: str | None = None) -> None:
        labels = {"status": status}
        if provider:
            labels["provider"] = provider
        self.exporter.inc("ai_requests_total", labels)
        self.exporter.observe("ai_latency_ms", float(latency_ms), labels)

    def capture_workflow(self, *, outcome: str, duration_ms: int, workflow: str) -> None:
        labels = {"outcome": outcome, "workflow": workflow}
        self.exporter.inc("workflow_nodes_total", labels)
        self.exporter.observe("workflow_node_duration_ms", float(duration_ms), labels)

    def capture_evaluation(self) -> None:
        self.exporter.inc("evaluations_total")

    def capture_provider_failure(self, provider: str) -> None:
        self.exporter.inc("provider_failures_total", {"provider": provider})

    def capture_cost(self, amount: float) -> None:
        self.exporter.observe("cost_usd", amount)

    def snapshot(self) -> dict[str, Any]:
        return self.exporter.snapshot()
