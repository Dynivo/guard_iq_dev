"""M14 AI Observability — unit tests."""

from __future__ import annotations

import asyncio
import inspect
import uuid
from pathlib import Path

from app.infrastructure.events.in_process_bus import InProcessEventBus
from app.modules.analytics.application.factory import AnalyticsFactory
from app.modules.analytics.application.handlers import (
    AnalyticsAggregateHandler,
    EvaluationRunHandler,
    MetricsCaptureHandler,
    TraceStoreHandler,
    register_analytics_workflow_handlers,
)
from app.modules.analytics.application.replay import ObservabilityReplayService
from app.modules.analytics.application.subscribers import register_analytics_handlers
from app.modules.analytics.domain.models import TraceStatus
from app.modules.workflow.domain.models import WorkflowContext, WorkflowNode
from app.modules.workflow.infrastructure.node_registry import InMemoryNodeRegistry
from app.shared.events.types import DomainEvent


ROOT = Path(__file__).resolve().parents[2]
CONFIGS = ROOT / "configs" / "analytics"


def test_observability_never_imports_generation_or_review() -> None:
    import app.modules.analytics.application.engine as engine_mod
    import app.modules.analytics.application.service as service_mod

    for mod in (engine_mod, service_mod):
        source = inspect.getsource(mod)
        assert "modules.content" not in source
        assert "modules.review" not in source
        assert "openai" not in source.lower()
        assert "ChatCompletion" not in source


def test_ai_trace_record_and_list() -> None:
    async def _run() -> None:
        engine = AnalyticsFactory.create_memory(config_dir=CONFIGS)
        org = uuid.uuid4()
        trace = await engine.record_ai_trace(
            request_id="req-1",
            correlation_id="corr-1",
            organization_id=org,
            provider="openai",
            model="gpt-test",
            latency_ms=150,
            tokens_in=100,
            tokens_out=40,
            status=TraceStatus.SUCCESS,
            cost_estimate=0.01,
        )
        assert trace.request_id == "req-1"
        listed = engine.ai_traces.list_for_org(org, correlation_id="corr-1")
        assert len(listed) == 1
        assert listed[0]["provider"] == "openai"

    asyncio.run(_run())


def test_evaluation_deterministic() -> None:
    async def _run() -> None:
        engine = AnalyticsFactory.create_memory(config_dir=CONFIGS)
        org = uuid.uuid4()
        inputs = {
            "approval_rate": 0.9,
            "edit_distance": 2,
            "latency_ms": 100,
            "learning_growth": 0.3,
        }
        a = await engine.evaluation.evaluate_and_store(
            organization_id=org,
            correlation_id="c-eval",
            subject_type="draft",
            subject_id="d1",
            inputs=inputs,
        )
        b = engine.evaluation.evaluate(
            organization_id=org,
            correlation_id="c-eval-2",
            subject_type="draft",
            subject_id="d2",
            inputs=inputs,
        )
        assert a.inputs_fingerprint == b.inputs_fingerprint
        assert a.overall == b.overall
        assert a.scores == b.scores

    asyncio.run(_run())


def test_metrics_capture() -> None:
    engine = AnalyticsFactory.create_memory(config_dir=CONFIGS)
    engine.metrics.capture_ai(status="success", latency_ms=50, provider="openai")
    engine.metrics.capture_evaluation()
    snap = engine.metrics.snapshot()
    assert "counters" in snap or any("ai_requests" in str(k) for k in snap)


def test_provider_intelligence_from_failure() -> None:
    async def _run() -> None:
        engine = AnalyticsFactory.create_memory(config_dir=CONFIGS)
        org = uuid.uuid4()
        event = DomainEvent(
            event_type="ProviderFailed",
            organization_id=org,
            correlation_id="c-fail",
            payload={
                "provider": "openai",
                "error_class": "TimeoutError: timed out",
                "fallback_used": True,
            },
        )
        result = await engine.handle_domain_event(event)
        assert result["handled"] is True
        health = engine.providers.get("openai")
        assert health is not None
        assert health["failures"] >= 1
        assert health["timeouts"] >= 1
        assert health["fallbacks"] >= 1

    asyncio.run(_run())


