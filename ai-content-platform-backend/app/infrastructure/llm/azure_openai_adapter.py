"""Azure OpenAI chat adapter — deployment completions via httpx."""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.logging import get_logger
from app.infrastructure.llm.base import CompletionRequest, CompletionResult

logger = get_logger(__name__)


class AzureOpenAIProvider:
    """Azure OpenAI chat completions against a named deployment."""

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        api_version: str,
        deployment: str,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._api_key = api_key
        self._api_version = api_version
        self._deployment = deployment

    @property
    def provider_name(self) -> str:
        return "azure_openai"

    def _url(self) -> str:
        return (
            f"{self._endpoint}/openai/deployments/{self._deployment}/chat/completions"
            f"?api-version={self._api_version}"
        )

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        headers = {
            "api-key": self._api_key,
            "Content-Type": "application/json",
        }
        messages: list[dict[str, Any]] = []
        if request.system_message:
            messages.append({"role": "system", "content": request.system_message})
        messages.append({"role": "user", "content": request.prompt})
        # Azure uses deployment in URL; model field is optional / ignored by many deployments
        body: dict[str, Any] = {
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.model:
            body["model"] = request.model
        if request.response_format == "json":
            body["response_format"] = {"type": "json_object"}

        start = time.perf_counter_ns()
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(self._url(), headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()

        latency_ms = (time.perf_counter_ns() - start) // 1_000_000
        choice = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        logger.info(
            "Azure OpenAI completion: deployment=%s latency=%dms tokens_in=%d tokens_out=%d",
            self._deployment,
            latency_ms,
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0),
        )
        return CompletionResult(
            text=choice,
            model=data.get("model", request.model or self._deployment),
            provider=self.provider_name,
            latency_ms=latency_ms,
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
            cost_estimate=0.0,
            raw_response=data,
        )

    async def complete_stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        headers = {
            "api-key": self._api_key,
            "Content-Type": "application/json",
        }
        messages: list[dict[str, Any]] = []
        if request.system_message:
            messages.append({"role": "system", "content": request.system_message})
        messages.append({"role": "user", "content": request.prompt})
        body: dict[str, Any] = {
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST", self._url(), headers=headers, json=body
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
