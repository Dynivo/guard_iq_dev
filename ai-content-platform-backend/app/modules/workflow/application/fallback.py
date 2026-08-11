"""Fallback resolution after node failure."""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.workflow.domain.models import FallbackPolicy, FallbackStrategy, WorkflowNode


@dataclass(frozen=True, slots=True)
class FallbackDecision:
    action: str  # continue_node | skip | stop
    next_node_id: str | None = None


def resolve_fallback(node: WorkflowNode) -> FallbackDecision:
    policy = node.fallback or FallbackPolicy(strategy=FallbackStrategy.STOP)
    if policy.strategy == FallbackStrategy.ALTERNATIVE_NODE:
        if not policy.alternative_node_id:
            return FallbackDecision(action="stop")
        return FallbackDecision(action="continue_node", next_node_id=policy.alternative_node_id)
    if policy.strategy == FallbackStrategy.SKIP:
        return FallbackDecision(action="skip")
    return FallbackDecision(action="stop")
