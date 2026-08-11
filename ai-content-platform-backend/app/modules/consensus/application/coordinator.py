"""Fan-out generation coordinator via AI Orchestrator execute_many."""

from __future__ import annotations

import string
import uuid
from typing import Any

from app.core.logging import get_logger
from app.modules.ai.domain.models import OrchestratorRequest, OrchestratorResult
from app.modules.ai.domain.ports import AIOrchestrator
from app.modules.consensus.application import sections as section_parser
from app.modules.consensus.domain.models import CandidateResponse, ConsensusRequest

logger = get_logger(__name__)


class DefaultGenerationCoordinator:
    """Build per-provider OrchestratorRequests and map results to CandidateResponse.

    Partial panel failure is expected: failed providers become ``success=False``
    candidates with logged errors; successful siblings still proceed.
    """

    def __init__(self, orchestrator: AIOrchestrator) -> None:
        self._orchestrator = orchestrator

    async def generate_panel(
        self, request: ConsensusRequest, providers: list[dict[str, str]]
    ) -> list[CandidateResponse]:
        if not providers:
            return []

        orch_requests: list[OrchestratorRequest] = []
        for member in providers:
            provider = str(member.get("provider") or "").strip().lower()
            model = str(member.get("model") or "").strip() or None
            orch_requests.append(
                OrchestratorRequest(
                    capability=request.capability,
                    prompt=request.prompt,
                    organization_id=request.organization_id,
                    correlation_id=request.correlation_id,
                    system_message=request.system_message,
                    response_format=request.response_format,
                    model=model,
                    prompt_version=request.prompt_version,
                    bypass_cache=True,
                    provider_override=provider or None,
                    skip_fallbacks=True,
                    metadata={
                        **dict(request.metadata),
                        "consensus_panel_provider": provider,
                        "consensus_panel_model": model or "",
                    },
                )
            )

        results = await self._orchestrator.execute_many(orch_requests)
        # Defensive: length mismatch must not abort the whole panel
        if len(results) != len(providers):
            logger.error(
                "consensus.panel_length_mismatch",
                extra={
                    "app_module": "consensus",
                    "operation": "generate_panel",
                    "correlation_id": request.correlation_id,
                    "providers": len(providers),
                    "results": len(results),
                    "outcome": "failure",
                },
            )
            while len(results) < len(providers):
                results.append(
                    OrchestratorResult(
                        success=False,
                        error_code="MISSING_RESULT",
                        error_message="panel result missing",
                    )
                )

        candidates: list[CandidateResponse] = []
        anon_ids = _anonymous_ids(len(providers))
        failed_providers: list[dict[str, str]] = []

        for idx, member in enumerate(providers):
            outcome = results[idx] if idx < len(results) else OrchestratorResult(
                success=False, error_message="missing_outcome"
            )
            provider = str(
                getattr(outcome, "provider", None)
                or member.get("provider")
                or ""
            ).strip().lower()
            model = str(getattr(outcome, "model", None) or member.get("model") or "")
            candidate_id = str(uuid.uuid4())
            anonymous_id = anon_ids[idx]

            if (
                isinstance(outcome, OrchestratorResult)
                and outcome.success
                and outcome.result is not None
            ):
                text = outcome.result.text or ""
                parsed = section_parser.parse_sections(text)
                candidates.append(
                    CandidateResponse(
                        candidate_id=candidate_id,
                        provider=provider or outcome.result.provider,
                        model=model or outcome.result.model,
                        text=text,
                        latency_ms=int(outcome.result.latency_ms),
                        tokens_in=int(outcome.result.tokens_in),
                        tokens_out=int(outcome.result.tokens_out),
                        cost_estimate=float(outcome.result.cost_estimate),
                        success=True,
                        sections=parsed,
                        anonymous_id=anonymous_id,
                        metadata={
                            "cache_hit": outcome.cache_hit,
                            "retries": outcome.retries,
                        },
                    )
                )
            else:
                error = _outcome_error(outcome)
                failed_providers.append(
                    {"provider": provider, "model": model, "error": error}
                )
                logger.warning(
                    "consensus.panel_provider_failed provider=%s model=%s error=%s",
                    provider,
                    model,
                    error,
                )
                candidates.append(
                    CandidateResponse(
                        candidate_id=candidate_id,
                        provider=provider,
                        model=model,
                        text="",
                        success=False,
                        error=error,
                        sections=section_parser.parse_sections(""),
                        anonymous_id=anonymous_id,
                        metadata={
                            **_metrics_meta(getattr(outcome, "metrics", None)),
                            "error_code": getattr(outcome, "error_code", None) or "",
                        },
                    )
                )

        successful = sum(1 for c in candidates if c.success)
        logger.info(
            "consensus.panel_generated",
            extra={
                "app_module": "consensus",
                "operation": "generate_panel",
                "correlation_id": request.correlation_id,
                "candidate_count": len(candidates),
                "successful_count": successful,
                "failed_count": len(candidates) - successful,
                "failed_providers": [f["provider"] for f in failed_providers],
                "partial_success": successful > 0 and successful < len(candidates),
                "outcome": "success" if successful > 0 else "failure",
            },
        )
        return candidates


def _outcome_error(outcome: Any) -> str:
    if isinstance(outcome, BaseException):
        return str(outcome)
    if not isinstance(outcome, OrchestratorResult):
        return f"unexpected_outcome:{type(outcome).__name__}"
    return str(
        outcome.error_message
        or outcome.error_code
        or "generation_failed"
    )


def _anonymous_ids(count: int) -> list[str]:
    letters = list(string.ascii_uppercase)
    ids: list[str] = []
    for i in range(count):
        if i < len(letters):
            ids.append(letters[i])
        else:
            cycle = i // len(letters)
            ids.append(f"{letters[i % len(letters)]}{cycle}")
    return ids


def _metrics_meta(metrics: dict[str, Any] | None) -> dict[str, Any]:
    if not metrics:
        return {}
    return {
        k: v
        for k, v in metrics.items()
        if k in {"latency_ms", "retries", "error", "duration_ms", "exception"}
    }
