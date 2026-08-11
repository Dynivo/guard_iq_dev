"""Unit tests for RBAC role hierarchy."""

from __future__ import annotations

from app.core.constants import MembershipRole
from app.core.security.rbac import _role_level


def test_role_hierarchy_ordering() -> None:
    assert _role_level(MembershipRole.VIEWER) < _role_level(MembershipRole.EDITOR)
    assert _role_level(MembershipRole.EDITOR) < _role_level(MembershipRole.OWNER)


def test_role_level_accepts_string() -> None:
    assert _role_level("editor") == _role_level(MembershipRole.EDITOR)


def test_unknown_role_is_below_viewer() -> None:
    assert _role_level("unknown") < _role_level(MembershipRole.VIEWER)
