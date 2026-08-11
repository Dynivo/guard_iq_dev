"""Wire default Consensus Engine dependencies."""

from __future__ import annotations

from typing import Any

from app.modules.ai.application.factory import AIOrchestratorFactory
from app.modules.ai.domain.ports import AIOrchestrator
from app.modules.consensus.application.config_loader import load_consensus_config
from app.modules.consensus.application.consensus_builder import DefaultConsensusBuilder
from app.modules.consensus.application.coordinator import DefaultGenerationCoordinator
from app.modules.consensus.application.cost_optimizer import DefaultCostOptimizer
from app.modules.consensus.application.critique import DefaultCritiqueEngine
from app.modules.consensus.application.engine import DefaultConsensusEngine
from app.modules.consensus.application.evaluate import DefaultDeterministicEvaluator
from app.modules.consensus.application.judge import DefaultAIJudge
from app.modules.consensus.application.merge import DefaultMergeEngine
from app.modules.consensus.application.repository import InMemoryCandidateRepository
from app.modules.consensus.application.revise import DefaultRevisionEngine
from app.modules.consensus.application.weights import InMemoryProviderWeightStore


class ConsensusEngineFactory:
    """Compose production ConsensusEngine with optional shared orchestrator."""

    @staticmethod
    def create(
        orchestrator: AIOrchestrator | None = None,
        *,
        config: dict[str, Any] | None = None,
        weight_store: InMemoryProviderWeightStore | None = None,
        repository: InMemoryCandidateRepository | None = None,
    ) -> DefaultConsensusEngine:
        cfg = config if config is not None else load_consensus_config()
        orch = orchestrator or AIOrchestratorFactory.create()
        weights = weight_store or InMemoryProviderWeightStore(cfg)
        repo = repository or InMemoryCandidateRepository()

        return DefaultConsensusEngine(
            coordinator=DefaultGenerationCoordinator(orch),
            evaluator=DefaultDeterministicEvaluator(cfg),
            judge=DefaultAIJudge(orch, config=cfg),
            consensus_builder=DefaultConsensusBuilder(),
            merge_engine=DefaultMergeEngine(cfg),
            critique_engine=DefaultCritiqueEngine(orch),
            revision_engine=DefaultRevisionEngine(orch),
            cost_optimizer=DefaultCostOptimizer(cfg),
            weight_store=weights,
            repository=repo,
            config=cfg,
        )
