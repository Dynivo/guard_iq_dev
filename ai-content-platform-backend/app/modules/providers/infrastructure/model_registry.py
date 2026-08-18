"""Model registry — capability resolution metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_CONFIGS = Path(__file__).resolve().parents[4] / "configs"


@dataclass(frozen=True, slots=True)
class ModelSpec:
    model_id: str
    provider: str
    model: str
    context_window: int = 128_000
    supports_streaming: bool = False
    supports_json: bool = True
    supports_images: bool = False
    supports_function_calling: bool = False
    supports_vision: bool = False
    max_output_tokens: int = 4096
    latency_class: str = "standard"  # fast | standard | slow
    cost_tier: str = "medium"
    metadata: dict[str, Any] = field(default_factory=dict)


class YamlModelRegistry:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _CONFIGS / "providers" / "models.yaml"
        self._models: dict[str, ModelSpec] = {}
        self.reload()

    def reload(self) -> None:
        self._models = {}
        if not self._path.exists():
            return
        data = yaml.safe_load(self._path.read_text(encoding="utf-8")) or {}
        for mid, item in (data.get("models") or {}).items():
            provider = str(item.get("provider") or "").strip().lower()
            if not provider or provider == "mock":
                continue
            self._models[mid] = ModelSpec(
                model_id=mid,
                provider=provider,
                model=str(item.get("model") or mid),
                context_window=int(item.get("context_window", 128_000)),
                supports_streaming=bool(item.get("supports_streaming", False)),
                supports_json=bool(item.get("supports_json", True)),
                supports_images=bool(item.get("supports_images", False)),
                supports_function_calling=bool(item.get("supports_function_calling", False)),
                supports_vision=bool(item.get("supports_vision", False)),
                max_output_tokens=int(item.get("max_output_tokens", 4096)),
                latency_class=str(item.get("latency_class", "standard")),
                cost_tier=str(item.get("cost_tier", "medium")),
                metadata={k: v for k, v in item.items() if k not in {
                    "provider", "model", "context_window", "supports_streaming",
                    "supports_json", "supports_images", "supports_function_calling",
                    "supports_vision", "max_output_tokens", "latency_class", "cost_tier",
                }},
            )

    def get(self, model_id: str) -> ModelSpec | None:
        return self._models.get(model_id)

    def resolve_provider_model(self, model_id: str) -> tuple[str, str] | None:
        spec = self.get(model_id)
        if not spec:
            return None
        return spec.provider, spec.model

    def all(self) -> dict[str, ModelSpec]:
        return dict(self._models)
