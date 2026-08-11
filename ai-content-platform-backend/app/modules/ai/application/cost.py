"""YAML-backed cost estimator."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

_CONFIGS_DIR = Path(__file__).resolve().parents[4] / "configs"

# Strip dated / variant suffixes so gpt-4o-mini-2024-07-18 → gpt-4o-mini
_DATE_SUFFIX = re.compile(r"-\d{4}-\d{2}-\d{2}$")


def normalize_model_key(model: str) -> str:
    m = (model or "").strip()
    if not m:
        return "default"
    m = _DATE_SUFFIX.sub("", m)
    return m


class YamlCostEstimator:
    """Estimate USD cost from tokens using configs/providers/pricing.yaml.

    Rates in YAML are USD per 1K tokens (vendor list prices are usually per 1M).
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _CONFIGS_DIR / "providers" / "pricing.yaml"
        self._pricing: dict[str, Any] = {}
        self.reload()

    def reload(self) -> None:
        if self._path.exists():
            self._pricing = yaml.safe_load(self._path.read_text(encoding="utf-8")) or {}
        else:
            self._pricing = {}

    def _lookup_rates(self, provider: str, model: str) -> dict[str, Any]:
        providers = self._pricing.get("providers") or {}
        prov = providers.get(provider) or providers.get(provider.lower()) or {}
        models = prov.get("models") or {}
        key = normalize_model_key(model)
        if key in models:
            return models[key]
        # Progressive prefix match (gpt-4o-mini-xyz → gpt-4o-mini)
        for candidate in sorted(models.keys(), key=len, reverse=True):
            if candidate == "default":
                continue
            if key.startswith(candidate) or candidate.startswith(key):
                return models[candidate]
        return models.get("default") or {}

    def estimate(
        self,
        *,
        provider: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
    ) -> float:
        rates = self._lookup_rates(provider, model)
        in_rate = float(rates.get("input_per_1k", 0.0))
        out_rate = float(rates.get("output_per_1k", 0.0))
        return round((tokens_in / 1000.0) * in_rate + (tokens_out / 1000.0) * out_rate, 8)
