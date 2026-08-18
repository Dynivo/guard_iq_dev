"""Cost-aware panel selection from consensus policy YAML."""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.modules.consensus.application.config_loader import load_consensus_config
from app.modules.consensus.domain.models import ProviderWeight

logger = get_logger(__name__)


class DefaultCostOptimizer:
    """Select panel members under max_providers / budget / preferred / force_providers.

    Preferred providers with API keys are always included first (up to max_providers)
    so multi-model scoring actually fans out — budget only soft-limits fill-ins.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config if config is not None else load_consensus_config()

    def select_panel(
        self,
        *,
        policy_id: str,
        available_providers: list[str],
        weights: dict[str, ProviderWeight],
    ) -> list[dict[str, str]]:
        policies = (self._config.get("policies") or {}).get("policies") or {}
        default_policy = (self._config.get("policies") or {}).get("default_policy") or "balanced"
        policy_name = (policy_id or default_policy).strip() or default_policy
        policy = policies.get(policy_name) or policies.get(default_policy) or {}

        providers_cfg = self._config.get("providers") or {}
        panel_entries = providers_cfg.get("panel") or []
        model_by_provider: dict[str, str] = {}
        for entry in panel_entries:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("provider") or "").strip().lower()
            if name:
                model_by_provider[name] = str(entry.get("model") or "")

        cost_cfg = self._config.get("cost") or {}
        estimates = dict(cost_cfg.get("estimates_usd_per_call") or {})
        selection = dict(cost_cfg.get("selection") or {})
        w_rel = float(selection.get("weight_reliability", 0.35))
        w_write = float(selection.get("weight_writing", 0.35))
        w_cost = float(selection.get("weight_cost", 0.15))
        w_lat = float(selection.get("weight_latency", 0.15))

        max_providers = int(policy.get("max_providers") or 1)
        budget = float(policy.get("budget_usd") or 0.0)
        force = [str(p).lower() for p in (policy.get("force_providers") or [])]
        preferred = [str(p).lower() for p in (policy.get("preferred") or [])]

        available = [
            p.strip().lower()
            for p in available_providers
            if p and str(p).strip() and str(p).strip().lower() in model_by_provider
        ]
        available_set = set(available)

        selected: list[str] = []

        def _add(name: str) -> bool:
            if name not in available_set or name in selected:
                return False
            if len(selected) >= max_providers:
                return False
            selected.append(name)
            return True

        # 1) Explicit force list
        for name in force:
            _add(name)

        # 2) Preferred (in YAML order) — always include when keyed so scoring uses all models
        for name in preferred:
            _add(name)

        # 3) Fill remaining seats by score (budget applies only here)
        remaining = [p for p in available if p not in selected]
        ranked = sorted(
            remaining,
            key=lambda p: self._score(
                p,
                weights=weights,
                estimates=estimates,
                preferred=preferred,
                w_rel=w_rel,
                w_write=w_write,
                w_cost=w_cost,
                w_lat=w_lat,
            ),
            reverse=True,
        )

        spent = sum(float(estimates.get(p, 0.0)) for p in selected)
        for name in ranked:
            if len(selected) >= max_providers:
                break
            cost = float(estimates.get(name, 0.0))
            if budget > 0 and spent + cost > budget and selected:
                continue
            selected.append(name)
            spent += cost

        if not selected and available:
            fallback = preferred[0] if preferred and preferred[0] in available_set else available[0]
            selected = [fallback]

        panel = [
            {"provider": name, "model": model_by_provider.get(name, "")}
            for name in selected[:max_providers]
        ]

        logger.info(
            "consensus.panel_selected policy=%s panel=%s available=%s estimated_cost=%.3f",
            policy_name,
            [m["provider"] for m in panel],
            available,
            spent,
        )
        return panel

    def _score(
        self,
        provider: str,
        *,
        weights: dict[str, ProviderWeight],
        estimates: dict[str, Any],
        preferred: list[str],
        w_rel: float,
        w_write: float,
        w_cost: float,
        w_lat: float,
    ) -> float:
        weight = weights.get(provider) or ProviderWeight(provider=provider)
        cost_est = float(estimates.get(provider, 0.02) or 0.0)
        cost_efficiency = 1.0 / (1.0 + max(cost_est, 0.0) * 50.0)
        preference_bonus = 0.15 if provider in preferred else 0.0
        preferred_rank = preferred.index(provider) if provider in preferred else 99
        preference_bonus += max(0.0, 0.1 - 0.01 * preferred_rank)

        return (
            w_rel * weight.reliability
            + w_write * weight.writing_score
            + w_cost * (weight.cost * 0.5 + cost_efficiency * 0.5)
            + w_lat * weight.latency
            + preference_bonus
        )
