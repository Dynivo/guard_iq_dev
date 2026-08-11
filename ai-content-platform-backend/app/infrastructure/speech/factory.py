"""Factories for STT, TTS, and Translator providers."""

from __future__ import annotations

from app.core.config import get_settings
from app.core.logging import get_logger
from app.infrastructure.speech.mock import (
    MockSpeechSynthesisProvider,
    MockTranscriptionProvider,
)
from app.infrastructure.speech.azure_translator_adapter import MockTranslationProvider
from app.modules.capture.domain.ports import (
    SpeechSynthesisProvider,
    TranscriptionProvider,
    TranslationProvider,
)

logger = get_logger(__name__)

_AZURE_ALIASES = frozenset({"azure", "azure_speech"})


def _is_azure(name: str | None) -> bool:
    return (name or "").strip().lower() in _AZURE_ALIASES


def _is_mock(name: str | None) -> bool:
    return (name or "").strip().lower() in {"", "mock", "none", "off"}


def _speech_locale(settings) -> str:
    # Prefer recognition language; strip accidental inline comments from .env
    raw = (
        settings.AZURE_SPEECH_RECO_LANGUAGE
        or settings.AZURE_SPEECH_LOCALE
        or "en-IN"
    )
    return str(raw).split("#")[0].strip() or "en-IN"


def _want_azure_stt(settings) -> bool:
    # STT_PROVIDER preferred; TRANSCRIPTION_PROVIDER is legacy alias
    explicit = settings.STT_PROVIDER or settings.TRANSCRIPTION_PROVIDER or ""
    if _is_mock(explicit) and not settings.AZURE_SPEECH_KEY:
        return False
    if _is_azure(explicit):
        return bool(settings.AZURE_SPEECH_KEY and settings.AZURE_SPEECH_REGION)
    # Auto: keys present and not explicitly mock
    if settings.AZURE_SPEECH_KEY and settings.AZURE_SPEECH_REGION and not _is_mock(explicit):
        return True
    return False


def _want_azure_tts(settings) -> bool:
    explicit = settings.TTS_PROVIDER or settings.STT_PROVIDER or settings.TRANSCRIPTION_PROVIDER or ""
    if _is_mock(explicit) and not settings.AZURE_SPEECH_KEY:
        return False
    if _is_azure(explicit):
        return bool(settings.AZURE_SPEECH_KEY and settings.AZURE_SPEECH_REGION)
    if settings.AZURE_SPEECH_KEY and settings.AZURE_SPEECH_REGION and not _is_mock(explicit):
        return True
    return False


def _want_azure_translate(settings) -> bool:
    explicit = settings.TRANSLATE_PROVIDER or ""
    if _is_mock(explicit) and not settings.AZURE_TRANSLATOR_KEY:
        return False
    if _is_azure(explicit):
        return bool(settings.AZURE_TRANSLATOR_KEY)
    if settings.AZURE_TRANSLATOR_KEY and not _is_mock(explicit):
        return True
    return False


def get_transcription_provider() -> TranscriptionProvider:
    """Resolve STT provider fresh each call (avoids stale mock after .env change)."""
    settings = get_settings()
    if _want_azure_stt(settings):
        from app.infrastructure.speech.azure_speech_adapter import (
            AzureSpeechTranscriptionProvider,
        )

        locale = _speech_locale(settings)
        logger.info(
            "Using Azure STT region=%s locale=%s",
            settings.AZURE_SPEECH_REGION,
            locale,
        )
        return AzureSpeechTranscriptionProvider(
            api_key=settings.AZURE_SPEECH_KEY,
            region=settings.AZURE_SPEECH_REGION,
            locale=locale,
            endpoint=settings.AZURE_SPEECH_ENDPOINT or None,
        )
    logger.warning(
        "Using mock STT (set STT_PROVIDER=azure + AZURE_SPEECH_KEY/REGION). "
        "stt=%s transcription=%s key=%s",
        settings.STT_PROVIDER,
        settings.TRANSCRIPTION_PROVIDER,
        bool(settings.AZURE_SPEECH_KEY),
    )
    return MockTranscriptionProvider()


def get_speech_synthesis_provider() -> SpeechSynthesisProvider:
    settings = get_settings()
    if _want_azure_tts(settings):
        from app.infrastructure.speech.azure_speech_adapter import AzureSpeechSynthesisProvider

        locale = _speech_locale(settings)
        return AzureSpeechSynthesisProvider(
            api_key=settings.AZURE_SPEECH_KEY,
            region=settings.AZURE_SPEECH_REGION,
            locale=locale,
            endpoint=settings.AZURE_SPEECH_ENDPOINT or None,
        )
    return MockSpeechSynthesisProvider()


def get_translation_provider() -> TranslationProvider:
    settings = get_settings()
    if _want_azure_translate(settings):
        from app.infrastructure.speech.azure_translator_adapter import AzureTranslatorProvider

        logger.info(
            "Using Azure Translator region=%s",
            settings.AZURE_TRANSLATOR_REGION or "(none)",
        )
        return AzureTranslatorProvider(
            api_key=settings.AZURE_TRANSLATOR_KEY,
            region=settings.AZURE_TRANSLATOR_REGION,
            endpoint=settings.AZURE_TRANSLATOR_ENDPOINT
            or "https://api.cognitive.microsofttranslator.com",
        )
    return MockTranslationProvider()


def clear_speech_provider_cache() -> None:
    """Kept for callers; providers are no longer process-cached."""
    from app.core.config.settings import get_settings as _gs

    _gs.cache_clear()
