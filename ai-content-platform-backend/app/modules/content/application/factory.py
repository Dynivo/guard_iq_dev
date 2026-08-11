"""Compose Content Planner pipeline with engines, validator, metrics."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai_cache.application.namespaced import NamespacedAICache
from app.modules.ai_cache.infrastructure.memory_cache import InMemoryAICache
from app.modules.content.application.audience_engine import DefaultAudienceEngine
from app.modules.content.application.business_priority import DefaultBusinessPriorityEngine
from app.modules.content.application.calendar_awareness import StubCalendarAwareness
from app.modules.content.application.diversity_engine import DefaultContentDiversityEngine
from app.modules.content.application.metrics import PlannerMetricsRecorder
from app.modules.content.application.pipeline import DefaultContentPlanPipeline
from app.modules.content.application.planner import DefaultContentPlanner
from app.modules.content.application.strategy import DefaultStrategyEngine
from app.modules.content.application.topic_intelligence import DefaultTopicIntelligence
from app.modules.content.application.validator import DefaultContentValidator
from app.modules.content.infrastructure.plan_repository import (
    InMemoryContentPlanRepository,
    PgContentPlanRepository,
)
from app.modules.content.infrastructure.policy_loader import YamlPlannerPolicyLoader

_CONFIGS = Path(__file__).resolve().parents[4] / "configs" / "planner"


class ContentPlannerFactory:
    @staticmethod
    def create_memory(*, policy_id: str = "default") -> DefaultContentPlanner:
        policy = YamlPlannerPolicyLoader(_CONFIGS).load(policy_id)
        cache = NamespacedAICache(InMemoryAICache())
        return DefaultContentPlanner(
            strategy=DefaultStrategyEngine(),
            repository=InMemoryContentPlanRepository(),
            policy=policy,
            cache=cache,
            topic_intelligence=DefaultTopicIntelligence(cache),
            audience_engine=DefaultAudienceEngine(),
            diversity_engine=DefaultContentDiversityEngine(),
            calendar=StubCalendarAwareness(),
            business_priority=DefaultBusinessPriorityEngine(),
        )

    @staticmethod
    def create_pipeline_memory(
        *, policy_id: str = "default", metrics: PlannerMetricsRecorder | None = None
    ) -> DefaultContentPlanPipeline:
        policy = YamlPlannerPolicyLoader(_CONFIGS).load(policy_id)
        planner = ContentPlannerFactory.create_memory(policy_id=policy_id)
        return DefaultContentPlanPipeline(
            planner=planner,
            validator=DefaultContentValidator(),
            policy=policy,
            metrics=metrics or PlannerMetricsRecorder(),
        )

    @staticmethod
    def create(
        session: AsyncSession | None = None,
        *,
        policy_id: str = "default",
    ) -> DefaultContentPlanner:
        if session is None:
            return ContentPlannerFactory.create_memory(policy_id=policy_id)
        policy = YamlPlannerPolicyLoader(_CONFIGS).load(policy_id)
        cache = NamespacedAICache(InMemoryAICache())
        return DefaultContentPlanner(
            strategy=DefaultStrategyEngine(),
            repository=PgContentPlanRepository(session),
            policy=policy,
            cache=cache,
            topic_intelligence=DefaultTopicIntelligence(cache),
            audience_engine=DefaultAudienceEngine(),
            diversity_engine=DefaultContentDiversityEngine(),
            calendar=StubCalendarAwareness(),
            business_priority=DefaultBusinessPriorityEngine(),
        )

    @staticmethod
    def create_pipeline(
        session: AsyncSession | None = None,
        *,
        policy_id: str = "default",
        metrics: PlannerMetricsRecorder | None = None,
    ) -> DefaultContentPlanPipeline:
        policy = YamlPlannerPolicyLoader(_CONFIGS).load(policy_id)
        planner = ContentPlannerFactory.create(session, policy_id=policy_id)
        return DefaultContentPlanPipeline(
            planner=planner,
            validator=DefaultContentValidator(),
            policy=policy,
            metrics=metrics or PlannerMetricsRecorder(),
        )
