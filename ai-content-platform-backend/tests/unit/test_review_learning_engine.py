"""M13 Human Review, Approval & Learning Platform — unit tests."""

from __future__ import annotations

import asyncio
import inspect
import uuid
from pathlib import Path

import pytest

from app.infrastructure.events.in_process_bus import InProcessEventBus
from app.modules.learning.application.factory import LearningFactory
from app.modules.review.application.factory import ReviewFactory
from app.modules.review.domain.models import ReviewStatus
from app.shared.events import draft_approved, draft_edited, draft_rejected
from app.shared.result import Failure, Success


ROOT = Path(__file__).resolve().parents[2]
CONFIGS = ROOT / "configs"


def test_review_service_does_not_import_learning() -> None:
    import app.modules.review.application.service as review_mod
    import app.modules.review.application.engine as engine_mod

    for mod in (review_mod, engine_mod):
        source = inspect.getsource(mod)
        assert "LearningMaterializer" not in source
        assert "modules.learning" not in source


def test_enqueue_assign_approve_flow() -> None:
    async def _run() -> None:
        engine = ReviewFactory.create_memory(config_dir=CONFIGS / "review")
        org = uuid.uuid4()
        draft = uuid.uuid4()
        reviewer = uuid.uuid4()
        session = await engine.enqueue_draft(
            org, draft, original_text="Hello world post", priority="high"
        )
        assert session.status == ReviewStatus.PENDING
        assign = await engine.assign(session.id, [reviewer])
        assert isinstance(assign, Success)
        result = await engine.approve(
            session.id, reviewer, text="Hello world post", hook="Hook"
        )
        assert isinstance(result, Success)
        assert result.value["session"]["status"] == "approved"
        assert engine.metrics.snap.approvals == 1

    asyncio.run(_run())


def test_reject_empty_reason_fails() -> None:
    async def _run() -> None:
        engine = ReviewFactory.create_memory(config_dir=CONFIGS / "review")
        session = await engine.enqueue_draft(uuid.uuid4(), uuid.uuid4())
        result = await engine.reject(session.id, uuid.uuid4(), reason="  ", category="tone")
        assert isinstance(result, Failure)
        assert result.code == "EMPTY_REASON"

    asyncio.run(_run())


def test_feedback_reason_codes_validation() -> None:
    engine = ReviewFactory.create_memory(config_dir=CONFIGS / "review")
    ok, errors = engine.feedback.validate_reason_codes(["hook_weak"], ["writing"])
    assert ok
    ok2, errors2 = engine.feedback.validate_reason_codes(["not_a_code"], ["writing"])
    assert not ok2
    assert any("unknown_reason_code" in e for e in errors2)


def test_versioning_diff_and_rollback() -> None:
    async def _run() -> None:
        engine = ReviewFactory.create_memory(config_dir=CONFIGS / "review")
        session = await engine.enqueue_draft(
            uuid.uuid4(), uuid.uuid4(), original_text="abcdef"
        )
        result = await engine.edit(
            session.id,
            uuid.uuid4(),
            original_text="abcdef",
            edited_text="abcXYZ",
        )
        assert isinstance(result, Success)
        assert result.value["diff"]["edit_distance"] > 0
        ref = engine.versioning.rollback_ref(session, "original")
        assert ref is not None
        assert ref.text == "abcdef"

    asyncio.run(_run())


def test_learning_capture_process_store_approve() -> None:
    async def _run() -> None:
        learning = LearningFactory.create_memory(config_dir=CONFIGS / "learning")
        org = uuid.uuid4()
        event = draft_approved(
            organization_id=org,
            draft_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            feedback_event_id=uuid.uuid4(),
            content_type="linkedin_post",
            text="Great approved post about AI.",
            hook="Hook",
            correlation_id="c-1",
            review_session_id=uuid.uuid4(),
            reason_codes=["hook_weak"],
        )
        result = await learning.handle_domain_event(event)
        assert result["captured"] is True
        assert learning.store.status()["examples"] == 1
        assert any(a["kind"] == "example" for a in result["artifacts"])

    asyncio.run(_run())


def test_learning_reject_creates_rule() -> None:
    async def _run() -> None:
        learning = LearningFactory.create_memory(config_dir=CONFIGS / "learning")
        event = draft_rejected(
            organization_id=uuid.uuid4(),
            draft_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            feedback_event_id=uuid.uuid4(),
            category="tone",
            reason="Too casual for brand",
            correlation_id="c-2",
            reason_codes=["too_casual"],
        )
        result = await learning.handle_domain_event(event)
        assert result["captured"] is True
        assert learning.store.status()["rules"] == 1

    asyncio.run(_run())


