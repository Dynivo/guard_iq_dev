"""Consensus Engine ports."""

from __future__ import annotations

from typing import Any, Protocol

from app.modules.consensus.domain.models import (
    CandidateResponse,
    ConsensusMetrics,
    ConsensusRequest,
    ConsensusResult,
    ConsensusRun,
    CritiqueReport,
    EvaluationScore,
    JudgeDecision,
    MergeDecision,
    ProviderWeight,
)


class ConsensusEngine(Protocol):
    async def run(self, request: ConsensusRequest) -> ConsensusResult: ...

    def get_run(self, run_id: str) -> ConsensusRun | None: ...


class GenerationCoordinator(Protocol):
    async def generate_panel(
        self, request: ConsensusRequest, providers: list[dict[str, str]]
    ) -> list[CandidateResponse]: ...


class CandidateRepository(Protocol):
    async def save_run(self, run: ConsensusRun) -> None: ...

    async def get_run(self, run_id: str) -> ConsensusRun | None: ...

    async def list_runs(
        self, organization_id: Any = None, *, limit: int = 50
    ) -> list[ConsensusRun]: ...


class DeterministicEvaluator(Protocol):
    def evaluate(self, candidate: CandidateResponse) -> EvaluationScore: ...

    def evaluate_many(self, candidates: list[CandidateResponse]) -> list[EvaluationScore]: ...


class AIJudge(Protocol):
    async def judge(
        self,
        candidates: list[CandidateResponse],
        evaluations: list[EvaluationScore],
        *,
        correlation_id: str = "",
        organization_id: Any = None,
    ) -> JudgeDecision: ...


class ConsensusBuilder(Protocol):
    def build(
        self,
        candidates: list[CandidateResponse],
        evaluations: list[EvaluationScore],
        judge: JudgeDecision | None,
    ) -> ConsensusMetrics: ...


class MergeEngine(Protocol):
    def merge(
        self,
        candidates: list[CandidateResponse],
        evaluations: list[EvaluationScore],
        judge: JudgeDecision | None,
    ) -> MergeDecision: ...


class CritiqueEngine(Protocol):
    async def critique(
        self,
        merged: MergeDecision,
        *,
        correlation_id: str = "",
        organization_id: Any = None,
    ) -> CritiqueReport: ...


class RevisionEngine(Protocol):
    async def revise(
        self,
        request: ConsensusRequest,
        merged: MergeDecision,
        critique: CritiqueReport,
        *,
        correlation_id: str = "",
    ) -> MergeDecision: ...


class CostOptimizer(Protocol):
    def select_panel(
        self,
        *,
        policy_id: str,
        available_providers: list[str],
        weights: dict[str, ProviderWeight],
    ) -> list[dict[str, str]]: ...


class ProviderWeightStore(Protocol):
    def get(self, provider: str) -> ProviderWeight: ...

    def all(self) -> dict[str, ProviderWeight]: ...

    def update(self, provider: str, *, delta_writing: float = 0.0, delta_success: float = 0.0) -> ProviderWeight: ...
