"""Regression checks for the client-ready fresh-database seed."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from scripts.seed_database import DEFAULT_BRAND_EXTRA_SETTINGS, _admin_password
from scripts.seed_shailesh_guardiq_brand import SUPPLIED_LOGO_PATH


def test_fresh_seed_enables_two_automatic_images() -> None:
    assert DEFAULT_BRAND_EXTRA_SETTINGS["default_image_count"] == 2
    assert DEFAULT_BRAND_EXTRA_SETTINGS["auto_generate_image_with_draft"] is True


def test_fresh_seed_uses_the_supplied_guard_iq_logo() -> None:
    assert SUPPLIED_LOGO_PATH.is_file()
    assert SUPPLIED_LOGO_PATH.name == "guard_iq_logo.png"


def test_fresh_seed_rejects_a_missing_admin_password(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SEED_ADMIN_PASSWORD", raising=False)
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="SEED_ADMIN_PASSWORD"):
            _admin_password()
    finally:
        get_settings.cache_clear()


def test_fresh_seed_accepts_a_strong_admin_password(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "unique-test-password")
    get_settings.cache_clear()
    try:
        assert _admin_password() == "unique-test-password"
    finally:
        get_settings.cache_clear()
