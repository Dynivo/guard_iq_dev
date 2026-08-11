"""Perplexity adapter — OpenAI-compatible chat API via httpx."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator

import httpx

from app.core.logging import get_logger
from app.infrastructure.llm.base import CompletionRequest, CompletionResult
from app.shared.ai_types import StreamingUnsupportedError

logger = get_logger(__name__)

_BASE_URL = "https://api.perplexity.ai"


class PerplexityProvider:
    """Perplexity chat completions adapter (OpenAI-compatible wire format)."""

    def __init__(self, api_key: str, base_url: str = _BASE_URL) -> None:
        self._api_key = api_key
        self._base_url = base_url

    @property
    def provider_name(self) -> str:
        return "perplexity"

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        messages = []
        if request.system_message:
            messages.append({"role": "system", "content": request.system_message})
        messages.append({"role": "user", "content": request.prompt})

        body: dict = {
            "model": request.model or "sonar",
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        start = time.perf_counter_ns()
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self._base_url}/chat/completions", headers=headers, json=body
            )
            resp.raise_for_status()

        latency_ms = (time.perf_counter_ns() - start) // 1_000_000
        data = resp.json()
        choice = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})

        logger.info(
            "Perplexity completion: model=%s latency=%dms",
            request.model,
            latency_ms,
        )

        return CompletionResult(
            text=choice,
            model=data.get("model", request.model),
            provider=self.provider_name,
            latency_ms=latency_ms,
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
            cost_estimate=0.0,
            raw_response=data,
        )

    async def complete_stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        raise StreamingUnsupportedError(self.provider_name)
        yield  # pragma: no cover — make this an async generator

