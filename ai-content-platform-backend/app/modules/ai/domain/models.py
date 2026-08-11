"""AI Orchestrator domain models."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from app.shared.ai_types import CompletionResult


@dataclass
class OrchestratorRequest:
    capability: str
    prompt: str
    organization_id: uuid.UUID | None = None
    correlation_id: str = ""
    system_message: str = ""
    response_format: str = "json"
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    prompt_version: str = ""
    bypass_cache: bool = False
    allow_nonstream_fallback: bool = True
    provider_override: str | None = None
    skip_fallbacks: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OrchestratorResult:
    success: bool
    result: CompletionResult | None = None
    capability: str = ""
    provider: str = ""
    model: str = ""
    cache_hit: bool = False
    retries: int = 0
    error_code: str | None = None
    error_message: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StreamChunk:
    text: str
    done: bool = False
    provider: str = ""
    model: str = ""
