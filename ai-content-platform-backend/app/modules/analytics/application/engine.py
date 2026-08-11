"""ObservabilityEngine facade — measure only; never mutate AI artifacts."""

from __future__ import annotations

import uuid
from typing import Any

from app.modules.analytics.application.ai_trace import AITraceEngine
from app.modules.analytics.application.cache import ObservabilityCache
from app.modules.analytics.application.correlation import CorrelationEngine
from app.modules.analytics.application.cost_engine import CostEngine
from app.modules.analytics.application.evaluation import EvaluationEngine
from app.modules.analytics.application.failure_analysis import FailureAnalysis
from app.modules.analytics.application.insights import InsightsEngine
from app.modules.analytics.application.metrics_engine import MetricsEngine
from app.modules.analytics.application.model_intelligence import ModelIntelligence
from app.modules.analytics.application.provider_intelligence import ProviderIntelligence
from app.modules.analytics.application.store import InMemoryObservabilityStore
from app.modules.analytics.application.workflow_trace import WorkflowTraceEngine
from app.modules.analytics.domain.models import AITrace, TraceStatus, WorkflowTrace
from app.shared.events.types import DomainEvent


class ObservabilityEngine:
    def __init__(
        self,
        *,
        store: InMemoryObservabilityStore | None = None,
        config_dir: str | None = None,
    ) -> None:
        self.store = store or InMemoryObservabilityStore()
        self.ai_traces = AITraceEngine(self.store)
        self.workflow_traces = WorkflowTraceEngine(self.store)
        self.evaluation = EvaluationEngine(self.store, config_dir)
        self.providers = ProviderIntelligence()
        self.models = ModelIntelligence()
        self.cost = CostEngine(self.store, config_dir=config_dir)
        self.metrics = MetricsEngine(config_dir=config_dir)
        self.correlation = CorrelationEngine(self.store)
        self.failures = FailureAnalysis()
        self.insights = InsightsEngine(self.store)
        self.cache = ObservabilityCache()

    async def handle_domain_event(self, event: DomainEvent) -> dict[str, Any]:
        """Non-blocking sink for EventBus — never mutates generation/review."""
        result: dict[str, Any] = {"event_type": event.event_type, "handled": True}

        if event.event_type == "ProviderFailed":
            self.failures.classify(event)
            health = self.providers.observe_failure(event)
            self.metrics.capture_provider_failure(health.provider)
            trace = await self.ai_traces.from_domain_event(event)
            result["ai_trace"] = trace.to_dict()
            return result

        if event.event_type.startswith("Workflow") or event.event_type.startswith("Node"):
            wf = await self.workflow_traces.from_domain_event(event)
            if wf:
                self.metrics.capture_workflow(
                    outcome=wf.outcome or ("failure" if wf.failure else "success"),
                    duration_ms=wf.duration_ms,
                    workflow=wf.workflow_name,
                )
                result["workflow_trace"] = wf.to_dict()
            return result

        # Lifecycle / generation events → AI-ish traces + optional cost
        lifecycle = {
            "DraftGenerated",
            "DraftApproved",
            "DraftRejected",
            "DraftEdited",
            "ImageGenerated",
            "CarouselGenerated",
            "ArticleImported",
            "PromptEvaluated",
        }
        if event.event_type in lifecycle:
            payload = dict(event.payload or {})
            if event.event_type == "ImageGenerated":
                await self.cost.record_category(
                    event.organization_id,
                    "image",
                    correlation_id=event.correlation_id,
                )
            if event.event_type == "CarouselGenerated":
                await self.cost.record_category(
                    event.organization_id,
                    "render",
                    correlation_id=event.correlation_id,
                )
            # Build evaluation inputs from review outcomes when available
            if event.event_type in {"DraftApproved", "DraftRejected", "DraftEdited"}:
                approvals = sum(
                    1
                    for t in self.store.ai_traces
                    if t.organization_id == event.organization_id
                    and t.event_type == "DraftApproved"
                )
                rejects = sum(
                    1
                    for t in self.store.ai_traces
                    if t.organization_id == event.organization_id
                    and t.event_type == "DraftRejected"
                )
                # Include current event in rates after we record
                if event.event_type == "DraftApproved":
                    approvals += 1
                if event.event_type == "DraftRejected":
                    rejects += 1
                total = approvals + rejects
                approval_rate = approvals / total if total else 0.0
                orig = payload.get("original_text") or ""
                edited = payload.get("edited_text") or ""
                edit_distance = abs(len(edited) - len(orig))
                eval_result = await self.evaluation.evaluate_and_store(
                    organization_id=event.organization_id,
                    correlation_id=event.correlation_id,
                    subject_type="draft",
                    subject_id=str(payload.get("draft_id") or "unknown"),
                    inputs={
                        "approval_rate": approval_rate,
                        "edit_distance": edit_distance,
                        "latency_ms": int(payload.get("latency_ms") or 0),
                        "learning_growth": float(payload.get("learning_growth") or 0.1),
                        "visual_quality": float(payload.get("visual_quality") or 0.5),
                        "typography_quality": float(payload.get("typography_quality") or 0.5),
                        "carousel_quality": float(payload.get("carousel_quality") or 0.5),
                    },
                )
                self.metrics.capture_evaluation()
                self.insights.from_evaluation(eval_result)
                result["evaluation"] = eval_result.to_dict()

            trace = await self.ai_traces.from_domain_event(event)
            self.providers.observe_trace(trace)
            self.models.observe_trace(trace)
            self.metrics.capture_ai(
                status=str(trace.status),
                latency_ms=trace.latency_ms,
                provider=trace.provider,
            )
            cost = await self.cost.record_from_trace(trace)
            if cost:
                self.metrics.capture_cost(cost.amount_usd)
                result["cost"] = cost.to_dict()
            result["ai_trace"] = trace.to_dict()
            return result

        # Unknown events still get a minimal AI trace for observability coverage
        trace = await self.ai_traces.from_domain_event(event)
        result["ai_trace"] = trace.to_dict()
        return result

    async def record_ai_trace(self, **kwargs: Any) -> AITrace:
        status = kwargs.pop("status", TraceStatus.SUCCESS)
        if isinstance(status, str):
            status = TraceStatus(status)
        trace = AITrace(status=status, **kwargs)
        recorded = await self.ai_traces.record(trace)
        self.providers.observe_trace(recorded)
        self.models.observe_trace(recorded)
        self.metrics.capture_ai(
            status=str(recorded.status),
            latency_ms=recorded.latency_ms,
            provider=recorded.provider,
        )
        await self.cost.record_from_trace(recorded)
        return recorded

    async def record_workflow_trace(self, **kwargs: Any) -> WorkflowTrace:
        trace = WorkflowTrace(**kwargs)
        return await self.workflow_traces.record(trace)

    def status(self) -> dict[str, Any]:
        return {
            **self.store.status(),
            "metrics": self.metrics.snapshot(),
            "providers": self.providers.list_health(),
            "models": self.models.list_health(),
            "failures": self.failures.summary(),
        }
