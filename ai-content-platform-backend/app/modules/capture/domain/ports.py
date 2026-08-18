"""Speech transcription, synthesis, and translation ports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    text: str
    locale: str = "en-GB"
    provider: str = "azure"
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class SynthesisResult:
    audio_bytes: bytes
    content_type: str = "audio/mpeg"
    provider: str = "azure"


@dataclass(frozen=True, slots=True)
class TranslationResult:
    text: str
    source_language: str
    target_language: str
    translated: bool
    provider: str = "azure"
    original_text: str = ""


class TranscriptionProvider(Protocol):
    """Speech-to-text — voice note bytes → transcript."""

    @property
    def name(self) -> str: ...

    async def transcribe(
        self,
        audio_bytes: bytes,
        *,
        content_type: str = "audio/webm",
        locale: str | None = None,
    ) -> TranscriptionResult: ...


class SpeechSynthesisProvider(Protocol):
    """Text-to-speech — draft text → audio bytes."""

    @property
    def name(self) -> str: ...

    async def synthesize(
        self,
        text: str,
        *,
        locale: str | None = None,
        voice: str | None = None,
    ) -> SynthesisResult: ...


class TranslationProvider(Protocol):
    """Translate text into a target language when needed."""

    @property
    def name(self) -> str: ...

    async def translate_if_needed(
        self,
        text: str,
        *,
        target_language: str = "en",
    ) -> TranslationResult: ...
