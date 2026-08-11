"""Capability Router domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


CAPABILITY_ALIASES: dict[str, str] = {
    "relevance": "relevance_scoring",
    "copywriting": "writing",
    "carousel_copy": "writing",
    "writing_from_plan": "writing",
    "image_prompt": "image_prompting",
    "preference_summary": "preference_learning",
}


def normalize_capability(name: str) -> str:
    key = name.strip().lower()
    return CAPABILITY_ALIASES.get(key, key)


@dataclass(frozen=True, slots=True)
class RetryConfig:
    max_attempts: int = 2
    strategy: str = "fixed_delay"
    delay_ms: int = 200
    max_delay_ms: int = 5_000


@dataclass(frozen=True, slots=True)
class ProviderTarget:
    provider: str
    model: str = ""


@dataclass(frozen=True, slots=True)
class CapabilityConfig:
    name: str
    provider: str
    model: str = ""
    model_id: str = ""
    temperature: float = 0.5
    max_tokens: int = 4096
    fallbacks: tuple[ProviderTarget, ...] = ()
    timeout_ms: int = 60_000
    retry: RetryConfig = field(default_factory=RetryConfig)
    cacheable: bool = True
    cache_ttl_seconds: int = 3_600
    sensitive: bool = False
    failure_threshold: int = 5
    recovery_timeout_ms: int = 30_000
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    capability: str
    primary: ProviderTarget
    fallbacks: tuple[ProviderTarget, ...]
    temperature: float
    max_tokens: int
    timeout_ms: int
    retry: RetryConfig
    cacheable: bool
    cache_ttl_seconds: int
    sensitive: bool
    failure_threshold: int
    recovery_timeout_ms: int
    source: str = "yaml"  # yaml | org_db | default
    model_id: str = ""
    context_window: int | None = None
