"""Workflow Engine unit tests — definition, execution, retry, fallback, conditions, events."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import pytest

from app.infrastructure.events.in_process_bus import InProcessEventBus
from app.modules.workflow.application.builtin_handlers import register_builtin_handlers
from app.modules.workflow.application.conditions import DefaultConditionEvaluator
from app.modules.workflow.application.engine import DefaultWorkflowEngine
from app.modules.workflow.application.factory import WorkflowFactory
from app.modules.workflow.application.retry import compute_delay_ms
from app.modules.workflow.application.validator import DefaultWorkflowValidator
from app.modules.workflow.domain.models import (
    ConditionType,
    FallbackPolicy,
    FallbackStrategy,
    NodeCondition,
    NodeOutcome,
    RetryPolicy,
    RetryStrategy,
    WorkflowContext,
    WorkflowDefinition,
    WorkflowNode,
)
from app.modules.workflow.infrastructure.history_memory import InMemoryExecutionHistoryStore
from app.modules.workflow.infrastructure.metrics_memory import InMemoryWorkflowMetrics
from app.modules.workflow.infrastructure.node_registry import InMemoryNodeRegistry
from app.modules.workflow.infrastructure.registry import InMemoryWorkflowRegistry
from app.modules.workflow.infrastructure.yaml_loader import YamlWorkflowLoader
from app.shared.result import Failure, Success

WORKFLOWS_DIR = Path(__file__).resolve().parents[2] / "configs" / "workflows"


def _ctx(**kwargs) -> WorkflowContext:
    return WorkflowContext(
        correlation_id=kwargs.pop("correlation_id", "corr-test"),
        organization_id=kwargs.pop("organization_id", uuid.uuid4()),
        **kwargs,
    )


def _engine(definition: WorkflowDefinition | None = None, bus: InProcessEventBus | None = None):
    bus = bus or InProcessEventBus()
    wreg = InMemoryWorkflowRegistry()
    nreg = InMemoryNodeRegistry()
    register_builtin_handlers(nreg)
    if definition:
        wreg.register(definition)
    metrics = InMemoryWorkflowMetrics()
    history = InMemoryExecutionHistoryStore()
    engine = DefaultWorkflowEngine(
        workflow_registry=wreg,
        node_registry=nreg,
        event_bus=bus,
        metrics=metrics,
        history=history,
    )
    return engine, wreg, nreg, bus, metrics, history


def test_yaml_loader_parses_content_pipeline() -> None:
    loader = YamlWorkflowLoader()
    definition = loader.load_path(WORKFLOWS_DIR / "content_pipeline.yaml")
    assert definition.name == "content_pipeline"
    assert definition.entry_node_id == "normalize"
    assert len(definition.nodes) >= 5


def test_factory_loads_all_workflow_yamls() -> None:
    engine, wreg, nreg = WorkflowFactory.create(workflows_dir=WORKFLOWS_DIR)
    names = set(wreg.list_names())
    assert {
        "news_ingestion",
        "content_generation",
        "image_generation",
        "carousel_generation",
        "learning",
        "content_pipeline",
    }.issubset(names)
    assert "noop" in nreg.known_types()


def test_validator_duplicate_ids() -> None:
    definition = WorkflowDefinition(
        name="bad",
        version="1",
        entry_node_id="a",
        nodes=(
            WorkflowNode(id="a", name="A", type="noop", terminal=True),
            WorkflowNode(id="a", name="A2", type="noop", terminal=True),
        ),
    )
    result = DefaultWorkflowValidator().validate(definition, {"noop"})
    assert isinstance(result, Failure)
    assert result.code == "DUPLICATE_NODE_ID"


def test_validator_unknown_type() -> None:
    definition = WorkflowDefinition(
        name="bad",
        version="1",
        entry_node_id="a",
        nodes=(WorkflowNode(id="a", name="A", type="llm.write", terminal=True),),
    )
    result = DefaultWorkflowValidator().validate(definition, {"noop"})
    assert isinstance(result, Failure)
    assert result.code == "UNKNOWN_NODE_TYPE"


def test_validator_cycle() -> None:
    definition = WorkflowDefinition(
        name="cycle",
        version="1",
        entry_node_id="a",
        nodes=(
            WorkflowNode(
                id="a",
                name="A",
                type="noop",
                conditions=(NodeCondition(ConditionType.ALWAYS, "b"),),
            ),
            WorkflowNode(
                id="b",
                name="B",
                type="noop",
                conditions=(NodeCondition(ConditionType.ALWAYS, "a"),),
            ),
        ),
    )
    result = DefaultWorkflowValidator().validate(definition, {"noop"})
    assert isinstance(result, Failure)
    assert result.code == "CYCLE_DETECTED"


def test_validator_ok() -> None:
    definition = WorkflowDefinition(
        name="ok",
        version="1",
        entry_node_id="a",
        nodes=(WorkflowNode(id="a", name="A", type="noop", terminal=True),),
    )
    result = DefaultWorkflowValidator().validate(definition, {"noop"})
    assert isinstance(result, Success)


def test_execution_happy_path() -> None:
    definition = WorkflowDefinition(
        name="happy",
        version="1.0",
        entry_node_id="start",
        nodes=(
            WorkflowNode(
                id="start",
                name="Start",
                type="set_context",
                config={"set": {"flag": True}},
                conditions=(NodeCondition(ConditionType.ALWAYS, "end"),),
            ),
            WorkflowNode(id="end", name="End", type="noop", terminal=True),
        ),
    )
    engine, *_ = _engine(definition)
    result = asyncio.run(engine.run("happy", initial_context=_ctx()))
    assert result.success
    assert result.context.get("flag") is True
    assert result.metrics_summary.get("outcome") == "success"


def test_retry_fixed_delay_eventually_succeeds() -> None:
    class Flaky:
        def __init__(self) -> None:
            self.calls = 0

        async def execute(self, node, context) -> NodeOutcome:
            self.calls += 1
            if self.calls < 3:
                return NodeOutcome(success=False, error_message="transient")
            return NodeOutcome(success=True, outputs={"ok": True})

    definition = WorkflowDefinition(
        name="retry_demo",
        version="1",
        entry_node_id="flaky",
        nodes=(
            WorkflowNode(
                id="flaky",
                name="Flaky",
                type="flaky",
                retry=RetryPolicy(
                    strategy=RetryStrategy.FIXED_DELAY,
                    max_attempts=3,
                    delay_ms=1,
                ),
                terminal=True,
            ),
        ),
    )
    engine, _, nreg, *_ = _engine(definition)
    flaky = Flaky()
    nreg.register("flaky", flaky)
    result = asyncio.run(engine.run("retry_demo", initial_context=_ctx()))
    assert result.success
    assert flaky.calls == 3
    assert result.metrics_summary["retries_total"] == 2


def test_retry_exponential_delay_math() -> None:
    policy = RetryPolicy(
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        max_attempts=5,
        delay_ms=10,
        max_delay_ms=50,
    )
    assert compute_delay_ms(policy, 1) == 10
    assert compute_delay_ms(policy, 2) == 20
    assert compute_delay_ms(policy, 3) == 40
    assert compute_delay_ms(policy, 4) == 50  # capped


def test_fallback_stop() -> None:
    definition = WorkflowDefinition(
        name="fb_stop",
        version="1",
        entry_node_id="boom",
        nodes=(
            WorkflowNode(
                id="boom",
                name="Boom",
                type="fail",
                config={"message": "nope"},
                retry=RetryPolicy(strategy=RetryStrategy.NONE, max_attempts=1),
                fallback=FallbackPolicy(strategy=FallbackStrategy.STOP),
                terminal=True,
            ),
        ),
    )
    engine, *_ = _engine(definition)
    result = asyncio.run(engine.run("fb_stop", initial_context=_ctx()))
    assert not result.success
    assert result.error_code == "NODE_FAILED"


def test_fallback_skip() -> None:
    definition = WorkflowDefinition(
        name="fb_skip",
        version="1",
        entry_node_id="boom",
        nodes=(
            WorkflowNode(
                id="boom",
                name="Boom",
                type="fail",
                retry=RetryPolicy(max_attempts=1),
                fallback=FallbackPolicy(strategy=FallbackStrategy.SKIP),
                conditions=(NodeCondition(ConditionType.ALWAYS, "done"),),
            ),
            WorkflowNode(id="done", name="Done", type="noop", terminal=True),
        ),
    )
    engine, *_ = _engine(definition)
    result = asyncio.run(engine.run("fb_skip", initial_context=_ctx()))
    assert result.success


def test_fallback_alternative_node() -> None:
    definition = WorkflowDefinition(
        name="fb_alt",
        version="1",
        entry_node_id="boom",
        nodes=(
            WorkflowNode(
                id="boom",
                name="Boom",
                type="fail",
                retry=RetryPolicy(max_attempts=1),
                fallback=FallbackPolicy(
                    strategy=FallbackStrategy.ALTERNATIVE_NODE,
                    alternative_node_id="rescue",
                ),
            ),
            WorkflowNode(
                id="rescue",
                name="Rescue",
                type="set_context",
                config={"set": {"rescued": True}},
                terminal=True,
            ),
        ),
    )
    engine, *_ = _engine(definition)
    result = asyncio.run(engine.run("fb_alt", initial_context=_ctx()))
    assert result.success
    assert result.context.get("rescued") is True


def test_condition_expression() -> None:
    evaluator = DefaultConditionEvaluator()
    ctx = _ctx()
    ctx.set("score", 4)
    cond = NodeCondition(
        type=ConditionType.EXPRESSION,
        target_node_id="x",
        expression="data.score >= 3",
    )
    assert evaluator.matches(cond, ctx, last_success=True) is True
    ctx.set("score", 2)
    assert evaluator.matches(cond, ctx, last_success=True) is False


def test_content_pipeline_expression_branch() -> None:
    engine, wreg, _ = WorkflowFactory.create(workflows_dir=WORKFLOWS_DIR)
    # Override bus isolation: factory uses global bus; still OK for success path
    result = asyncio.run(
        engine.run("content_pipeline", initial_context=_ctx())
    )
    assert result.success
    assert result.context.get("stage") == "draft"


def test_events_published() -> None:
    definition = WorkflowDefinition(
        name="events_demo",
        version="1",
        entry_node_id="a",
        nodes=(WorkflowNode(id="a", name="A", type="noop", terminal=True),),
    )
    bus = InProcessEventBus()
    seen: list[str] = []

    async def capture(event) -> None:
        seen.append(event.event_type)

    for t in (
        "WorkflowStarted",
        "NodeStarted",
        "NodeCompleted",
        "WorkflowCompleted",
    ):
        bus.subscribe(t, capture)

    engine, *_rest = _engine(definition, bus=bus)
    result = asyncio.run(engine.run("events_demo", initial_context=_ctx()))
    assert result.success
    assert "WorkflowStarted" in seen
    assert "NodeStarted" in seen
    assert "NodeCompleted" in seen
    assert "WorkflowCompleted" in seen


def test_engine_is_domain_agnostic() -> None:
    """Core engine modules must not import business domains (factory may register handlers)."""
    import ast
    from pathlib import Path

    engine_root = Path(__file__).resolve().parents[2] / "app" / "modules" / "workflow"
    forbidden = ("news", "content", "image", "carousel", "review", "learning")
    # Composition root may register domain handlers without embedding business logic.
    allow_files = {"factory.py"}
    offenders: list[str] = []
    for path in engine_root.rglob("*.py"):
        if path.name in allow_files:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                mod = node.module
                if any(f"modules.{f}" in mod for f in forbidden):
                    offenders.append(f"{path.name}:{mod}")
    assert offenders == []
