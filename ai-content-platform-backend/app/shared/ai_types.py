"""Canonical AI completion types — shared, no infrastructure coupling."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Protocol


class StreamingUnsupportedError(Exception):
    """Raised when a provider cannot stream completions."""

    def __init__(self, provider: str, message: str = "") -> None:
        self.provider = provider
        super().__init__(message or f"Streaming unsupported for provider '{provider}'")


@dataclass
class CompletionRequest:
    """Canonical input to any LLM provider."""

    prompt: str
    model: str = ""
    temperature: float = 0.5
    max_tokens: int = 4096
    system_message: str = ""
    response_format: str = "json"
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class CompletionResult:
    """Canonical output from any LLM provider."""

    text: str
    model: str
    provider: str
    latency_ms: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_estimate: float = 0.0
    raw_response: dict | None = None
    cache_hit: bool = False
    retries: int = 0


class AIProvider(Protocol):
    """Protocol that all LLM adapters implement."""

    @property
    def provider_name(self) -> str: ...

    async def complete(self, request: CompletionRequest) -> CompletionResult: ...

    async def complete_stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        """Yield text chunks. Default adapters may raise StreamingUnsupportedError."""
        ...
