"""Unit tests for mock speech + translator providers."""

from __future__ import annotations

import pytest

from app.infrastructure.speech.azure_translator_adapter import MockTranslationProvider
from app.infrastructure.speech.mock import (
    MockSpeechSynthesisProvider,
    MockTranscriptionProvider,
)
from app.infrastructure.speech.factory import _is_azure, _speech_locale


@pytest.mark.asyncio
async def test_mock_transcribe_returns_editable_text() -> None:
    provider = MockTranscriptionProvider()
    result = await provider.transcribe(b"fake-audio", content_type="audio/webm")
    assert result.provider == "mock"
    assert "Mock transcript" in result.text


@pytest.mark.asyncio
async def test_mock_synthesize_returns_wav_bytes() -> None:
    provider = MockSpeechSynthesisProvider()
    result = await provider.synthesize("Hello LinkedIn")
    assert result.provider == "mock"
    assert result.content_type == "audio/wav"
    assert result.audio_bytes[:4] == b"RIFF"


@pytest.mark.asyncio
async def test_mock_translate_passthrough() -> None:
    provider = MockTranslationProvider()
    result = await provider.translate_if_needed("hello", target_language="en")
    assert result.translated is False
    assert result.text == "hello"


def test_azure_alias_normalization() -> None:
    assert _is_azure("azure")
    assert _is_azure("azure_speech")
    assert not _is_azure("mock")


def test_speech_locale_strips_inline_comments() -> None:
    class S:
        AZURE_SPEECH_RECO_LANGUAGE = "en-IN   # or hi-IN"
        AZURE_SPEECH_LOCALE = "en-GB"

    assert _speech_locale(S()) == "en-IN"
