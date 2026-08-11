"""Workflow handlers for observability nodes."""

from __future__ import annotations

import uuid
from typing import Any

from app.modules.analytics.application.factory import AnalyticsFactory
from app.modules.analytics.domain.models import TraceStatus
from app.modules.workflow.domain.models import NodeOutcome, WorkflowContext, WorkflowNode


def _engine_from_context(context: WorkflowContext):
    engine = context.get("_analytics_engine")
    if engine is None:
        engine = AnalyticsFactory.create_memory()
        context.set("_analytics_engine", engine)
    return engine


def _uuid(value: Any) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _org_id(context: WorkflowContext) -> uuid.UUID:
    raw = context.organization_id or context.get("organization_id")
    return _uuid(raw) if raw else uuid.uuid4()


class MetricsCaptureHandler:
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        engine = _engine_from_context(context)
        status = str(context.get("status") or "success")
        latency = int(context.get("latency_ms") or 0)
        provider = context.get("provider")
        engine.metrics.capture_ai(status=status, latency_ms=latency, provider=provider)
        payload = {"metrics.captured": True, "metrics.snapshot": engine.metrics.snapshot()}
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class MetricsAggregateHandler:
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        engine = _engine_from_context(context)
        snap = engine.metrics.snapshot()
        org = context.organization_id or context.get("organization_id")
        cost = engine.cost.aggregate(_uuid(org) if org else None)
        payload = {"metrics.aggregate": snap, "cost.aggregate": cost}
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class EvaluationRunHandler:
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        engine = _engine_from_context(context)
        org = _org_id(context)
        result = await engine.evaluation.evaluate_and_store(
            organization_id=org,
            correlation_id=str(context.correlation_id or "wf-eval"),
            subject_type=str(context.get("subject_type") or "workflow"),
            subject_id=str(context.get("subject_id") or context.execution_id),
            inputs=dict(context.get("evaluation_inputs") or {
                "approval_rate": float(context.get("approval_rate") or 0.5),
                "edit_distance": float(context.get("edit_distance") or 0),
                "latency_ms": float(context.get("latency_ms") or 100),
                "learning_growth": float(context.get("learning_growth") or 0.2),
            }),
        )
        engine.metrics.capture_evaluation()
        engine.insights.from_evaluation(result)
        payload = {"evaluation.result": result.to_dict()}
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class TraceStoreHandler:
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        engine = _engine_from_context(context)
        org = _org_id(context)
        trace = await engine.record_ai_trace(
            request_id=str(context.get("request_id") or uuid.uuid4()),
            correlation_id=str(context.correlation_id or "wf-trace"),
            organization_id=org,
            workflow_id=str(context.get("workflow_id") or context.workflow_name),
            provider=context.get("provider"),
            model=context.get("model"),
            capability=context.get("capability"),
            latency_ms=int(context.get("latency_ms") or 0),
            tokens_in=int(context.get("tokens_in") or 0),
            tokens_out=int(context.get("tokens_out") or 0),
            cache_hit=bool(context.get("cache_hit") or False),
            retry_count=int(context.get("retry_count") or 0),
            status=TraceStatus(str(context.get("status") or "success")),
            event_type=str(context.get("event_type") or "WorkflowTrace"),
            cost_estimate=float(context.get("cost_estimate") or 0.0),
        )
        wf = await engine.record_workflow_trace(
            execution_id=str(context.execution_id),
            correlation_id=str(context.correlation_id or "wf-trace"),
            organization_id=org,
            workflow_name=str(context.workflow_name or "observability"),
            node_id="trace.store",
            phase="finish",
            duration_ms=int(context.get("latency_ms") or 0),
            failure=False,
            outcome="success",
        )
        payload = {"trace.ai": trace.to_dict(), "trace.workflow": wf.to_dict()}
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class AnalyticsAggregateHandler:
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        engine = _engine_from_context(context)
        status = engine.status()
        payload = {"analytics.status": status}
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


def register_analytics_workflow_handlers(node_registry) -> None:
    node_registry.register("metrics.capture", MetricsCaptureHandler())
    node_registry.register("metrics.aggregate", MetricsAggregateHandler())
    node_registry.register("evaluation.run", EvaluationRunHandler())
    node_registry.register("trace.store", TraceStoreHandler())
    node_registry.register("analytics.aggregate", AnalyticsAggregateHandler())
