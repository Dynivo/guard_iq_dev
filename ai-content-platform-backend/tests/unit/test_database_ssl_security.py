from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path

import pytest

from app.infrastructure.postgres import session as db_session


def test_production_rejects_unverified_database_tls(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(
        DATABASE_SSL="require-insecure",
        DATABASE_SSL_CA="",
        APP_ENV="production",
    )
    monkeypatch.setattr(db_session, "get_settings", lambda: settings)

    with pytest.raises(RuntimeError, match="not allowed in production"):
        db_session._ssl_context()


def test_default_database_tls_keeps_certificate_verification(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    settings = SimpleNamespace(
        DATABASE_SSL="require",
        DATABASE_SSL_CA="",
        APP_ENV="production",
    )
    monkeypatch.setattr(db_session, "get_settings", lambda: settings)
    monkeypatch.setattr(db_session, "_DEFAULT_RDS_CA", tmp_path / "missing.pem")

    context = db_session._ssl_context()

    assert context.check_hostname is True
