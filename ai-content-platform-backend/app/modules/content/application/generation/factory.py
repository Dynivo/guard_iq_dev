"""Compose Content Generation Engine stack."""

from __future__ import annotations

from pathlib import Path

from app.modules.ai.domain.ports import AIOrchestrator
from app.modules.content.application.generation.engine import (
    DefaultContentGenerationEngine,
    FakeOrchestrator,
)
from app.modules.content.application.generation.policy_loader import load_generation_policy

_GEN = Path(__file__).resolve().parents[5] / "configs" / "content" / "generation"


class ContentGenerationFactory:
    @staticmethod
    def create_memory(
        *,
        orchestrator: AIOrchestrator | None = None,
        config_dir: Path | None = None,
        response_text: str | None = None,
        consensus_engine=None,
    ) -> DefaultContentGenerationEngine:
        root = config_dir or _GEN
        orch = orchestrator or FakeOrchestrator(response_text=response_text)
        return DefaultContentGenerationEngine(
            orch,
            policy=load_generation_policy(root),
            consensus_engine=consensus_engine,
        )
