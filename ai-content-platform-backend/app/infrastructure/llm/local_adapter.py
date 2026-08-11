"""Local / self-hosted LLM adapter — calls an OpenAI-compatible local endpoint."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator

import httpx

from app.core.logging import get_logger
from app.infrastructure.llm.base import CompletionRequest, CompletionResult
from app.shared.ai_types import StreamingUnsupportedError

logger = get_logger(__name__)


class LocalProvider:
    """Adapter for local/self-hosted models exposing an OpenAI-compatible API (e.g. Ollama, vLLM)."""

    def __init__(self, base_url: str = "http://localhost:11434/v1", api_key: str = "") -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    @property
    def provider_name(self) -> str:
        return "local"

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        messages = []
        if request.system_message:
            messages.append({"role": "system", "content": request.system_message})
        messages.append({"role": "user", "content": request.prompt})

        body: dict = {
            "model": request.model or "llama3",
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        start = time.perf_counter_ns()
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self._base_url}/chat/completions", headers=headers, json=body
            )
            resp.raise_for_status()

        latency_ms = (time.perf_counter_ns() - start) // 1_000_000
        data = resp.json()
        choice = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})

        logger.info("Local completion: model=%s latency=%dms", request.model, latency_ms)

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

