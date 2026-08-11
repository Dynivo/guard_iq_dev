"""ContentPlanPipeline — Planner → ContentValidator → ContentPlan."""

from __future__ import annotations

from dataclasses import replace

from app.modules.content.application.metrics import PlannerMetricsRecorder
from app.modules.content.domain.models import (
    ContentPlan,
    PlanStatus,
    PlannerInput,
    PlannerPolicy,
    StrategyAction,
)
from app.modules.content.domain.ports import ContentPlanner, ContentValidator


class DefaultContentPlanPipeline:
    def __init__(
        self,
        *,
        planner: ContentPlanner,
        validator: ContentValidator,
        policy: PlannerPolicy,
        metrics: PlannerMetricsRecorder | None = None,
    ) -> None:
        self._planner = planner
        self._validator = validator
        self._policy = policy
        self._metrics = metrics or PlannerMetricsRecorder()

    @property
    def planner(self) -> ContentPlanner:
        return self._planner

    @property
    def validator(self) -> ContentValidator:
        return self._validator

    @property
    def metrics(self) -> PlannerMetricsRecorder:
        return self._metrics

    async def prepare_plan(self, inp: PlannerInput) -> ContentPlan:
        plan = await self._planner.plan(inp)
        if plan.strategy_action == StrategyAction.IGNORE:
            self._metrics.record(plan)
            return plan

        result = self._validator.validate(plan, self._policy)
        if not result.valid:
            plan = replace(
                plan,
                status=PlanStatus.REJECTED,
                strategy_action=StrategyAction.IGNORE,
                rejected_reason="; ".join(result.errors),
                reasoning=plan.reasoning + result.errors,
                metrics={**plan.metrics, "validated": True, "valid": False},
            )
        else:
            plan = replace(
                plan,
                metrics={**plan.metrics, "validated": True, "valid": True},
            )
        self._metrics.record(plan)
        return plan
