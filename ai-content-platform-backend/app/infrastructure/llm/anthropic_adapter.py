"""Anthropic adapter — calls the messages endpoint via httpx."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator

import httpx

from app.core.logging import get_logger
from app.infrastructure.llm.base import CompletionRequest, CompletionResult
from app.shared.ai_types import StreamingUnsupportedError

logger = get_logger(__name__)

_BASE_URL = "https://api.anthropic.com/v1"


class AnthropicProvider:
    """Anthropic messages API adapter."""

    def __init__(self, api_key: str, base_url: str = _BASE_URL) -> None:
        self._api_key = api_key
        self._base_url = base_url

    @property
    def provider_name(self) -> str:
        return "anthropic"

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        body: dict = {
            "model": request.model or "claude-sonnet-4-20250514",
            "max_tokens": request.max_tokens,
            "messages": [{"role": "user", "content": request.prompt}],
        }
        if request.system_message:
            body["system"] = request.system_message

        start = time.perf_counter_ns()
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self._base_url}/messages", headers=headers, json=body
            )
            resp.raise_for_status()

        latency_ms = (time.perf_counter_ns() - start) // 1_000_000
        data = resp.json()
        text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
        output_text = "\n".join(text_blocks)
        usage = data.get("usage", {})

        logger.info(
            "Anthropic completion: model=%s latency=%dms",
            request.model,
            latency_ms,
        )

        return CompletionResult(
            text=output_text,
            model=data.get("model", request.model),
            provider=self.provider_name,
            latency_ms=latency_ms,
            tokens_in=usage.get("input_tokens", 0),
            tokens_out=usage.get("output_tokens", 0),
            cost_estimate=0.0,
            raw_response=data,
        )

    async def complete_stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        raise StreamingUnsupportedError(self.provider_name)
        yield  # pragma: no cover — make this an async generator

