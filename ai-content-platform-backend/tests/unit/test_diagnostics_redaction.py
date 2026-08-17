"""The diagnostics bundle is meant to be emailed to the agency, so anything
secret inside it is disclosed. These pin the redaction of credentials that
were observed leaking into the on-disk log."""

from __future__ import annotations

import pytest

from app.modules.jobs.application import use_cases


class _FakeSettings:
    GEMINI_API_KEY = "AQ.Ab8RN6KaTESTKEYvalue1234567890"
    OPENAI_API_KEY = ""
    JWT_SECRET_KEY = "super-secret-jwt-signing-value-xyz"
    DATABASE_URL = "postgresql+asyncpg://appuser:hunter2pass@localhost:5432/db"

    def __getattr__(self, name: str) -> str:  # any other secret setting -> empty
        return ""


@pytest.fixture(autouse=True)
def _settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(use_cases, "get_settings", lambda: _FakeSettings(), raising=False)
    import app.core.config as cfg

    monkeypatch.setattr(cfg, "get_settings", lambda: _FakeSettings())


def test_redacts_api_key_from_logged_request_url() -> None:
    """Google's SDK logs the full URL, putting the key in the query string."""
    line = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-flash-latest:generateContent?key=AQ.Ab8RN6KaTESTKEYvalue1234567890"
    )
    out = use_cases._redact_secrets(line)
    assert "AQ.Ab8RN6KaTESTKEYvalue1234567890" not in out
    assert "redacted" in out


def test_redacts_unknown_key_in_query_string() -> None:
    """A per-source key we never held in settings must still be scrubbed."""
    out = use_cases._redact_secrets("GET /v1/news?api_key=abcdef123456SECRET&q=cyber")
    assert "abcdef123456SECRET" not in out
    assert "q=cyber" in out


def test_redacts_jwt_secret_and_database_url() -> None:
    text = "signing with super-secret-jwt-signing-value-xyz on postgresql+asyncpg://appuser:hunter2pass@localhost:5432/db"
    out = use_cases._redact_secrets(text)
    assert "super-secret-jwt-signing-value-xyz" not in out
    assert "hunter2pass" not in out


def test_leaves_ordinary_log_text_alone() -> None:
    text = 'SELECT users.password_hash FROM users WHERE id = 1'
    assert use_cases._redact_secrets(text) == text
