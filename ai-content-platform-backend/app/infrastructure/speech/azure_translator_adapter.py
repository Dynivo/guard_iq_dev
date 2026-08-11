"""Azure Translator — detect language and translate only when needed."""

from __future__ import annotations

import uuid

import httpx

from app.core.exceptions import ValidationError
from app.core.logging import get_logger
from app.modules.capture.domain.ports import TranslationResult

logger = get_logger(__name__)


class MockTranslationProvider:
    """Pass-through when Translator is not configured."""

    @property
    def name(self) -> str:
        return "mock"

    async def translate_if_needed(
        self,
        text: str,
        *,
        target_language: str = "en",
    ) -> TranslationResult:
        return TranslationResult(
            text=text,
            source_language=target_language,
            target_language=target_language,
            translated=False,
            provider=self.name,
            original_text=text,
        )


class AzureTranslatorProvider:
    """Azure Cognitive Services Translator v3."""

    def __init__(
        self,
        *,
        api_key: str,
        region: str,
        endpoint: str = "https://api.cognitive.microsofttranslator.com",
    ) -> None:
        if not api_key:
            raise ValidationError("Azure Translator key is required")
        self._key = api_key.strip()
        self._region = (region or "").strip()
        self._endpoint = (endpoint or "https://api.cognitive.microsofttranslator.com").rstrip("/")

    @property
    def name(self) -> str:
        return "azure"

    async def translate_if_needed(
        self,
        text: str,
        *,
        target_language: str = "en",
    ) -> TranslationResult:
        cleaned = (text or "").strip()
        if not cleaned:
            return TranslationResult(
                text="",
                source_language=target_language,
                target_language=target_language,
                translated=False,
                provider=self.name,
                original_text="",
            )

        target = (target_language or "en").split("-")[0].lower()
        headers = {
            "Ocp-Apim-Subscription-Key": self._key,
            "Content-Type": "application/json",
            "X-ClientTraceId": str(uuid.uuid4()),
        }
        if self._region:
            headers["Ocp-Apim-Subscription-Region"] = self._region

        # Detect language first
        detect_url = f"{self._endpoint}/detect?api-version=3.0"
        async with httpx.AsyncClient(timeout=30.0) as client:
            detect_resp = await client.post(
                detect_url, headers=headers, json=[{"Text": cleaned[:5000]}]
            )
            if detect_resp.status_code >= 400:
                logger.warning(
                    "Azure detect failed status=%s body=%s",
                    detect_resp.status_code,
                    detect_resp.text[:300],
                )
                # Fail open — keep original text
                return TranslationResult(
                    text=cleaned,
                    source_language="unknown",
                    target_language=target,
                    translated=False,
                    provider=self.name,
                    original_text=cleaned,
                )
            detected = detect_resp.json()
            source = "unknown"
            if isinstance(detected, list) and detected:
                source = str(detected[0].get("language") or "unknown").lower()

            source_base = source.split("-")[0]
            if source_base == target:
                return TranslationResult(
                    text=cleaned,
                    source_language=source,
                    target_language=target,
                    translated=False,
                    provider=self.name,
                    original_text=cleaned,
                )

            translate_url = (
                f"{self._endpoint}/translate?api-version=3.0"
                f"&from={source_base}&to={target}"
            )
            tr_resp = await client.post(
                translate_url, headers=headers, json=[{"Text": cleaned[:5000]}]
            )
            if tr_resp.status_code >= 400:
                logger.warning(
                    "Azure translate failed status=%s body=%s",
                    tr_resp.status_code,
                    tr_resp.text[:300],
                )
                raise ValidationError(
                    f"Translation failed ({tr_resp.status_code}). "
                    "Edit the transcript manually or retry."
                )
            payload = tr_resp.json()
            translated_text = cleaned
            if isinstance(payload, list) and payload:
                translations = payload[0].get("translations") or []
                if translations:
                    translated_text = str(translations[0].get("text") or cleaned).strip()

        return TranslationResult(
            text=translated_text,
            source_language=source,
            target_language=target,
            translated=translated_text != cleaned,
            provider=self.name,
            original_text=cleaned,
        )
