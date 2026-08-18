"""Load capability → provider map from YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.modules.providers.domain.models import (
    CapabilityConfig,
    ProviderTarget,
    RetryConfig,
    normalize_capability,
)

_CONFIGS_DIR = Path(__file__).resolve().parents[4] / "configs"


class YamlCapabilityConfigLoader:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _CONFIGS_DIR / "providers" / "default.yaml"
        self._capabilities: dict[str, CapabilityConfig] = {}
        self.reload()

    def reload(self) -> None:
        self._capabilities = {}
        if not self._path.exists():
            return
        data = yaml.safe_load(self._path.read_text(encoding="utf-8")) or {}
        raw = data.get("capabilities") or {}
        for name, item in raw.items():
            # Store under the literal capability key. Aliases are resolved in get()
            # so secondary keys (copywriting → writing) cannot overwrite primary config.
            key = str(name).strip().lower()
            self._capabilities[key] = self._parse(name, item or {})

    def get(self, capability: str) -> CapabilityConfig | None:
        key = str(capability).strip().lower()
        if key in self._capabilities:
            return self._capabilities[key]
        canonical = normalize_capability(capability)
        return self._capabilities.get(canonical)

    def all(self) -> dict[str, CapabilityConfig]:
        return dict(self._capabilities)

    def _parse(self, name: str, item: dict[str, Any]) -> CapabilityConfig:
        retry_raw = item.get("retry") or {}
        fallbacks_raw = item.get("fallbacks") or []
        fallbacks = tuple(
            ProviderTarget(
                provider=str(f.get("provider") or ""),
                model=str(f.get("model") or ""),
            )
            for f in fallbacks_raw
            if str(f.get("provider") or "").strip().lower() not in {"", "mock"}
        )
        provider = str(item.get("provider") or "gemini").strip().lower()
        if provider == "mock":
            raise ValueError(f"Capability '{name}' uses the removed mock provider")
        return CapabilityConfig(
            name=normalize_capability(name),
            provider=provider,
            model=str(item.get("model") or ""),
            model_id=str(item.get("model_id") or ""),
            temperature=float(item.get("temperature", 0.5)),
            max_tokens=int(item.get("max_tokens", 4096)),
            fallbacks=fallbacks,
            timeout_ms=int(item.get("timeout_ms", 60_000)),
            retry=RetryConfig(
                max_attempts=int(retry_raw.get("max_attempts", 2)),
                strategy=str(retry_raw.get("strategy", "fixed_delay")),
                delay_ms=int(retry_raw.get("delay_ms", 200)),
                max_delay_ms=int(retry_raw.get("max_delay_ms", 5_000)),
            ),
            cacheable=bool(item.get("cacheable", True)),
            cache_ttl_seconds=int(item.get("cache_ttl_seconds", 3_600)),
            sensitive=bool(item.get("sensitive", False)),
            failure_threshold=int(item.get("failure_threshold", 5)),
            recovery_timeout_ms=int(item.get("recovery_timeout_ms", 30_000)),
            extra={k: v for k, v in item.items() if k not in {
                "provider", "model", "model_id", "temperature", "max_tokens", "fallbacks",
                "timeout_ms", "retry", "cacheable", "cache_ttl_seconds", "sensitive",
                "failure_threshold", "recovery_timeout_ms",
            }},
        )
