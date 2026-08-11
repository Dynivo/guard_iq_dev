"""Delivery auth helpers for media streaming."""

from __future__ import annotations

import uuid

import pytest

from app.api.routes.media import _assert_org_access
from app.core.constants import MembershipRole
from app.core.exceptions import AuthorizationError
from app.modules.auth.domain.entities import AuthenticatedUser


def _user(org_id: uuid.UUID | None = None) -> AuthenticatedUser:
    oid = org_id or uuid.uuid4()
    return AuthenticatedUser(
        user_id=uuid.uuid4(),
        email="a@b.c",
        display_name="A",
        organization_id=oid,
        role=MembershipRole.VIEWER,
    )


def test_org_prefix_allowed() -> None:
    user = _user()
    _assert_org_access(f"{user.organization_id}/images/x.png", user)


def test_foreign_org_denied() -> None:
    user = _user()
    other = uuid.uuid4()
    with pytest.raises(AuthorizationError):
        _assert_org_access(f"{other}/images/x.png", user)


def test_path_traversal_denied() -> None:
    user = _user()
    with pytest.raises(AuthorizationError):
        _assert_org_access(f"{user.organization_id}/../secret.png", user)
