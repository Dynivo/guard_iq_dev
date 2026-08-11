"""Persist AI call telemetry to llm_calls + live ObservabilityEngine."""

from __future__ import annotations

import uuid
from typing import Any

from app.core.logging import get_logger
from app.infrastructure.postgres.models.ai_ops import LlmCall
from app.infrastructure.postgres.session import async_session_factory
from app.modules.analytics.domain.models import AITrace, TraceStatus

logger = get_logger(__name__)


class PostgresRequestRecorder:
    """Writes every orchestrator call to Postgres for durable analytics."""

    async def record(self, payload: dict[str, Any]) -> None:
        provider = str(payload.get("provider") or "unknown")
        model = str(payload.get("model") or "unknown")
        org_raw = payload.get("organization_id")
        org_id: uuid.UUID | None = None
        if org_raw:
            try:
                org_id = uuid.UUID(str(org_raw))
            except ValueError:
                org_id = None

        latency = int(payload.get("latency_ms") or 0)
        cost = float(payload.get("cost_estimate") or 0.0)
        if "success" in payload:
            success = bool(payload.get("success"))
        else:
            success = payload.get("evaluation_status") != "failed"
        status = "success" if success else "failed"
        tokens_in = payload.get("tokens_in")
        tokens_out = payload.get("tokens_out")
        correlation_id = str(payload.get("correlation_id") or "")[:255]
        capability = str(payload.get("capability") or "")
        error = str(payload.get("error_message") or payload.get("error") or "")[:2000] or None
        request_id = str(payload.get("request_id") or uuid.uuid4())

        try:
            async with async_session_factory() as session:
                row = LlmCall(
                    organization_id=org_id,
                    provider=provider,
                    model=model,
                    input_hash=str(payload.get("prompt_hash") or "")[:64] or None,
                    input_text=(capability[:500] if capability else None),
                    output_text=None,
                    latency_ms=latency or None,
                    tokens_in=int(tokens_in) if tokens_in is not None else None,
                    tokens_out=int(tokens_out) if tokens_out is not None else None,
                    cost_estimate=cost,
                    correlation_id=correlation_id or None,
                    status=status,
                    error_message=error,
                )
                session.add(row)
                await session.commit()
        except Exception:  # noqa: BLE001 — telemetry must never break generation
            logger.exception("Failed to persist llm_calls row")

        if org_id is None:
            return

        try:
            # Lazy import avoids circular: analytics.engine → ai.cost → ai.__init__ → recorder
            from app.modules.analytics.application.runtime import get_observability_engine

            engine = get_observability_engine()
            trace = AITrace(
                request_id=request_id,
                correlation_id=correlation_id or request_id,
                organization_id=org_id,
                provider=provider,
                model=model,
                capability=capability or None,
                latency_ms=latency,
                cost_estimate=cost,
                tokens_in=int(tokens_in or 0),
                tokens_out=int(tokens_out or 0),
                status=TraceStatus.SUCCESS if success else TraceStatus.FAILURE,
                event_type="LlmCall",
                metadata={"capability": capability},
            )
            await engine.store.store_ai_trace(trace)
            engine.providers.observe_trace(trace)
            engine.models.observe_trace(trace)
            await engine.cost.record_from_trace(trace)
            engine.metrics.capture_ai(
                status="success" if success else "failure",
                latency_ms=latency,
                provider=provider,
            )
            if cost > 0:
                engine.metrics.capture_cost(cost)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to update in-memory observability from LLM call")
