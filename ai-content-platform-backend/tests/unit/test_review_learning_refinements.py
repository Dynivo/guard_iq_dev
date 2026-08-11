"""M13r Review & Learning refinements — unit tests."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import pytest

from app.modules.learning.application.confidence import LearningConfidenceService
from app.modules.learning.application.factory import LearningFactory
from app.modules.learning.application.lifecycle import KnowledgeLifecycleService
from app.modules.learning.domain.models import KnowledgeLifecycle
from app.modules.review.application.factory import ReviewFactory
from app.modules.review.application.workflow_templates import ReviewWorkflowTemplateService
from app.shared.events import draft_approved, draft_edited
from app.shared.result import Failure, Success


ROOT = Path(__file__).resolve().parents[2]
CONFIGS = ROOT / "configs"
REVIEW_CFG = CONFIGS / "review"
LEARNING_CFG = CONFIGS / "learning"


def test_knowledge_starts_as_candidate_not_active() -> None:
    async def _run() -> None:
        learning = LearningFactory.create_memory(config_dir=LEARNING_CFG)
        event = draft_approved(
            organization_id=uuid.uuid4(),
            draft_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            feedback_event_id=uuid.uuid4(),
            content_type="linkedin_post",
            text="Candidate example text",
            hook="H",
            correlation_id="c-life",
        )
        result = await learning.handle_domain_event(event)
        assert result["captured"] is True
        art = result["artifacts"][0]
        assert art["lifecycle"] == "candidate"
        assert art["is_active"] is False
        stored = learning.store.examples[0]
        assert stored["lifecycle"] == "candidate"
        assert stored["is_active"] is False

    asyncio.run(_run())


def test_lifecycle_transition_to_approved_activates() -> None:
    async def _run() -> None:
        learning = LearningFactory.create_memory(config_dir=LEARNING_CFG)
        event = draft_approved(
            organization_id=uuid.uuid4(),
            draft_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            feedback_event_id=uuid.uuid4(),
            content_type="linkedin_post",
            text="Promote me",
            hook="H",
            correlation_id="c-approve-life",
        )
        await learning.handle_domain_event(event)
        ex_id = learning.store.examples[0]["id"]
        await learning.store.transition_lifecycle("examples", ex_id, "verified")
        row = await learning.store.transition_lifecycle("examples", ex_id, "approved")
        assert row["lifecycle"] == "approved"
        assert row["is_active"] is True
        with pytest.raises(ValueError):
            await learning.store.transition_lifecycle("examples", ex_id, "candidate")

    asyncio.run(_run())


def test_lifecycle_service_invalid_skip() -> None:
    svc = KnowledgeLifecycleService(str(LEARNING_CFG))
    result = svc.transition(KnowledgeLifecycle.CANDIDATE, KnowledgeLifecycle.APPROVED)
    assert isinstance(result, Failure)


def test_confidence_fields_on_artifacts() -> None:
    async def _run() -> None:
        learning = LearningFactory.create_memory(config_dir=LEARNING_CFG)
        event = draft_edited(
            organization_id=uuid.uuid4(),
            draft_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            feedback_event_id=uuid.uuid4(),
            original_text="long original text here",
            edited_text="short",
            correlation_id="c-conf",
        )
        result = await learning.handle_domain_event(event)
        for art in result["artifacts"]:
            assert "confidence" in art
            assert art["approval_count"] == 0
            assert art["usage_count"] == 0
            assert art["success_rate"] == 0.0
            assert art["created_from_review"] is True
            assert art["last_used"] is None
        assert learning.store.status()["signals"] >= 1

    asyncio.run(_run())


def test_confidence_record_usage() -> None:
    svc = LearningConfidenceService()
    art = {"usage_count": 0, "success_rate": 0.0, "confidence": 0.5}
    art = svc.record_usage(art, success=True)
    assert art["usage_count"] == 1
    assert art["success_rate"] == 1.0
    assert art["last_used"] is not None
    art = svc.record_approval(art)
    assert art["approval_count"] == 1
    assert art["confidence"] > 0.5


def test_dynamic_policy_cybersecurity_requires_three() -> None:
    async def _run() -> None:
        engine = ReviewFactory.create_memory(config_dir=REVIEW_CFG)
        org = uuid.uuid4()
        session = await engine.enqueue_draft(
            org,
            uuid.uuid4(),
            topic="cybersecurity",
            risk="high",
            original_text="sec post",
        )
        resolved = engine.decision.resolve_requirements(session)
        assert resolved["required_reviewers"] == 3
        assert resolved["quorum"] == 3
        # One reviewer insufficient
        await engine.assign(session.id, [uuid.uuid4()])
        result = await engine.approve(session.id, uuid.uuid4(), text="sec post")
        assert isinstance(result, Failure)
        assert "insufficient_reviewers" in (result.message or "")
        # Three reviewers — ok
        r2, r3 = uuid.uuid4(), uuid.uuid4()
        await engine.assign(session.id, [r2, r3])
        result2 = await engine.approve(session.id, r2, text="sec post")
        assert isinstance(result2, Success)

    asyncio.run(_run())


def test_workflow_template_cybersecurity_applies_metadata() -> None:
    async def _run() -> None:
        engine = ReviewFactory.create_memory(config_dir=REVIEW_CFG)
        session = await engine.enqueue_draft(
            uuid.uuid4(),
            uuid.uuid4(),
            template_id="cybersecurity",
        )
        assert session.metadata.get("template_id") == "cybersecurity"
        assert session.metadata.get("topic") == "cybersecurity"
        assert session.metadata.get("risk") == "high"
        assert session.metadata.get("template_required_reviewers") == 3
        resolved = engine.decision.resolve_requirements(session)
        assert resolved["quorum"] == 3

    asyncio.run(_run())


def test_all_workflow_templates_load() -> None:
    svc = ReviewWorkflowTemplateService(str(REVIEW_CFG))
    ids = svc.list_ids()
    for tid in (
        "marketing",
        "engineering",
        "compliance",
        "cybersecurity",
        "healthcare",
        "finance",
    ):
        assert tid in ids
        assert svc.get(tid)


def test_reviewer_intelligence_metrics() -> None:
    async def _run() -> None:
        engine = ReviewFactory.create_memory(config_dir=REVIEW_CFG)
        org = uuid.uuid4()
        reviewer = uuid.uuid4()
        s1 = await engine.enqueue_draft(org, uuid.uuid4(), original_text="a")
        await engine.assign(s1.id, [reviewer])
        await engine.approve(s1.id, reviewer, text="a")
        s2 = await engine.enqueue_draft(org, uuid.uuid4())
        await engine.reject(s2.id, reviewer, reason="bad", category="tone")
        s3 = await engine.enqueue_draft(org, uuid.uuid4(), original_text="abcdef")
        await engine.edit(
            s3.id, reviewer, original_text="abcdef", edited_text="abcXYZ"
        )
        profile = engine.reviewer_intelligence.get(org, reviewer)
        assert profile is not None
        assert profile.approvals == 1
        assert profile.rejections == 1
        assert profile.edits == 1
        assert profile.approval_rate == pytest.approx(0.5)
        assert profile.rejection_rate == pytest.approx(0.5)
        assert profile.average_edit_distance > 0
        assert 0.0 <= profile.recommendation_score <= 1.0

    asyncio.run(_run())


def test_preference_history_still_preserved_as_candidates() -> None:
    async def _run() -> None:
        learning = LearningFactory.create_memory(config_dir=LEARNING_CFG)
        org = uuid.uuid4()
        for original, edited in (("long text here", "short"), ("aaaa", "bbbbbbbbbbbb")):
            event = draft_edited(
                organization_id=org,
                draft_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                feedback_event_id=uuid.uuid4(),
                original_text=original,
                edited_text=edited,
                correlation_id="c-pref",
            )
            await learning.handle_domain_event(event)
        status = learning.store.status()
        assert status["preferences"] >= 2
        assert status["preference_updates"] >= 1
        assert all(p.get("lifecycle") == "candidate" for p in learning.store.preferences)
        assert status["preferences_active"] == 0

    asyncio.run(_run())
