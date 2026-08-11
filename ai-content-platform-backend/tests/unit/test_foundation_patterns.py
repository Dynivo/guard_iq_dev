"""Unit tests for Result pattern, EventBus, correlation, Review decoupling."""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.observability.correlation import (
    ensure_correlation_id,
    get_correlation_id,
    reset_correlation_id,
    set_correlation_id,
)
from app.infrastructure.events.in_process_bus import InProcessEventBus
from app.modules.review.application.service import ReviewService, unwrap_result
from app.shared.events import draft_approved
from app.shared.events.session_context import reset_event_session, set_event_session
from app.shared.result import Failure, Success, fail, ok


def test_result_ok_and_fail() -> None:
    s = ok({"id": "1"})
    assert isinstance(s, Success)
    assert s.is_success
    f = fail("EMPTY_TEXT", "nope")
    assert isinstance(f, Failure)
    assert f.is_failure
    assert f.code == "EMPTY_TEXT"


def test_unwrap_result_raises_validation() -> None:
    from app.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        unwrap_result(fail("INVALID_STATUS", "bad"))
    assert unwrap_result(ok({"a": 1})) == {"a": 1}


def test_correlation_contextvar() -> None:
    token = set_correlation_id("corr-abc")
    try:
        assert get_correlation_id() == "corr-abc"
        assert ensure_correlation_id() == "corr-abc"
    finally:
        reset_correlation_id(token)


def test_event_bus_delivers_to_subscriber() -> None:
    bus = InProcessEventBus()
    received: list[str] = []

    async def handler(event) -> None:
        received.append(event.event_type)

    bus.subscribe("DraftApproved", handler)
    org = uuid.uuid4()
    event = draft_approved(
        organization_id=org,
        draft_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        feedback_event_id=uuid.uuid4(),
        content_type="educational",
        text="hello",
        hook="Hook",
        correlation_id="c-1",
    )
    asyncio.run(bus.publish(event))
    assert received == ["DraftApproved"]


def test_review_service_does_not_import_learning_materializer() -> None:
    import inspect

    import app.modules.review.application.service as review_mod

    source = inspect.getsource(review_mod)
    assert "LearningMaterializer" not in source
    assert "modules.learning" not in source


def test_review_edit_empty_returns_failure() -> None:
    session = MagicMock()
    bus = InProcessEventBus()
    svc = ReviewService(session, event_bus=bus)

    draft = MagicMock()
    draft.organization_id = uuid.uuid4()
    draft.generated_text = "orig"
    draft.status = "pending_review"
    draft.id = uuid.uuid4()

    async def _run() -> None:
        session.get = AsyncMock(return_value=draft)
        result = await svc.edit(draft.organization_id, draft.id, uuid.uuid4(), "   ")
        assert isinstance(result, Failure)
        assert result.code == "EMPTY_TEXT"

    asyncio.run(_run())


def test_learning_handler_uses_session_context() -> None:
    from app.modules.learning.application.subscribers import register_learning_handlers
    from app.modules.learning.application.materialize import LearningMaterializer

    bus = InProcessEventBus()
    register_learning_handlers(bus)

    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()

    # Patch materializer path by using real handle with mocked session.add
    org = uuid.uuid4()
    event = draft_approved(
        organization_id=org,
        draft_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        feedback_event_id=uuid.uuid4(),
        content_type="educational",
        text="Approved post text",
        hook="H",
        correlation_id="c-learn",
    )

    async def _run() -> None:
        token = set_event_session(session)
        try:
            await bus.publish(event)
        finally:
            reset_event_session(token)

    asyncio.run(_run())
    assert session.add.called
    assert session.flush.await_count >= 1
