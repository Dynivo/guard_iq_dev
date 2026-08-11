"""Cost Engine — aggregate costs without re-implementing provider pricing logic."""

from __future__ import annotations

import uuid
from typing import Any

from app.modules.ai.application.cost import YamlCostEstimator
from app.modules.analytics.application.config_loader import load_analytics_config
from app.modules.analytics.application.store import InMemoryObservabilityStore
from app.modules.analytics.domain.models import AITrace, CostCategory, CostRecord


class CostEngine:
    def __init__(
        self,
        store: InMemoryObservabilityStore,
        *,
        config_dir: str | None = None,
        estimator: YamlCostEstimator | None = None,
    ) -> None:
        self._store = store
        self._config = load_analytics_config(config_dir)
        self._estimator = estimator or YamlCostEstimator()

    def _cfg(self) -> dict[str, Any]:
        return (self._config.get("cost") or {}).get("cost") or {}

    async def record_from_trace(self, trace: AITrace) -> CostRecord | None:
        amount = float(trace.cost_estimate or 0.0)
        if amount <= 0 and (trace.tokens_in or trace.tokens_out) and trace.provider and trace.model:
            amount = self._estimator.estimate(
                provider=trace.provider,
                model=trace.model,
                tokens_in=trace.tokens_in,
                tokens_out=trace.tokens_out,
            )
        if amount <= 0:
            return None
        record = CostRecord(
            record_id=str(uuid.uuid4()),
            organization_id=trace.organization_id,
            category=CostCategory.PROVIDER,
            amount_usd=amount,
            correlation_id=trace.correlation_id,
            provider=trace.provider,
            model=trace.model,
            metadata={"event_type": trace.event_type},
        )
        await self._store.store_cost(record)
        return record

    async def record_category(
        self,
        org_id: uuid.UUID,
        category: str,
        amount_usd: float | None = None,
        *,
        correlation_id: str | None = None,
        workflow_name: str | None = None,
    ) -> CostRecord:
        cfg = self._cfg()
        defaults = {
            "image": float(cfg.get("default_image_usd") or 0.02),
            "render": float(cfg.get("default_render_usd") or 0.01),
            "storage": float(cfg.get("default_storage_usd") or 0.001),
        }
        amt = float(amount_usd if amount_usd is not None else defaults.get(category, 0.0))
        try:
            cat = CostCategory(category)
        except ValueError:
            cat = CostCategory.OTHER
        record = CostRecord(
            record_id=str(uuid.uuid4()),
            organization_id=org_id,
            category=cat,
            amount_usd=amt,
            correlation_id=correlation_id,
            workflow_name=workflow_name,
        )
        await self._store.store_cost(record)
        return record

    def org_usage(self, org_id: uuid.UUID) -> dict[str, float]:
        return dict(self._store.org_usage.get(str(org_id), {}))

    def aggregate(self, org_id: uuid.UUID | None = None) -> dict[str, Any]:
        if org_id is not None:
            usage = self.org_usage(org_id)
            return {"organization_id": str(org_id), "usage": usage, "total": usage.get("total", 0.0)}
        return {
            "organizations": {
                k: {"usage": dict(v), "total": v.get("total", 0.0)}
                for k, v in self._store.org_usage.items()
            }
        }