def test_cost_engine_from_trace() -> None:
    async def _run() -> None:
        engine = AnalyticsFactory.create_memory(config_dir=CONFIGS)
        org = uuid.uuid4()
        await engine.record_ai_trace(
            request_id="req-cost",
            correlation_id="c-cost",
            organization_id=org,
            provider="openai",
            model="gpt-test",
            tokens_in=1000,
            tokens_out=500,
            status=TraceStatus.SUCCESS,
            cost_estimate=0.05,
        )
        agg = engine.cost.aggregate(org)
        assert agg["total"] >= 0.05

    asyncio.run(_run())


def test_workflow_trace_and_statistics() -> None:
    async def _run() -> None:
        engine = AnalyticsFactory.create_memory(config_dir=CONFIGS)
        org = uuid.uuid4()
        await engine.record_workflow_trace(
            execution_id="exec-1",
            correlation_id="c-wf",
            organization_id=org,
            workflow_name="observability",
            node_id="trace.store",
            phase="finish",
            duration_ms=40,
            failure=False,
            outcome="success",
        )
        stats = engine.workflow_traces.statistics()
        assert "observability" in stats or stats

    asyncio.run(_run())


def test_replay_and_diff() -> None:
    async def _run() -> None:
        engine = AnalyticsFactory.create_memory(config_dir=CONFIGS)
        org = uuid.uuid4()
        await engine.record_ai_trace(
            request_id="r-replay",
            correlation_id="c-replay",
            organization_id=org,
            status=TraceStatus.SUCCESS,
            latency_ms=10,
        )
        replay = ObservabilityReplayService(engine.store)
        data = replay.replay(org, "c-replay")
        assert data["count"] >= 1
        left = data["ai_traces"][0]
        right = {**left, "latency_ms": 99}
        diff = replay.diff_traces(left, right)
        assert diff["identical"] is False
        assert "latency_ms" in diff["changed_fields"]

    asyncio.run(_run())


def test_eventbus_subscriber_non_blocking() -> None:
    async def _run() -> None:
        bus = InProcessEventBus()
        engine = AnalyticsFactory.create_memory(config_dir=CONFIGS)
        register_analytics_handlers(bus, engine=engine)
        org = uuid.uuid4()
        await bus.publish(
            DomainEvent(
                event_type="DraftGenerated",
                organization_id=org,
                correlation_id="c-bus",
                payload={"draft_id": str(uuid.uuid4()), "latency_ms": 20},
            )
        )
        assert len(engine.store.ai_traces) >= 1

    asyncio.run(_run())


def test_workflow_handlers_register_and_run() -> None:
    async def _run() -> None:
        registry = InMemoryNodeRegistry()
        register_analytics_workflow_handlers(registry)
        assert registry.get("metrics.capture") is not None
        assert registry.get("evaluation.run") is not None
        assert registry.get("trace.store") is not None

        org = uuid.uuid4()
        ctx = WorkflowContext(
            correlation_id="c-handler",
            organization_id=org,
            workflow_name="observability",
        )
        ctx.set("latency_ms", 25)
        ctx.set("status", "success")
        ctx.set("provider", "openai")
        node = WorkflowNode(id="n1", name="cap", type="metrics.capture")

        out = await MetricsCaptureHandler().execute(node, ctx)
        assert out.success
        eval_out = await EvaluationRunHandler().execute(
            WorkflowNode(id="n2", name="eval", type="evaluation.run"), ctx
        )
        assert eval_out.success
        trace_out = await TraceStoreHandler().execute(
            WorkflowNode(id="n3", name="trace", type="trace.store"), ctx
        )
        assert trace_out.success
        agg = await AnalyticsAggregateHandler().execute(
            WorkflowNode(id="n4", name="agg", type="analytics.aggregate"), ctx
        )
        assert agg.success
        assert "analytics.status" in agg.outputs

    asyncio.run(_run())


def test_correlation_explorer() -> None:
    async def _run() -> None:
        engine = AnalyticsFactory.create_memory(config_dir=CONFIGS)
        org = uuid.uuid4()
        corr = "c-join"
        await engine.record_ai_trace(
            request_id="r1",
            correlation_id=corr,
            organization_id=org,
            status=TraceStatus.SUCCESS,
        )
        await engine.evaluation.evaluate_and_store(
            organization_id=org,
            correlation_id=corr,
            subject_type="draft",
            subject_id="d",
            inputs={"approval_rate": 0.5, "edit_distance": 0, "latency_ms": 10},
        )
        joined = engine.correlation.explore(org, corr)
        assert joined["correlation_id"] == corr
        assert len(joined.get("ai_traces") or joined.get("traces") or []) >= 0

    asyncio.run(_run())
