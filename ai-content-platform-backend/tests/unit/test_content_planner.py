"""Content Planner refinements + Strategy Engine unit tests."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from app.modules.content.application.audience_engine import DefaultAudienceEngine
from app.modules.content.application.calendar_awareness import StubCalendarAwareness
from app.modules.content.application.diversity_engine import DefaultContentDiversityEngine
from app.modules.content.application.factory import ContentPlannerFactory
from app.modules.content.application.strategy import DefaultStrategyEngine
from app.modules.content.application.topic_intelligence import DefaultTopicIntelligence
from app.modules.content.application.validator import DefaultContentValidator
from app.modules.content.domain.models import (
    Audience,
    ContentFormat,
    ContentType,
    PlanStatus,
    PlannerInput,
    PlannerPolicy,
    RecentContentHistory,
    StrategyAction,
)
from app.modules.content.infrastructure.policy_loader import YamlPlannerPolicyLoader
from app.modules.knowledge.domain.models import (
    CitationMap,
    KnowledgeItem,
    KnowledgeType,
    OptimizedContext,
)
from app.modules.workflow.application.factory import WorkflowFactory
from app.modules.workflow.domain.models import WorkflowContext

ORG = uuid.uuid4()
CONFIGS = Path(__file__).resolve().parents[2] / "configs"


def _ctx(text: str = "DSPT compliance update for care homes") -> OptimizedContext:
    return OptimizedContext(
        text=text,
        citations=({"id": "c1", "title": "DSPT"},),
        citation_map=CitationMap(),
        knowledge_sources=("articles", "rules"),
        items=(
            KnowledgeItem(
                id="1",
                type=KnowledgeType.ARTICLE,
                organization_id=ORG,
                title="DSPT",
                content=text,
                rank_score=0.8,
                similarity=0.7,
            ),
        ),
        token_estimate=40,
        token_budget=4000,
        sections={"knowledge": text, "rules": "Always cite sources"},
        metrics={},
    )


def _inp(**kwargs) -> PlannerInput:
    base = dict(
        organization_id=ORG,
        context=_ctx(),
        topic="DSPT compliance for care homes",
        industry="healthcare",
        relevance_score=0.85,
        correlation_id="plan-1",
    )
    base.update(kwargs)
    return PlannerInput(**base)


def test_policy_loader() -> None:
    policy = YamlPlannerPolicyLoader(CONFIGS / "planner").load("default")
    assert policy.min_relevance > 0
    assert policy.priorities
    assert policy.require_image_style


def test_strategy_ignores_low_relevance() -> None:
    decision = asyncio.run(
        DefaultStrategyEngine().evaluate(
            PlannerInput(
                organization_id=ORG,
                context=_ctx(),
                topic="random",
                relevance_score=0.1,
            ),
            PlannerPolicy(min_relevance=0.3),
        )
    )
    assert decision.action == StrategyAction.IGNORE


def test_strategy_ignores_duplicates() -> None:
    decision = asyncio.run(
        DefaultStrategyEngine().evaluate(
            PlannerInput(
                organization_id=ORG,
                context=_ctx(),
                topic="dspt care homes compliance",
                previous_post_topics=("dspt care homes compliance guide",),
                relevance_score=0.9,
            ),
            PlannerPolicy(max_duplicate_score=0.5, min_relevance=0.2, min_confidence=0.2),
        )
    )
    assert decision.action == StrategyAction.IGNORE


def test_strategy_security_alert() -> None:
    decision = asyncio.run(
        DefaultStrategyEngine().evaluate(
            PlannerInput(
                organization_id=ORG,
                context=_ctx("ransomware phishing mfa breach alert"),
                topic="ransomware phishing mfa",
                relevance_score=0.9,
            ),
            PlannerPolicy(min_relevance=0.2, min_confidence=0.2),
        )
    )
    assert decision.action == StrategyAction.CREATE
    assert decision.recommended_type == ContentType.SECURITY_ALERT
    assert decision.format == ContentFormat.SINGLE


def test_strategy_checklist_carousel() -> None:
    decision = asyncio.run(
        DefaultStrategyEngine().evaluate(
            PlannerInput(
                organization_id=ORG,
                context=_ctx("security checklist how to steps"),
                topic="security checklist how to",
                relevance_score=0.9,
            ),
            PlannerPolicy(min_relevance=0.2, min_confidence=0.2),
        )
    )
    assert decision.recommended_type == ContentType.CHECKLIST
    assert decision.format == ContentFormat.CAROUSEL


def test_planner_does_not_self_validate() -> None:
    planner = ContentPlannerFactory.create_memory()
    assert not hasattr(planner, "validate_plan")
    plan = asyncio.run(planner.plan(_inp()))
    assert plan.metrics.get("validated") is False
    assert plan.status == PlanStatus.PENDING
    assert plan.explanation.decision
    assert plan.explanation.evidence


def test_pipeline_validates_separately() -> None:
    pipeline = ContentPlannerFactory.create_pipeline_memory()
    plan = asyncio.run(pipeline.prepare_plan(_inp()))
    assert plan.metrics.get("validated") is True
    assert plan.metrics.get("valid") is True
    snap = pipeline.metrics.snapshot()
    assert snap.accepted_plans >= 1


def test_planner_ignore_path() -> None:
    planner = ContentPlannerFactory.create_memory()
    plan = asyncio.run(
        planner.plan(
            _inp(topic="noise", relevance_score=0.05, correlation_id="ign-1")
        )
    )
    assert plan.status == PlanStatus.IGNORED
    assert plan.strategy_action == StrategyAction.IGNORE


def test_content_validator_independent() -> None:
    planner = ContentPlannerFactory.create_memory()
    plan = asyncio.run(planner.plan(_inp(topic="Educational guide on MFA", relevance_score=0.9)))
    result = DefaultContentValidator().validate(plan, PlannerPolicy())
    assert result.valid


def test_topic_intelligence() -> None:
    signals = asyncio.run(
        DefaultTopicIntelligence().analyze(_inp(), PlannerPolicy())
    )
    assert 0.0 <= signals.novelty_score <= 1.0
    assert signals.category in {"compliance", "security", "healthcare", "educational", "general"}


def test_audience_engine() -> None:
    profile = DefaultAudienceEngine().resolve(_inp(), PlannerPolicy())
    assert profile.primary == Audience.HEALTHCARE
    assert profile.confidence > 0
    assert profile.hierarchy


def test_diversity_engine() -> None:
    rec = DefaultContentDiversityEngine().recommend(
        _inp(previous_content_types=("educational",) * 5),
        PlannerPolicy(diversity_max_type_share=0.4),
        RecentContentHistory(content_types=("educational",) * 5),
    )
    assert rec.repetition_score >= 0.4
    assert rec.recommend_alternate_type is not None


def test_calendar_stub() -> None:
    ctx = StubCalendarAwareness().snapshot(ORG)
    assert ctx.frequency_ok
    assert ctx.today_generated_count == 0


def test_workflow_content_plan_nodes() -> None:
    engine, wreg, nreg = WorkflowFactory.create(workflows_dir=CONFIGS / "workflows")
    assert "content.strategy" in nreg.known_types()
    assert "content.plan" in nreg.known_types()
    assert "content.validate" in nreg.known_types()
    assert "content_plan" in wreg.list_names()
    result = asyncio.run(
        engine.run(
            "content_plan",
            initial_context=WorkflowContext(
                correlation_id="cwf",
                organization_id=ORG,
                data={
                    "topic": "DSPT compliance checklist for care homes",
                    "industry": "healthcare",
                    "relevance_score": 0.8,
                    "knowledge.optimized_context": {
                        "text": "DSPT compliance checklist",
                        "sections": {"knowledge": "DSPT compliance checklist"},
                        "token_estimate": 30,
                        "token_budget": 4000,
                    },
                },
            ),
        )
    )
    assert result.success
    assert result.context.get("content.plan") is not None
    assert result.context.get("content.strategy_decision") is not None
    assert result.context.get("content.plan_valid") is True
