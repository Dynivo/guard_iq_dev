"""Tests for stuck image-batch recovery helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.modules.image.application.orphan_recovery import _never_started


def test_never_started_queued_pending() -> None:
    job = SimpleNamespace(
        status="pending",
        generation_metadata_json={"batch": True, "phase": "queued"},
        created_at=datetime.now(timezone.utc) - timedelta(hours=2),
        id=uuid4(),
    )
    assert _never_started(job) is True


def test_running_phase_not_never_started() -> None:
    job = SimpleNamespace(
        status="running",
        generation_metadata_json={"batch": True, "phase": "running"},
        created_at=datetime.now(timezone.utc),
        id=uuid4(),
    )
    assert _never_started(job) is False
