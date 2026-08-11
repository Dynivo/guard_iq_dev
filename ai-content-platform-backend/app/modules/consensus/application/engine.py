"""Default Consensus Engine — full M17 pipeline orchestration."""

from __future__ import annotations

import time
import uuid
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.consensus.application.config_loader import load_consensus_config
from app.modules.consensus.application.consensus_builder import DefaultConsensusBuilder
from app.modules.consensus.application.coordinator import DefaultGenerationCoordinator
from app.modules.consensus.application.cost_optimizer import DefaultCostOptimizer
from app.modules.consensus.application.critique import DefaultCritiqueEngine
from app.modules.consensus.application.evaluate import DefaultDeterministicEvaluator
from app.modules.consensus.application.judge import DefaultAIJudge
from app.modules.consensus.application.merge import DefaultMergeEngine
from app.modules.consensus.application.repository import InMemoryCandidateRepository
from app.modules.consensus.application.revise import DefaultRevisionEngine
from app.modules.consensus.application.weights import InMemoryProviderWeightStore
from app.modules.consensus.domain.models import (
    ConsensusRequest,
    ConsensusResult,
    ConsensusRun,
)
from app.modules.consensus.domain.ports import (
    AIJudge,
    CandidateRepository,
    ConsensusBuilder,
    CostOptimizer,
    CritiqueEngine,
    DeterministicEvaluator,
    GenerationCoordinator,
    MergeEngine,
    ProviderWeightStore,
    RevisionEngine,
)

logger = get_logger(__name__)


