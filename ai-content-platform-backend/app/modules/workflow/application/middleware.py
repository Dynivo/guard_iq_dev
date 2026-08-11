"""Pluggable workflow middleware (FastAPI-style hooks)."""

from __future__ import annotations

from typing import Any, Protocol

from app.core.logging import get_logger
from app.modules.workflow.domain.models import NodeOutcome, WorkflowContext, WorkflowNode, WorkflowResult
from app.modules.workflow.domain.ports import WorkflowMetricsPort

logger = get_logger(__name__)


class WorkflowMiddleware(Protocol):
    async def before_workflow(self, context: WorkflowContext, workflow_name: str) -> None: ...

    async def after_workflow(self, context: WorkflowContext, result: WorkflowResult) -> None: ...

    async def before_node(self, context: WorkflowContext, node: WorkflowNode) -> None: ...

    async def after_node(
        self,
        context: WorkflowContext,
        node: WorkflowNode,
        outcome: NodeOutcome,
    ) -> None: ...


class LoggingMiddleware:
    async def before_workflow(self, context: WorkflowContext, workflow_name: str) -> None:
        logger.info(
            "workflow.before",
            extra={
                "app_module": "workflow",
                "operation": "before_workflow",
                "correlation_id": context.correlation_id,
                "workflow_name": workflow_name,
            },
        )

    async def after_workflow(self, context: WorkflowContext, result: WorkflowResult) -> None:
        logger.info(
            "workflow.after",
            extra={
                "app_module": "workflow",
                "operation": "after_workflow",
                "correlation_id": context.correlation_id,
                "outcome": "success" if result.success else "failure",
            },
        )

    async def before_node(self, context: WorkflowContext, node: WorkflowNode) -> None:
        logger.info(
            "workflow.node.before",
            extra={
                "app_module": "workflow",
                "operation": "before_node",
                "correlation_id": context.correlation_id,
                "node_id": node.id,
            },
        )

    async def after_node(
        self,
        context: WorkflowContext,
        node: WorkflowNode,
        outcome: NodeOutcome,
    ) -> None:
        logger.info(
            "workflow.node.after",
            extra={
                "app_module": "workflow",
                "operation": "after_node",
                "correlation_id": context.correlation_id,
                "node_id": node.id,
                "outcome": "success" if outcome.success else "failure",
            },
        )


class MetricsMiddleware:
    """Optional middleware — factory does not enable by default."""

    def __init__(self, metrics: WorkflowMetricsPort) -> None:
        self._metrics = metrics

    async def before_workflow(self, context: WorkflowContext, workflow_name: str) -> None:
        return None

    async def after_workflow(self, context: WorkflowContext, result: WorkflowResult) -> None:
        return None

    async def before_node(self, context: WorkflowContext, node: WorkflowNode) -> None:
        return None

    async def after_node(
        self,
        context: WorkflowContext,
        node: WorkflowNode,
        outcome: NodeOutcome,
    ) -> None:
        return None


class MiddlewareChain:
    def __init__(self, middlewares: list[Any] | None = None) -> None:
        self._items = list(middlewares or [])

    def add(self, middleware: WorkflowMiddleware) -> None:
        self._items.append(middleware)

    async def before_workflow(self, context: WorkflowContext, workflow_name: str) -> None:
        for mw in self._items:
            await mw.before_workflow(context, workflow_name)

    async def after_workflow(self, context: WorkflowContext, result: WorkflowResult) -> None:
        for mw in reversed(self._items):
            await mw.after_workflow(context, result)

    async def before_node(self, context: WorkflowContext, node: WorkflowNode) -> None:
        for mw in self._items:
            await mw.before_node(context, node)

    async def after_node(
        self,
        context: WorkflowContext,
        node: WorkflowNode,
        outcome: NodeOutcome,
    ) -> None:
        for mw in reversed(self._items):
            await mw.after_node(context, node, outcome)
