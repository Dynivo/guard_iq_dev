"""OpenAI adapter — calls the chat completions endpoint via httpx."""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator

import httpx

from app.core.logging import get_logger
from app.infrastructure.llm.base import CompletionRequest, CompletionResult

logger = get_logger(__name__)

_BASE_URL = "https://api.openai.com/v1"


class OpenAIProvider:
    """OpenAI-compatible chat completions adapter."""

    def __init__(self, api_key: str, base_url: str = _BASE_URL) -> None:
        self._api_key = api_key
        self._base_url = base_url

    @property
    def provider_name(self) -> str:
        return "openai"

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
            "model": request.model or "gpt-4o-mini",
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.response_format == "json":
            body["response_format"] = {"type": "json_object"}

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
            "OpenAI completion: model=%s latency=%dms tokens_in=%d tokens_out=%d",
            request.model,
            latency_ms,
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0),
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
        import json
        from collections.abc import AsyncIterator as _AI  # noqa: F401
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        messages = []
        if request.system_message:
            messages.append({"role": "system", "content": request.system_message})
        messages.append({"role": "user", "content": request.prompt})
        body = {
            "model": request.model or "gpt-4o-mini",
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/chat/completions",
                headers=headers,
                json=body,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        data = json.loads(payload)
                        delta = data["choices"][0].get("delta", {}).get("content")
                        if delta:
                            yield delta
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