class DefaultConsensusEngine:
    """Orchestrate: panel → generate → eval → judge → consensus → merge → critique → revise."""

    def __init__(
        self,
        *,
        coordinator: GenerationCoordinator,
        evaluator: DeterministicEvaluator,
        judge: AIJudge,
        consensus_builder: ConsensusBuilder,
        merge_engine: MergeEngine,
        critique_engine: CritiqueEngine,
        revision_engine: RevisionEngine,
        cost_optimizer: CostOptimizer,
        weight_store: ProviderWeightStore,
        repository: CandidateRepository,
        config: dict[str, Any] | None = None,
    ) -> None:
        self._coordinator = coordinator
        self._evaluator = evaluator
        self._judge = judge
        self._consensus = consensus_builder
        self._merge = merge_engine
        self._critique = critique_engine
        self._revise = revision_engine
        self._cost = cost_optimizer
        self._weights = weight_store
        self._repo = repository
        self._config = config if config is not None else load_consensus_config()
        self._run_cache: dict[str, ConsensusRun] = {}

    async def run(self, request: ConsensusRequest) -> ConsensusResult:
        started = time.perf_counter()
        settings = get_settings()
        policy_id = (
            request.policy_id
            or settings.CONSENSUS_POLICY
            or (self._config.get("policies") or {}).get("default_policy")
            or "balanced"
        ).strip()
        correlation_id = request.correlation_id or str(uuid.uuid4())
        request.correlation_id = correlation_id
        run_id = str(uuid.uuid4())

        available = self._available_providers(request)
        panel = self._cost.select_panel(
            policy_id=policy_id,
            available_providers=available,
            weights=self._weights.all(),
        )

        candidates = await self._coordinator.generate_panel(request, panel)
        evaluations = self._evaluator.evaluate_many(candidates)

        try:
            judge = await self._judge.judge(
                candidates,
                evaluations,
                correlation_id=correlation_id,
                organization_id=request.organization_id,
            )
        except Exception as exc:  # noqa: BLE001 — never fail whole run for judge
            logger.error(
                "consensus.judge_stage_failed",
                extra={
                    "app_module": "consensus",
                    "operation": "run",
                    "correlation_id": correlation_id,
                    "error": str(exc),
                    "outcome": "failure",
                },
            )
            from app.modules.consensus.domain.models import JudgeDecision

            judge = JudgeDecision(rankings=[], confidence=0.0, anonymized=True)

        consensus = self._consensus.build(candidates, evaluations, judge)
        merge = self._merge.merge(candidates, evaluations, judge)

        try:
            critique = await self._critique.critique(
                merge,
                correlation_id=correlation_id,
                organization_id=request.organization_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "consensus.critique_stage_failed",
                extra={
                    "app_module": "consensus",
                    "operation": "run",
                    "correlation_id": correlation_id,
                    "error": str(exc),
                    "outcome": "failure",
                },
            )
            from app.modules.consensus.domain.models import CritiqueReport

            critique = CritiqueReport(
                issues=[],
                affected_sections=[],
                severity="low",
                raw={"error": str(exc)},
            )

        try:
            if critique.affected_sections and critique.severity in {
                "medium",
                "high",
                "critical",
            }:
                merge = await self._revise.revise(
                    request,
                    merge,
                    critique,
                    correlation_id=correlation_id,
                )
            elif critique.affected_sections:
                if policy_id in {"premium", "enterprise"}:
                    merge = await self._revise.revise(
                        request,
                        merge,
                        critique,
                        correlation_id=correlation_id,
                    )
        except Exception as exc:  # noqa: BLE001 — keep pre-revise merge
            logger.error(
                "consensus.revise_stage_failed",
                extra={
                    "app_module": "consensus",
                    "operation": "run",
                    "correlation_id": correlation_id,
                    "error": str(exc),
                    "outcome": "failure",
                },
            )

        total_cost = sum(float(c.cost_estimate) for c in candidates if c.success)
        total_latency = int((time.perf_counter() - started) * 1000)
        failed = [c for c in candidates if not c.success]
        succeeded = [c for c in candidates if c.success]
        success = bool(succeeded) and bool(merge.merged_text)
        # Partial panel success is a completed run with degraded confidence metadata
        if success and failed:
            status = "completed_partial"
        elif success:
            status = "completed"
        else:
            status = "failed"

        run = ConsensusRun(
            run_id=run_id,
            organization_id=request.organization_id,
            correlation_id=correlation_id,
            capability=request.capability,
            policy_id=policy_id,
            status=status,
            candidates=candidates,
            evaluations=evaluations,
            judge=judge,
            consensus=consensus,
            merge=merge,
            critique=critique,
            final_text=merge.merged_text,
            total_cost=round(total_cost, 6),
            total_latency_ms=total_latency,
            panel=[str(m.get("provider") or "") for m in panel],
            metadata={
                "prompt_version": request.prompt_version,
                "available_providers": available,
                "consensus_score": consensus.consensus_score,
                "agreement": consensus.agreement,
                "partial_success": bool(succeeded) and bool(failed),
                "successful_providers": [c.provider for c in succeeded],
                "failed_providers": [
                    {"provider": c.provider, "model": c.model, "error": c.error}
                    for c in failed
                ],
            },
        )
        await self._repo.save_run(run)
        self._run_cache[run.run_id] = run

        if failed:
            logger.warning(
                "consensus.partial_provider_failures run_id=%s failed=%s succeeded=%s",
                run_id,
                [{"provider": c.provider, "error": c.error} for c in failed],
                [c.provider for c in succeeded],
            )

        logger.info(
            "consensus.run_complete run_id=%s status=%s success=%s panel=%s",
            run_id,
            status,
            success,
            run.panel,
        )

        return ConsensusResult(
            success=success,
            final_text=merge.merged_text,
            run=run,
            provider="consensus",
            model="multi",
            error=""
            if success
            else (
                "consensus_panel_failed:"
                + ",".join(f"{c.provider}={c.error}" for c in failed)
                if failed
                else "consensus_panel_failed"
            ),
        )

    def get_run(self, run_id: str) -> ConsensusRun | None:
        cached = self._run_cache.get(run_id)
        if cached is not None:
            return cached
        if isinstance(self._repo, InMemoryCandidateRepository):
            return self._repo.get_run_sync(run_id)
        return None

    def _available_providers(self, request: ConsensusRequest) -> list[str]:
        meta = request.metadata or {}
        if meta.get("available_providers"):
            return [str(p).lower() for p in meta["available_providers"]]
        panel = (self._config.get("providers") or {}).get("panel") or []
        names: list[str] = []
        for entry in panel:
            if isinstance(entry, dict) and entry.get("provider"):
                names.append(str(entry["provider"]).lower())
        # Only providers with configured API keys (skip dead fan-out / mock unless alone)
        from app.modules.providers.infrastructure.provider_factory import DefaultProviderFactory

        factory = DefaultProviderFactory()
        keyed = [n for n in names if n != "mock" and factory.has_credentials(n)]
        if keyed:
            return keyed
        if "mock" in names and factory.has_credentials("mock"):
            return ["mock"]
        return names
