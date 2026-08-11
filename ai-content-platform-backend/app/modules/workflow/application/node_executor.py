"""NodeExecutor — registry lookup + timeout + simulation."""

from __future__ import annotations

import asyncio

from app.modules.workflow.domain.models import (
    NodeOutcome,
    SimulationOptions,
    WorkflowContext,
    WorkflowNode,
)
from app.modules.workflow.domain.ports import NodeRegistry


class RegistryNodeExecutor:
    """Default executor: NodeRegistry → Handler, with timeout and simulation support."""

    def __init__(
        self,
        node_registry: NodeRegistry,
        *,
        simulation: SimulationOptions | None = None,
    ) -> None:
        self._registry = node_registry
        self._simulation = simulation

    def with_simulation(self, simulation: SimulationOptions | None) -> RegistryNodeExecutor:
        return RegistryNodeExecutor(self._registry, simulation=simulation)

    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        sim = self._simulation
        if sim and sim.dry_run:
            context.state["simulation"] = True
            if node.id in sim.mock_outputs:
                outputs = dict(sim.mock_outputs[node.id])
                context.update(outputs)
                return NodeOutcome(success=True, outputs=outputs)
            if node.category in sim.skip_categories and node.type not in {
                "noop",
                "set_context",
                "fail",
            }:
                return NodeOutcome(success=True, outputs={"simulated": True, "node_id": node.id})

        known = self._registry.known_types()
        if node.type not in known:
            if sim and sim.dry_run:
                return NodeOutcome(success=True, outputs={"simulated": True, "node_id": node.id})
            return NodeOutcome(
                success=False,
                error_message=f"No handler registered for node type '{node.type}'",
            )

        handler = self._registry.get(node.type)
        coro = handler.execute(node, context)
        if node.timeout_ms and node.timeout_ms > 0:
            try:
                return await asyncio.wait_for(coro, timeout=node.timeout_ms / 1000.0)
            except TimeoutError:
                return NodeOutcome(
                    success=False,
                    error_message=f"Node '{node.id}' timed out after {node.timeout_ms}ms",
                    timed_out=True,
                )
        return await coro
