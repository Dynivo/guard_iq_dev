"""In-memory provider weight store backed by configs/consensus/weights.yaml."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.core.logging import get_logger
from app.modules.consensus.application.config_loader import load_consensus_config
from app.modules.consensus.domain.models import ProviderWeight

logger = get_logger(__name__)

_WEIGHT_FIELDS = (
    "reliability",
    "latency",
    "cost",
    "historical_success",
    "domain_score",
    "brand_score",
    "writing_score",
    "research_score",
    "image_prompt_score",
)


class InMemoryProviderWeightStore:
    """Loads initial weights from YAML; clamps learning updates to configured bounds."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        cfg = config if config is not None else load_consensus_config()
        weights_cfg = cfg.get("weights") or {}
        defaults = dict(weights_cfg.get("defaults") or {})
        learning = dict(weights_cfg.get("learning") or {})
        self._min = float(learning.get("min_weight", 0.05))
        self._max = float(learning.get("max_weight", 1.0))
        self._approve_delta = float(learning.get("approve_delta", 0.05))
        self._reject_delta = float(learning.get("reject_delta", -0.08))
        self._edit_delta = float(learning.get("edit_delta", -0.03))
        self._weights: dict[str, ProviderWeight] = {}

        providers = weights_cfg.get("providers") or {}
        if isinstance(providers, dict):
            for name, overrides in providers.items():
                merged = {**defaults, **(overrides if isinstance(overrides, dict) else {})}
                self._weights[str(name)] = self._build(str(name), merged, defaults)

        # Ensure panel providers from providers.yaml exist even if absent in weights.yaml
        panel = (cfg.get("providers") or {}).get("panel") or []
        for entry in panel:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("provider") or "").strip()
            if name and name not in self._weights:
                self._weights[name] = self._build(name, defaults, defaults)

        logger.info(
            "consensus.weights_loaded",
            extra={
                "app_module": "consensus",
                "operation": "load_weights",
                "provider_count": len(self._weights),
                "outcome": "success",
            },
        )

    @property
    def approve_delta(self) -> float:
        return self._approve_delta

    @property
    def reject_delta(self) -> float:
        return self._reject_delta

    @property
    def edit_delta(self) -> float:
        return self._edit_delta

    def get(self, provider: str) -> ProviderWeight:
        name = (provider or "").strip().lower()
        if name in self._weights:
            return deepcopy(self._weights[name])
        return ProviderWeight(provider=name or "unknown")

    def all(self) -> dict[str, ProviderWeight]:
        return {k: deepcopy(v) for k, v in self._weights.items()}

    def update(
        self,
        provider: str,
        *,
        delta_writing: float = 0.0,
        delta_success: float = 0.0,
    ) -> ProviderWeight:
        name = (provider or "").strip().lower()
        current = self._weights.get(name) or ProviderWeight(provider=name or "unknown")
        writing = self._clamp(current.writing_score + float(delta_writing))
        success = self._clamp(current.historical_success + float(delta_success))
        updated = ProviderWeight(
            provider=name or current.provider,
            reliability=current.reliability,
            latency=current.latency,
            cost=current.cost,
            historical_success=success,
            domain_score=current.domain_score,
            brand_score=current.brand_score,
            writing_score=writing,
            research_score=current.research_score,
            image_prompt_score=current.image_prompt_score,
            metadata=dict(current.metadata),
        )
        self._weights[name] = updated
        logger.info(
            "consensus.weight_updated",
            extra={
                "app_module": "consensus",
                "operation": "update_weight",
                "provider": name,
                "writing_score": updated.writing_score,
                "historical_success": updated.historical_success,
                "outcome": "success",
            },
        )
        return deepcopy(updated)

    def _clamp(self, value: float) -> float:
        return max(self._min, min(self._max, float(value)))

    @staticmethod
    def _build(
        name: str, merged: dict[str, Any], defaults: dict[str, Any]
    ) -> ProviderWeight:
        kwargs: dict[str, Any] = {"provider": name}
        for field in _WEIGHT_FIELDS:
            raw = merged.get(field, defaults.get(field, 0.5))
            try:
                kwargs[field] = float(raw)
            except (TypeError, ValueError):
                kwargs[field] = 0.5
        extras = {
            k: v
            for k, v in merged.items()
            if k not in _WEIGHT_FIELDS and k != "provider"
        }
        kwargs["metadata"] = extras
        return ProviderWeight(**kwargs)
