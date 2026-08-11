"""Workflow interceptors — future modules hook execution without changing the engine."""

from __future__ import annotations

from typing import Any, Protocol

from app.modules.workflow.domain.models import NodeOutcome, WorkflowContext, WorkflowNode, WorkflowResult


class WorkflowInterceptor(Protocol):
    """Same hook surface as middleware; intended for cross-module registration."""

    async def before_workflow(self, context: WorkflowContext, workflow_name: str) -> None: ...

    async def after_workflow(self, context: WorkflowContext, result: WorkflowResult) -> None: ...

    async def before_node(self, context: WorkflowContext, node: WorkflowNode) -> None: ...

    async def after_node(
        self,
        context: WorkflowContext,
        node: WorkflowNode,
        outcome: NodeOutcome,
    ) -> None: ...


class InterceptorRegistry:
    def __init__(self) -> None:
        self._items: list[Any] = []

    def register(self, interceptor: WorkflowInterceptor) -> None:
        self._items.append(interceptor)

    def all(self) -> list[Any]:
        return list(self._items)

    async def before_workflow(self, context: WorkflowContext, workflow_name: str) -> None:
        for item in self._items:
            await item.before_workflow(context, workflow_name)

    async def after_workflow(self, context: WorkflowContext, result: WorkflowResult) -> None:
        for item in reversed(self._items):
            await item.after_workflow(context, result)

    async def before_node(self, context: WorkflowContext, node: WorkflowNode) -> None:
        for item in self._items:
            await item.before_node(context, node)

    async def after_node(
        self,
        context: WorkflowContext,
        node: WorkflowNode,
        outcome: NodeOutcome,
    ) -> None:
        for item in reversed(self._items):
            await item.after_node(context, node, outcome)
