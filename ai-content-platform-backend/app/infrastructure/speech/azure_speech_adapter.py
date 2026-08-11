"""Azure Cognitive Services Speech — STT + TTS via REST."""

from __future__ import annotations

import xml.sax.saxutils as xml_escape

import httpx

from app.core.exceptions import ValidationError
from app.core.logging import get_logger
from app.modules.capture.domain.ports import SynthesisResult, TranscriptionResult

logger = get_logger(__name__)

_DEFAULT_VOICE = {
    "en-GB": "en-GB-SoniaNeural",
    "en-US": "en-US-JennyNeural",
    "en-IN": "en-IN-NeerjaNeural",
    "hi-IN": "hi-IN-SwaraNeural",
}


def _stt_url(region: str, locale: str, endpoint: str | None = None) -> str:
    _ = endpoint
    return (
        f"https://{region}.stt.speech.microsoft.com/"
        f"speech/recognition/conversation/cognitiveservices/v1"
        f"?language={locale}&format=detailed"
    )


def _tts_url(region: str, endpoint: str | None = None) -> str:
    _ = endpoint
    return f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"


def _normalize_stt_content_type(content_type: str) -> str:
    """Map browser MIME types to ones Azure Short Audio REST accepts."""
    raw = (content_type or "audio/wav").strip().lower()
    if raw.startswith("audio/wav") or raw.startswith("audio/x-wav") or raw.startswith("audio/wave"):
        return "audio/wav"
    if "ogg" in raw:
        return "audio/ogg; codecs=opus"
    if "webm" in raw:
        if "codecs" in raw:
            return content_type.strip()
        return "audio/webm; codecs=opus"
    if "mpeg" in raw or "mp3" in raw:
        return "audio/mpeg"
    if "mp4" in raw or "m4a" in raw:
        return "audio/mp4"
    return content_type.strip() or "audio/wav"


class AzureSpeechTranscriptionProvider:
    """Azure Speech-to-Text (conversation recognition REST)."""

    def __init__(
        self,
        *,
        api_key: str,
        region: str,
        locale: str = "en-IN",
        endpoint: str | None = None,
    ) -> None:
        if not api_key or not region:
            raise ValidationError("Azure Speech key and region are required")
        self._key = api_key.strip()
        self._region = region.strip()
        self._locale = locale.strip() or "en-IN"
        self._endpoint = (endpoint or "").strip() or None

    @property
    def name(self) -> str:
        return "azure"

    async def transcribe(
        self,
        audio_bytes: bytes,
        *,
        content_type: str = "audio/webm",
        locale: str | None = None,
    ) -> TranscriptionResult:
        if not audio_bytes:
            raise ValidationError("Audio is empty")
        if len(audio_bytes) < 256:
            raise ValidationError("Recording too short — speak for at least 1–2 seconds.")
        loc = (locale or self._locale).strip()
        url = _stt_url(self._region, loc, self._endpoint)
        # Detect WAV by magic bytes even if multipart Content-Type is wrong
        if audio_bytes[:4] == b"RIFF":
            mime = "audio/wav"
        else:
            mime = _normalize_stt_content_type(content_type)
        headers = {
            "Ocp-Apim-Subscription-Key": self._key,
            "Content-Type": mime,
            "Accept": "application/json",
        }
        logger.info(
            "Azure STT request bytes=%s content_type=%s locale=%s",
            len(audio_bytes),
            mime,
            loc,
        )
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, content=audio_bytes, headers=headers)
        if response.status_code >= 400:
            logger.warning(
                "Azure STT failed status=%s body=%s",
                response.status_code,
                response.text[:400],
            )
            raise ValidationError(
                f"Speech transcription failed ({response.status_code}). "
                "Try again or type your story instead."
            )
        payload = response.json()
        status = str(payload.get("RecognitionStatus") or "")
        text = (payload.get("DisplayText") or "").strip()
        if not text and isinstance(payload.get("NBest"), list) and payload["NBest"]:
            text = str(payload["NBest"][0].get("Display") or "").strip()
        if not text:
            logger.warning(
                "Azure STT empty transcript status=%s body=%s",
                status,
                response.text[:400],
            )
            if status in ("InitialSilenceTimeout", "NoMatch", "BabbleTimeout"):
                raise ValidationError(
                    f"Azure heard no clear speech ({status}). "
                    "Speak closer to the mic for 2+ seconds, then try again."
                )
            raise ValidationError(
                "Could not understand the audio. Try again or type your story."
            )
        confidence = None
        if isinstance(payload.get("NBest"), list) and payload["NBest"]:
            conf = payload["NBest"][0].get("Confidence")
            if conf is not None:
                confidence = float(conf)
        return TranscriptionResult(
            text=text,
            locale=loc,
            provider=self.name,
            confidence=confidence,
        )


class AzureSpeechSynthesisProvider:
    """Azure Text-to-Speech REST (SSML → mp3)."""

    def __init__(
        self,
        *,
        api_key: str,
        region: str,
        locale: str = "en-IN",
        endpoint: str | None = None,
    ) -> None:
        if not api_key or not region:
            raise ValidationError("Azure Speech key and region are required")
        self._key = api_key.strip()
        self._region = region.strip()
        self._locale = locale.strip() or "en-IN"
        self._endpoint = (endpoint or "").strip() or None

    @property
    def name(self) -> str:
        return "azure"

    async def synthesize(
        self,
        text: str,
        *,
        locale: str | None = None,
        voice: str | None = None,
    ) -> SynthesisResult:
        cleaned = (text or "").strip()
        if not cleaned:
            raise ValidationError("Nothing to speak")
        cleaned = cleaned[:4500]
        loc = (locale or self._locale).strip()
        voice_name = voice or _DEFAULT_VOICE.get(loc) or "en-IN-NeerjaNeural"
        if loc.startswith("en-") and loc not in _DEFAULT_VOICE:
            voice_name = voice or "en-IN-NeerjaNeural"
        escaped = xml_escape.escape(cleaned)
        ssml = (
            f'<speak version="1.0" xml:lang="{loc}">'
            f'<voice name="{voice_name}">{escaped}</voice></speak>'
        )
        url = _tts_url(self._region, self._endpoint)
        headers = {
            "Ocp-Apim-Subscription-Key": self._key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-16khz-128kbitrate-mono-mp3",
            "User-Agent": "AIContentPlatform",
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, content=ssml.encode("utf-8"), headers=headers)
        if response.status_code >= 400:
            logger.warning(
                "Azure TTS failed status=%s body=%s",
                response.status_code,
                response.text[:400],
            )
            raise ValidationError(f"Speech synthesis failed ({response.status_code}).")
        return SynthesisResult(
            audio_bytes=response.content,
            content_type="audio/mpeg",
            provider=self.name,
        )
