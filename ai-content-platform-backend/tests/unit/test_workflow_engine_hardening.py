"""Workflow Engine architectural hardening — unit tests."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import pytest

from app.infrastructure.events.in_process_bus import InProcessEventBus
from app.modules.workflow.application.builtin_handlers import register_builtin_handlers
from app.modules.workflow.application.engine import DefaultWorkflowEngine
from app.modules.workflow.application.factory import WorkflowFactory
from app.modules.workflow.application.middleware import LoggingMiddleware, MiddlewareChain
from app.modules.workflow.application.node_executor import RegistryNodeExecutor
from app.modules.workflow.application.validator import DefaultWorkflowValidator
from app.modules.workflow.domain.models import (
    CancelToken,
    ConditionType,
    NodeCategory,
    NodeCondition,
    NodeOutcome,
    SimulationOptions,
    WorkflowContext,
    WorkflowDefinition,
    WorkflowNode,
    WorkflowStatus,
)
from app.modules.workflow.infrastructure.history_db import NullExecutionHistoryStore
from app.modules.workflow.infrastructure.history_memory import InMemoryExecutionHistoryStore
from app.modules.workflow.infrastructure.metrics_memory import InMemoryWorkflowMetrics
from app.modules.workflow.infrastructure.node_registry import InMemoryNodeRegistry
from app.modules.workflow.infrastructure.registry import (
    CachedWorkflowRegistry,
    InMemoryWorkflowRegistry,
)
from app.modules.workflow.infrastructure.yaml_loader import YamlWorkflowLoader
from app.shared.result import Failure

WORKFLOWS_DIR = Path(__file__).resolve().parents[2] / "configs" / "workflows"


def _ctx(**kwargs) -> WorkflowContext:
    return WorkflowContext(
        correlation_id=kwargs.pop("correlation_id", "corr-harden"),
        organization_id=kwargs.pop("organization_id", uuid.uuid4()),
        **kwargs,
    )


def _engine(definition: WorkflowDefinition | None = None, **kwargs):
    bus = kwargs.pop("bus", None) or InProcessEventBus()
    wreg = InMemoryWorkflowRegistry()
    nreg = InMemoryNodeRegistry()
    register_builtin_handlers(nreg)
    if definition:
        wreg.register(definition)
    engine = DefaultWorkflowEngine(
        workflow_registry=wreg,
        node_registry=nreg,
        event_bus=bus,
        metrics=InMemoryWorkflowMetrics(),
        history=InMemoryExecutionHistoryStore(),
        **kwargs,
    )
    return engine, wreg, nreg, bus


def test_versioning_metadata_defaults_and_active_preference() -> None:
    wreg = InMemoryWorkflowRegistry()
    draft = WorkflowDefinition(
        name="meta",
        version="1.0",
        entry_node_id="a",
        nodes=(WorkflowNode(id="a", name="A", type="noop", terminal=True),),
        status=WorkflowStatus.DRAFT,
        author="tester",
    )
    active = WorkflowDefinition(
        name="meta",
        version="2.0",
        entry_node_id="a",
        nodes=(WorkflowNode(id="a", name="A", type="noop", terminal=True),),
        status=WorkflowStatus.ACTIVE,
        author="tester",
    )
    wreg.register(draft)
    wreg.register(active)
    got = wreg.get("meta")
    assert got.version == "2.0"
    assert got.status == WorkflowStatus.ACTIVE
    assert got.author == "tester"
    assert got.compatible_engine_version == "1"


def test_scoped_context_aliases_data_and_shared() -> None:
    ctx = _ctx()
    ctx.set("x", 1)
    assert ctx.data["x"] == 1
    assert ctx.shared["x"] == 1
    assert ctx.data is ctx.shared
    ctx.set_node_local("tmp", True)
    assert ctx.node["tmp"] is True
    ctx.clear_node_scope()
    assert ctx.node == {}
    assert ctx.get("x") == 1


def test_cancel_token_stops_workflow() -> None:
    token = CancelToken()

    class SlowThenCancel:
        async def execute(self, node, context) -> NodeOutcome:
            token.cancel("stop-now")
            return NodeOutcome(success=True)

    definition = WorkflowDefinition(
        name="cancel_demo",
        version="1",
        entry_node_id="a",
        nodes=(
            WorkflowNode(
                id="a",
                name="A",
                type="slow",
                conditions=(NodeCondition(ConditionType.ALWAYS, "b"),),
            ),
            WorkflowNode(id="b", name="B", type="noop", terminal=True),
        ),
    )
    engine, _, nreg, bus = _engine(definition)
    nreg.register("slow", SlowThenCancel())
    seen: list[str] = []

    async def capture(event) -> None:
        seen.append(event.event_type)

    bus.subscribe("WorkflowCancelled", capture)
    result = asyncio.run(
        engine.run("cancel_demo", initial_context=_ctx(), cancel_token=token)
    )
    assert not result.success
    assert result.cancelled
    assert result.error_code == "CANCELLED"
    assert "WorkflowCancelled" in seen


def test_node_timeout_via_executor() -> None:
    class Hanging:
        async def execute(self, node, context) -> NodeOutcome:
            await asyncio.sleep(1.0)
            return NodeOutcome(success=True)

    definition = WorkflowDefinition(
        name="timeout_node",
        version="1",
        entry_node_id="hang",
        nodes=(
            WorkflowNode(
                id="hang",
                name="Hang",
                type="hang",
                timeout_ms=50,
                terminal=True,
            ),
        ),
    )
    engine, _, nreg, bus = _engine(definition)
    nreg.register("hang", Hanging())
    seen: list[str] = []

    async def capture(event) -> None:
        seen.append(event.event_type)

    bus.subscribe("NodeTimedOut", capture)
    bus.subscribe("WorkflowFailed", capture)
    result = asyncio.run(engine.run("timeout_node", initial_context=_ctx()))
    assert not result.success
    assert result.error_code == "TIMEOUT"
    assert "NodeTimedOut" in seen
    assert "WorkflowFailed" in seen


def test_workflow_timeout() -> None:
    class Slow:
        async def execute(self, node, context) -> NodeOutcome:
            await asyncio.sleep(0.2)
            return NodeOutcome(success=True)

    definition = WorkflowDefinition(
        name="wf_timeout",
        version="1",
        entry_node_id="slow",
        nodes=(WorkflowNode(id="slow", name="Slow", type="slow", terminal=True),),
        timeout_ms=50,
    )
    engine, _, nreg, bus = _engine(definition)
    nreg.register("slow", Slow())
    seen: list[str] = []

    async def capture(event) -> None:
        seen.append(event.event_type)

    bus.subscribe("WorkflowTimedOut", capture)
    result = asyncio.run(engine.run("wf_timeout", initial_context=_ctx()))
    assert not result.success
    assert result.error_code == "TIMEOUT"
    assert "WorkflowTimedOut" in seen


def test_node_category_defaults_and_yaml() -> None:
    loader = YamlWorkflowLoader()
    definition = loader.load_path(WORKFLOWS_DIR / "content_pipeline.yaml")
    by_id = {n.id: n for n in definition.nodes}
    assert by_id["normalize"].category == NodeCategory.SYSTEM.value
    assert by_id["plan"].category == "content"
    assert by_id["validate_plan"].category == "content"


def test_linter_unreachable_and_self_transition() -> None:
    validator = DefaultWorkflowValidator()
    unreachable = WorkflowDefinition(
        name="u",
        version="1",
        entry_node_id="a",
        nodes=(
            WorkflowNode(id="a", name="A", type="noop", terminal=True),
            WorkflowNode(id="orphan", name="Orphan", type="noop", terminal=True),
        ),
    )
    result = validator.validate(unreachable, {"noop"})
    assert isinstance(result, Failure)
    assert result.code == "UNREACHABLE_NODES"

    self_edge = WorkflowDefinition(
        name="self",
        version="1",
        entry_node_id="a",
        nodes=(
            WorkflowNode(
                id="a",
                name="A",
                type="noop",
                conditions=(NodeCondition(ConditionType.ALWAYS, "a"),),
            ),
        ),
    )
    result2 = validator.validate(self_edge, {"noop"})
    assert isinstance(result2, Failure)
    assert result2.code == "SELF_TRANSITION"


def test_linter_dead_nodes() -> None:
    dead = WorkflowDefinition(
        name="dead",
        version="1",
        entry_node_id="a",
        nodes=(
            WorkflowNode(
                id="a",
                name="A",
                type="noop",
                conditions=(NodeCondition(ConditionType.ALWAYS, "b"),),
            ),
            WorkflowNode(id="b", name="B", type="noop"),  # no outbound, not terminal
        ),
    )
    result = DefaultWorkflowValidator().validate(dead, {"noop"})
    assert isinstance(result, Failure)
    assert result.code == "DEAD_NODES"


def test_middleware_and_interceptor_hooks() -> None:
    hooks: list[str] = []

    class SpyMiddleware:
        async def before_workflow(self, context, workflow_name) -> None:
            hooks.append("mw.before_wf")

        async def after_workflow(self, context, result) -> None:
            hooks.append("mw.after_wf")

        async def before_node(self, context, node) -> None:
            hooks.append(f"mw.before:{node.id}")

        async def after_node(self, context, node, outcome) -> None:
            hooks.append(f"mw.after:{node.id}")

    class SpyInterceptor:
        async def before_workflow(self, context, workflow_name) -> None:
            hooks.append("ix.before_wf")

        async def after_workflow(self, context, result) -> None:
            hooks.append("ix.after_wf")

        async def before_node(self, context, node) -> None:
            hooks.append(f"ix.before:{node.id}")

        async def after_node(self, context, node, outcome) -> None:
            hooks.append(f"ix.after:{node.id}")

    definition = WorkflowDefinition(
        name="hooks",
        version="1",
        entry_node_id="a",
        nodes=(WorkflowNode(id="a", name="A", type="noop", terminal=True),),
    )
    engine, *_ = _engine(
        definition,
        middlewares=[SpyMiddleware()],
        interceptors=[SpyInterceptor()],
    )
    result = asyncio.run(engine.run("hooks", initial_context=_ctx()))
    assert result.success
    assert hooks[0] == "mw.before_wf"
    assert "mw.before:a" in hooks
    assert "ix.before:a" in hooks
    assert hooks[-1] == "ix.after_wf"


def test_simulation_mode_mocks_unknown_types() -> None:
    definition = WorkflowDefinition(
        name="sim",
        version="1",
        entry_node_id="ai",
        nodes=(
            WorkflowNode(
                id="ai",
                name="AI",
                type="llm.write",
                category=NodeCategory.AI.value,
                conditions=(NodeCondition(ConditionType.ALWAYS, "end"),),
            ),
            WorkflowNode(id="end", name="End", type="noop", terminal=True),
        ),
    )
    # Register without engine validate of unknown type: use bypass by registering
    # a known noop path via simulation only — validate needs known types.
    # Register a stub type so validation passes, simulation still short-circuits category.
    engine, _, nreg, _ = _engine()

    class ShouldNotRun:
        async def execute(self, node, context) -> NodeOutcome:
            raise AssertionError("real handler must not run in simulation")

    nreg.register("llm.write", ShouldNotRun())
    engine._workflows.register(definition)
    result = asyncio.run(
        engine.run(
            "sim",
            initial_context=_ctx(),
            simulation=SimulationOptions(
                dry_run=True,
                mock_outputs={"ai": {"draft": "mocked"}},
            ),
        )
    )
    assert result.success
    assert result.context.get("draft") == "mocked"
    assert result.context.state.get("simulation") is True


def test_cached_registry_invalidate_reload() -> None:
    nreg = InMemoryNodeRegistry()
    register_builtin_handlers(nreg)
    cached = CachedWorkflowRegistry(
        YamlWorkflowLoader(),
        WORKFLOWS_DIR,
        node_registry=nreg,
    )
    assert "content_pipeline" in cached.list_names()
    cached.invalidate("content_pipeline")
    with pytest.raises(KeyError):
        cached.get("content_pipeline")
    cached.reload()
    assert cached.get("content_pipeline").name == "content_pipeline"


def test_null_history_and_factory_injection() -> None:
    engine, wreg, nreg = WorkflowFactory.create(
        workflows_dir=WORKFLOWS_DIR,
        history=NullExecutionHistoryStore(),
    )
    assert "noop" in nreg.known_types()
    result = asyncio.run(engine.run("content_pipeline", initial_context=_ctx()))
    assert result.success


def test_registry_lint_on_register() -> None:
    nreg = InMemoryNodeRegistry()
    register_builtin_handlers(nreg)
    wreg = InMemoryWorkflowRegistry(
        known_types=nreg.known_types(),
        lint_on_register=True,
    )
    bad = WorkflowDefinition(
        name="bad",
        version="1",
        entry_node_id="a",
        nodes=(
            WorkflowNode(id="a", name="A", type="noop", terminal=True),
            WorkflowNode(id="orphan", name="O", type="noop", terminal=True),
        ),
    )
    with pytest.raises(ValueError, match="UNREACHABLE"):
        wreg.register(bad)


def test_middleware_chain_standalone() -> None:
    chain = MiddlewareChain([LoggingMiddleware()])
    assert isinstance(chain, MiddlewareChain)


def test_node_executor_passthrough() -> None:
    nreg = InMemoryNodeRegistry()
    register_builtin_handlers(nreg)
    executor = RegistryNodeExecutor(nreg)
    node = WorkflowNode(id="a", name="A", type="noop", terminal=True)
    outcome = asyncio.run(executor.execute(node, _ctx()))
    assert outcome.success
