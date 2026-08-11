"""Unit tests for org-scoped draft repository helpers."""

from __future__ import annotations

import uuid

from app.modules.content.infrastructure.repositories import PgDraftRepository


def test_get_by_id_signature_accepts_org_id() -> None:
    """Regression: get_by_id must accept org_id to prevent IDOR."""
    import inspect

    sig = inspect.signature(PgDraftRepository.get_by_id)
    params = list(sig.parameters.keys())
    assert "org_id" in params
    assert "draft_id" in params


def test_org_uuid_format_for_media_prefix() -> None:
    org_id = uuid.uuid4()
    key = f"{org_id}/images/{uuid.uuid4()}.png"
    assert key.startswith(f"{org_id}/")