def test_learning_preference_history_preserved() -> None:
    async def _run() -> None:
        learning = LearningFactory.create_memory(config_dir=CONFIGS / "learning")
        org = uuid.uuid4()
        for original, edited in (("long text here", "short"), ("aaaa", "bbbbbbbbbbbb")):
            event = draft_edited(
                organization_id=org,
                draft_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                feedback_event_id=uuid.uuid4(),
                original_text=original,
                edited_text=edited,
                correlation_id="c-edit",
            )
            await learning.handle_domain_event(event)
        status = learning.store.status()
        assert status["preferences"] >= 1
        assert status["preference_updates"] >= 1
        # Candidates are never active on create
        assert all(not p.get("is_active") for p in learning.store.preferences)

    asyncio.run(_run())


def test_review_publishes_events_learning_subscribes_without_import() -> None:
    async def _run() -> None:
        bus = InProcessEventBus()
        learning = LearningFactory.create_memory(config_dir=CONFIGS / "learning")

        async def _on_event(event) -> None:
            await learning.handle_domain_event(event)

        bus.subscribe("DraftApproved", _on_event)
        engine = ReviewFactory.create_memory(
            config_dir=CONFIGS / "review", event_bus=bus
        )
        session = await engine.enqueue_draft(
            uuid.uuid4(), uuid.uuid4(), original_text="Post body"
        )
        await engine.assign(session.id, [uuid.uuid4()])
        result = await engine.approve(session.id, uuid.uuid4(), text="Post body")
        assert isinstance(result, Success)
        assert learning.store.status()["examples"] == 1

    asyncio.run(_run())


def test_multi_reviewer_assignment_and_replay() -> None:
    async def _run() -> None:
        from app.modules.review.application.replay import ReviewReplayService

        engine = ReviewFactory.create_memory(config_dir=CONFIGS / "review")
        session = await engine.enqueue_draft(uuid.uuid4(), uuid.uuid4())
        r1, r2 = uuid.uuid4(), uuid.uuid4()
        await engine.assign(session.id, [r1, r2])
        await engine.comment(session.id, r1, "Looks almost ready")
        await engine.approve(session.id, r1, text="ok")
        replay = ReviewReplayService(engine.queue, engine.approval, engine._history)
        data = await replay.replay(session.id)
        assert data["session"] is not None
        assert len(data["decisions"]) >= 1
        assert len(data["comments"]) == 1
        assert len(data["events"]) >= 1

    asyncio.run(_run())


def test_workflow_review_learning_handlers_registered() -> None:
    from app.modules.workflow.application.factory import WorkflowFactory

    _engine, _wr, nr = WorkflowFactory.create(load_builtins=True)
    known = nr.known_types()
    for name in (
        "review.queue",
        "review.assign",
        "review.approve",
        "review.reject",
        "review.edit",
        "learning.capture",
        "learning.process",
        "learning.store",
    ):
        assert name in known, name


def test_workflow_review_learning_end_to_end() -> None:
    async def _run() -> None:
        from app.modules.workflow.application.factory import WorkflowFactory
        from app.modules.workflow.domain.models import WorkflowContext

        wf_engine, wr, _nr = WorkflowFactory.create(
            workflows_dir=CONFIGS / "workflows",
            load_builtins=True,
        )
        assert wr.get("review_learning") is not None
        ctx = WorkflowContext(
            correlation_id="m13-wf",
            data={
                "organization_id": str(uuid.uuid4()),
                "draft_id": str(uuid.uuid4()),
                "text": "Workflow approved LinkedIn post body.",
                "hook": "WF Hook",
                "action": "approve",
                "reviewer_ids": [str(uuid.uuid4())],
                "actor_id": str(uuid.uuid4()),
            },
        )
        result = await wf_engine.run("review_learning", initial_context=ctx)
        assert result.success, result.error_message or result.error_code
        assert result.context.get("learning.status") is not None
        assert result.context.get("learning.status")["examples"] >= 1

    asyncio.run(_run())


def test_decision_policy_loads_from_yaml() -> None:
    engine = ReviewFactory.create_memory(config_dir=CONFIGS / "review")
    assert engine.decision._approval().get("default_mode") == "manual"
    assert engine.decision._approval().get("required_reviewers") == 1


def test_review_metrics_approval_rate() -> None:
    async def _run() -> None:
        engine = ReviewFactory.create_memory(config_dir=CONFIGS / "review")
        s1 = await engine.enqueue_draft(uuid.uuid4(), uuid.uuid4())
        await engine.approve(s1.id, uuid.uuid4(), text="a")
        s2 = await engine.enqueue_draft(uuid.uuid4(), uuid.uuid4())
        await engine.reject(s2.id, uuid.uuid4(), reason="nope", category="general")
        assert engine.metrics.approval_rate() == pytest.approx(0.5)

    asyncio.run(_run())
