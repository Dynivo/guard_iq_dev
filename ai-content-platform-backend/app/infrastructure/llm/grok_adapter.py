"""Grok (xAI) / Groq chat adapter — OpenAI-compatible via httpx.

Groq API keys (prefix ``gsk_``) are auto-routed to api.groq.com with a Llama model,
since those keys do not work against api.x.ai.
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import yaml

from app.core.logging import get_logger
from app.infrastructure.llm.base import CompletionRequest, CompletionResult

logger = get_logger(__name__)

_CONFIG = Path(__file__).resolve().parents[3] / "configs" / "providers" / "grok.yaml"
_GROQ_BASE = "https://api.groq.com/openai/v1"
_GROQ_DEFAULT_MODEL = "llama-3.3-70b-versatile"
_XAI_DEFAULT_MODEL = "grok-2-latest"


def _default_base_url() -> str:
    if _CONFIG.exists():
        data = yaml.safe_load(_CONFIG.read_text(encoding="utf-8")) or {}
        return str((data.get("base_url") or "https://api.x.ai/v1")).rstrip("/")
    return "https://api.x.ai/v1"


def _default_model() -> str:
    if _CONFIG.exists():
        data = yaml.safe_load(_CONFIG.read_text(encoding="utf-8")) or {}
        return str((data.get("defaults") or {}).get("model") or _XAI_DEFAULT_MODEL)
    return _XAI_DEFAULT_MODEL


def resolve_grok_endpoint(api_key: str, base_url: str | None = None) -> tuple[str, str]:
    """Return (base_url, default_model). Groq keys auto-route to Groq."""
    key = (api_key or "").strip()
    if key.startswith("gsk_"):
        return _GROQ_BASE, _GROQ_DEFAULT_MODEL
    return (base_url or _default_base_url()).rstrip("/"), _default_model()


class GrokProvider:
    """xAI Grok (or Groq-compatible) chat completions."""

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        *,
        default_model: str | None = None,
    ) -> None:
        resolved_base, resolved_model = resolve_grok_endpoint(api_key, base_url)
        self._api_key = api_key
        self._base_url = resolved_base
        self._default_model = default_model or resolved_model
        self._is_groq = "api.groq.com" in self._base_url

    @property
    def provider_name(self) -> str:
        return "grok"

    def _resolve_model(self, requested: str | None) -> str:
        model = (requested or "").strip() or self._default_model
        # Panel configs may still say grok-*; remap when talking to Groq
        if self._is_groq and (model.startswith("grok") or model == _XAI_DEFAULT_MODEL):
            return self._default_model
        return model

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        messages: list[dict[str, Any]] = []
        if request.system_message:
            messages.append({"role": "system", "content": request.system_message})
        messages.append({"role": "user", "content": request.prompt})
        model = self._resolve_model(request.model)
        body: dict[str, Any] = {
            "model": model,
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
            data = resp.json()

        latency_ms = (time.perf_counter_ns() - start) // 1_000_000
        choice = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        logger.info(
            "Grok completion: backend=%s model=%s latency=%dms tokens_in=%d tokens_out=%d",
            "groq" if self._is_groq else "xai",
            model,
            latency_ms,
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0),
        )
        return CompletionResult(
            text=choice,
            model=data.get("model", model),
            provider=self.provider_name,
            latency_ms=latency_ms,
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
            cost_estimate=0.0,
            raw_response=data,
        )

    async def complete_stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        messages: list[dict[str, Any]] = []
        if request.system_message:
            messages.append({"role": "system", "content": request.system_message})
        messages.append({"role": "user", "content": request.prompt})
        model = self._resolve_model(request.model)
        body = {
            "model": model,
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
