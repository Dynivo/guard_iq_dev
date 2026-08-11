"""Planner metrics recorder — in-memory distributions."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from threading import Lock

from app.modules.content.domain.models import ContentFormat, ContentPlan, StrategyAction


@dataclass
class PlannerMetricsSnapshot:
    planning_ms_total: int = 0
    accepted_plans: int = 0
    rejected_plans: int = 0
    create_actions: int = 0
    ignore_actions: int = 0
    carousel_count: int = 0
    single_count: int = 0
    content_types: dict[str, int] = field(default_factory=dict)
    audiences: dict[str, int] = field(default_factory=dict)

    @property
    def carousel_ratio(self) -> float:
        total = self.carousel_count + self.single_count
        return self.carousel_count / total if total else 0.0

    @property
    def strategy_create_ratio(self) -> float:
        total = self.create_actions + self.ignore_actions
        return self.create_actions / total if total else 0.0

    def to_dict(self) -> dict:
        return {
            "planning_ms_total": self.planning_ms_total,
            "accepted_plans": self.accepted_plans,
            "rejected_plans": self.rejected_plans,
            "create_actions": self.create_actions,
            "ignore_actions": self.ignore_actions,
            "carousel_ratio": round(self.carousel_ratio, 3),
            "strategy_create_ratio": round(self.strategy_create_ratio, 3),
            "content_types": dict(self.content_types),
            "audiences": dict(self.audiences),
        }


class PlannerMetricsRecorder:
    def __init__(self) -> None:
        self._lock = Lock()
        self._planning_ms_total = 0
        self._accepted = 0
        self._rejected = 0
        self._create = 0
        self._ignore = 0
        self._carousel = 0
        self._single = 0
        self._types: Counter[str] = Counter()
        self._audiences: Counter[str] = Counter()

    def record(self, plan: ContentPlan) -> None:
        with self._lock:
            self._planning_ms_total += int(plan.metrics.get("planning_ms") or 0)
            if plan.strategy_action == StrategyAction.CREATE and plan.status.value not in {
                "rejected",
                "ignored",
            }:
                self._accepted += 1
                self._create += 1
            else:
                self._rejected += 1
                if plan.strategy_action == StrategyAction.IGNORE:
                    self._ignore += 1
                else:
                    self._create += 1
            if plan.format == ContentFormat.CAROUSEL:
                self._carousel += 1
            else:
                self._single += 1
            self._types[plan.content_type.value] += 1
            self._audiences[plan.audience.value] += 1

    def snapshot(self) -> PlannerMetricsSnapshot:
        with self._lock:
            return PlannerMetricsSnapshot(
                planning_ms_total=self._planning_ms_total,
                accepted_plans=self._accepted,
                rejected_plans=self._rejected,
                create_actions=self._create,
                ignore_actions=self._ignore,
                carousel_count=self._carousel,
                single_count=self._single,
                content_types=dict(self._types),
                audiences=dict(self._audiences),
            )
