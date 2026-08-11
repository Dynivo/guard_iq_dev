"""Built-in domain-agnostic node handlers."""

from __future__ import annotations

from app.modules.workflow.domain.models import NodeOutcome, WorkflowContext, WorkflowNode


class NoopHandler:
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        return NodeOutcome(success=True, outputs={})


class SetContextHandler:
    """Merge `config.set` dict into context.data."""

    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        values = node.config.get("set") or {}
        if not isinstance(values, dict):
            return NodeOutcome(
                success=False,
                error_message="set_context requires config.set as object",
            )
        context.update(values)
        return NodeOutcome(success=True, outputs=dict(values))


class FailHandler:
    """Always fails — useful for retry/fallback tests."""

    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        message = str(node.config.get("message") or f"Node {node.id} forced failure")
        return NodeOutcome(success=False, error_message=message)


def register_builtin_handlers(registry) -> None:
    registry.register("noop", NoopHandler())
    registry.register("set_context", SetContextHandler())
    registry.register("fail", FailHandler())
