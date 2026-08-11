"""Mock speech providers for local/dev without Azure keys."""

from __future__ import annotations

from app.modules.capture.domain.ports import SynthesisResult, TranscriptionResult


class MockTranscriptionProvider:
    """Returns an editable placeholder transcript."""

    @property
    def name(self) -> str:
        return "mock"

    async def transcribe(
        self,
        audio_bytes: bytes,
        *,
        content_type: str = "audio/webm",
        locale: str | None = None,
    ) -> TranscriptionResult:
        _ = (audio_bytes, content_type)
        loc = locale or "en-GB"
        return TranscriptionResult(
            text=(
                "Mock transcript of your voice note. "
                "Edit this text to match what you said, then continue."
            ),
            locale=loc,
            provider=self.name,
            confidence=None,
        )


class MockSpeechSynthesisProvider:
    """Minimal silent-ish WAV so Hear draft works without Azure."""

    @property
    def name(self) -> str:
        return "mock"

    async def synthesize(
        self,
        text: str,
        *,
        locale: str | None = None,
        voice: str | None = None,
    ) -> SynthesisResult:
        _ = (text, locale, voice)
        # 0.3s of silence, 8-bit mono 8kHz WAV
        sample_rate = 8000
        duration_samples = int(sample_rate * 0.3)
        data_size = duration_samples
        header = bytearray()
        header.extend(b"RIFF")
        header.extend((36 + data_size).to_bytes(4, "little"))
        header.extend(b"WAVE")
        header.extend(b"fmt ")
        header.extend((16).to_bytes(4, "little"))
        header.extend((1).to_bytes(2, "little"))  # PCM
        header.extend((1).to_bytes(2, "little"))  # mono
        header.extend(sample_rate.to_bytes(4, "little"))
        header.extend(sample_rate.to_bytes(4, "little"))
        header.extend((1).to_bytes(2, "little"))
        header.extend((8).to_bytes(2, "little"))
        header.extend(b"data")
        header.extend(data_size.to_bytes(4, "little"))
        header.extend(bytes(data_size))
        return SynthesisResult(
            audio_bytes=bytes(header),
            content_type="audio/wav",
            provider=self.name,
        )
