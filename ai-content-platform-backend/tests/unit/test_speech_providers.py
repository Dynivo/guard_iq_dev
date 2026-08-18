"""Unit tests for speech provider configuration."""

from __future__ import annotations

import pytest

from app.infrastructure.speech.factory import (
    _is_azure,
    _speech_locale,
    get_speech_synthesis_provider,
    get_transcription_provider,
    get_translation_provider,
)


def test_azure_alias_normalization() -> None:
    assert _is_azure("azure")
    assert _is_azure("azure_speech")
    assert not _is_azure("mock")


def test_speech_requires_azure_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STT_PROVIDER", "azure")
    monkeypatch.setenv("TTS_PROVIDER", "azure")
    monkeypatch.setenv("AZURE_SPEECH_KEY", "")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="Azure Speech is not configured"):
            get_transcription_provider()
        with pytest.raises(RuntimeError, match="Azure Speech is not configured"):
            get_speech_synthesis_provider()
    finally:
        get_settings.cache_clear()


def test_translation_requires_azure_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSLATE_PROVIDER", "azure")
    monkeypatch.setenv("AZURE_TRANSLATOR_KEY", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="Azure Translator is not configured"):
            get_translation_provider()
    finally:
        get_settings.cache_clear()


def test_speech_locale_strips_inline_comments() -> None:
    class S:
        AZURE_SPEECH_RECO_LANGUAGE = "en-IN   # or hi-IN"
        AZURE_SPEECH_LOCALE = "en-GB"

    assert _speech_locale(S()) == "en-IN"
