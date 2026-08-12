"""Google Gemini adapter — calls generativeLanguage REST API via httpx."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator

import httpx

from app.core.logging import get_logger
from app.infrastructure.llm.base import CompletionRequest, CompletionResult
from app.shared.ai_types import StreamingUnsupportedError

logger = get_logger(__name__)

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider:
    """Google Gemini generativeLanguage adapter."""

    def __init__(self, api_key: str, base_url: str = _BASE_URL) -> None:
        self._api_key = api_key
        self._base_url = base_url

    @property
    def provider_name(self) -> str:
        return "gemini"

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        model = request.model or "gemini-flash-latest"
        url = f"{self._base_url}/models/{model}:generateContent?key={self._api_key}"

        parts = []
        if request.system_message:
            parts.append({"text": f"[System]: {request.system_message}\n\n{request.prompt}"})
        else:
            parts.append({"text": request.prompt})

        body = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
                # Newer Gemini models (e.g. gemini-3.6-flash under the
                # "gemini-flash-latest" alias) default to "thinking" — internal
                # reasoning tokens that count against maxOutputTokens. For short
                # structured-output capabilities (JSON extraction, short labels,
                # scoring) that reasoning can consume the entire budget before
                # any visible answer is written, hitting MAX_TOKENS with an
                # empty response. thinkingBudget must be >=1 (0 is rejected by
                # the API); 1 effectively disables it for these use cases.
                "thinkingConfig": {"thinkingBudget": 1},
            },
        }
        if request.response_format == "json":
            body["generationConfig"]["responseMimeType"] = "application/json"

        start = time.perf_counter_ns()
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=body)
            resp.raise_for_status()

        latency_ms = (time.perf_counter_ns() - start) // 1_000_000
        data = resp.json()

        candidates = data.get("candidates", [])
        text = ""
        if candidates:
            parts_out = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts_out)

        usage = data.get("usageMetadata", {})
        tokens_in = usage.get("promptTokenCount", 0)
        tokens_out = usage.get("candidatesTokenCount", 0)

        logger.info(
            "Gemini completion: model=%s latency=%dms tokens_in=%d tokens_out=%d",
            model,
            latency_ms,
            tokens_in,
            tokens_out,
        )

        return CompletionResult(
            text=text,
            model=model,
            provider=self.provider_name,
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_estimate=0.0,
            raw_response=data,
        )

    async def complete_stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        raise StreamingUnsupportedError(self.provider_name)
        yield  # pragma: no cover — make this an async generator

