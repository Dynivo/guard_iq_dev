"""API-facing analytics service — live DB first, in-memory as supplement."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analytics.application.engine import ObservabilityEngine
from app.modules.analytics.application.live_repository import LiveAnalyticsRepository
from app.modules.analytics.application.replay import ObservabilityReplayService
from app.modules.analytics.application.runtime import get_observability_engine


class AnalyticsService:
    def __init__(
        self,
        engine: ObservabilityEngine | None = None,
        session: AsyncSession | None = None,
    ) -> None:
        self._engine = engine or get_observability_engine()
        self._replay = ObservabilityReplayService(self._engine.store)
        self._session = session
        self._live = LiveAnalyticsRepository(session) if session is not None else None

    def metrics(self) -> dict[str, Any]:
        return self._engine.metrics.snapshot()

    async def metrics_live(self, org_id: uuid.UUID) -> dict[str, Any]:
        if self._live is None:
            return self.metrics()
        return await self._live.metrics_snapshot(org_id)

    def traces(
        self, org_id: uuid.UUID, *, correlation_id: str | None = None
    ) -> dict[str, Any]:
        return {
            "ai_traces": self._engine.ai_traces.list_for_org(
                org_id, correlation_id=correlation_id
            ),
            "workflow_traces": self._engine.workflow_traces.list_for_org(
                org_id, correlation_id=correlation_id
            ),
        }

    def evaluations(self, org_id: uuid.UUID) -> list[dict[str, Any]]:
        return [
            e.to_dict()
            for e in self._engine.store.evaluations
            if e.organization_id == org_id
        ]

    async def provider_health(self, org_id: uuid.UUID | None = None) -> list[dict[str, Any]]:
        """Merge live usage with providers that have API keys configured."""
        live: list[dict[str, Any]] = []
        if self._live is not None and org_id is not None:
            live = await self._live.provider_health(org_id)
        else:
            live = [
                {**h, "status": "observed"}
                for h in self._engine.providers.list_health()
                if int(h.get("requests") or 0) > 0
            ]

        by_name: dict[str, dict[str, Any]] = {}
        for row in live:
            key = str(row.get("provider") or "unknown").lower()
            if key == "mock":
                continue
            if key in {"", "unknown", "image"} and int(row.get("requests") or 0) == 0:
                continue
            by_name[key] = {
                **row,
                "provider": key,
                "configured": False,
                "status": row.get("status") or ("observed" if int(row.get("requests") or 0) else "idle"),
            }

        try:
            from app.modules.providers.infrastructure.provider_factory import (
                DefaultProviderFactory,
            )

            factory = DefaultProviderFactory()
            # Surface keys the org can actually call from this deployment
            display = ("openai", "gemini", "perplexity", "grok", "anthropic", "azure_openai")
            for name in display:
                if not factory.has_credentials(name):
                    continue
                if name in by_name:
                    by_name[name]["configured"] = True
                    if int(by_name[name].get("requests") or 0) == 0:
                        by_name[name]["status"] = "configured"
                    else:
                        by_name[name]["status"] = "active"
                else:
                    by_name[name] = {
                        "provider": name,
                        "requests": 0,
                        "successes": 0,
                        "failures": 0,
                        "timeouts": 0,
                        "fallbacks": 0,
                        "availability": None,
                        "average_latency_ms": 0,
                        "error_classes": {},
                        "configured": True,
                        "status": "configured",
                    }
        except Exception:
            pass

        # Drop noisy empty unknown rows
        rows = [
            r
            for r in by_name.values()
            if r.get("provider") != "unknown" or int(r.get("requests") or 0) > 0
        ]
        return sorted(
            rows,
            key=lambda r: (
                0 if r.get("configured") else 1,
                -int(r.get("requests") or 0),
                str(r.get("provider") or ""),
            ),
        )

    async def model_health(self, org_id: uuid.UUID | None = None) -> list[dict[str, Any]]:
        if self._live is not None and org_id is not None:
            live = await self._live.model_health(org_id)
            if live:
                return [
                    row
                    for row in live
                    if str(row.get("provider") or "").lower() != "mock"
                ]
        return [
            {**h, "status": "observed"}
            for h in self._engine.models.list_health()
            if int(h.get("requests") or 0) > 0
            and str(h.get("provider") or "").lower() != "mock"
        ]

    async def workflow_health(self, org_id: uuid.UUID | None = None) -> dict[str, Any]:
        if self._live is not None and org_id is not None:
            return await self._live.workflow_health(org_id)
        return self._engine.workflow_traces.statistics()

    async def cost(self, org_id: uuid.UUID) -> dict[str, Any]:
        if self._live is not None:
            live = await self._live.cost(org_id)
            if float(live.get("total") or 0) > 0 or live.get("usage"):
                return live
        mem = self._engine.cost.aggregate(org_id)
        mem["source"] = "memory"
        return mem

    async def usage(self, org_id: uuid.UUID) -> dict[str, Any]:
        if self._live is not None:
            return await self._live.usage(org_id)
        return {
            "organization_id": str(org_id),
            "usage": self._engine.cost.org_usage(org_id),
            "signals": self._engine.insights.list_signals(org_id),
            "source": "memory",
        }

    def correlation(self, org_id: uuid.UUID, correlation_id: str) -> dict[str, Any]:
        return self._engine.correlation.explore(org_id, correlation_id)

    def replay(self, org_id: uuid.UUID, correlation_id: str) -> dict[str, Any]:
        return self._replay.replay(org_id, correlation_id)

    @property
    def engine(self) -> ObservabilityEngine:
        return self._engine
