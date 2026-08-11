"""Workflow engine ports — replaceable adapters."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.modules.workflow.domain.models import (
    CancelToken,
    ExecutionHistoryRecord,
    NodeCondition,
    NodeOutcome,
    SimulationOptions,
    WorkflowContext,
    WorkflowDefinition,
    WorkflowNode,
    WorkflowResult,
)
from app.shared.result import Result


class NodeHandler(Protocol):
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome: ...


class NodeRegistry(Protocol):
    def register(self, type_name: str, handler: NodeHandler) -> None: ...

    def get(self, type_name: str) -> NodeHandler: ...

    def known_types(self) -> set[str]: ...


class NodeExecutor(Protocol):
    """Sits between engine and handlers — enables timeout, simulation, future streaming."""

    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome: ...


class WorkflowLoader(Protocol):
    def load_path(self, path: Path) -> WorkflowDefinition: ...

    def load_dir(self, directory: Path) -> list[WorkflowDefinition]: ...


class WorkflowRegistry(Protocol):
    def register(self, definition: WorkflowDefinition) -> None: ...

    def get(self, name: str, version: str | None = None) -> WorkflowDefinition: ...

    def list_names(self) -> list[str]: ...


class ConditionEvaluator(Protocol):
    def matches(
        self,
        condition: NodeCondition,
        context: WorkflowContext,
        *,
        last_success: bool,
    ) -> bool: ...


class WorkflowMetricsPort(Protocol):
    def record_workflow_started(self, execution_id: str, workflow_name: str) -> None: ...

    def record_node_timing(
        self,
        execution_id: str,
        node_id: str,
        duration_ms: int,
        retries: int,
        outcome: str,
    ) -> None: ...

    def record_workflow_finished(
        self,
        execution_id: str,
        outcome: str,
        duration_ms: int,
    ) -> None: ...

    def summary(self, execution_id: str) -> dict: ...


class ExecutionHistoryStore(Protocol):
    async def append(self, record: ExecutionHistoryRecord) -> None: ...

    async def list_for_execution(self, execution_id: str) -> list[ExecutionHistoryRecord]: ...


class WorkflowValidator(Protocol):
    def validate(
        self,
        definition: WorkflowDefinition,
        known_types: set[str],
    ) -> Result[WorkflowDefinition]: ...


class WorkflowEngine(Protocol):
    async def run(
        self,
        workflow_name: str,
        *,
        initial_context: WorkflowContext,
        version: str | None = None,
        cancel_token: CancelToken | None = None,
        simulation: SimulationOptions | None = None,
        workflow_timeout_ms: int | None = None,
    ) -> WorkflowResult: ...
