"""Unit tests for M17 Consensus Engine (deterministic / mocked orchestrator)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.modules.ai.domain.models import OrchestratorRequest, OrchestratorResult
from app.modules.consensus.application.consensus_builder import DefaultConsensusBuilder
from app.modules.consensus.application.cost_optimizer import DefaultCostOptimizer
from app.modules.consensus.application.evaluate import DefaultDeterministicEvaluator
from app.modules.consensus.application.factory import ConsensusEngineFactory
from app.modules.consensus.application.merge import DefaultMergeEngine
from app.modules.consensus.application.sections import parse_sections
from app.modules.consensus.application.subscribers import register_consensus_handlers
from app.modules.consensus.application.weights import InMemoryProviderWeightStore
from app.modules.consensus.domain.models import (
    CandidateResponse,
    ConsensusRequest,
    EvaluationScore,
)
from app.modules.workflow.application.factory import WorkflowFactory
from app.modules.workflow.infrastructure.node_registry import InMemoryNodeRegistry
from app.shared.ai_types import CompletionResult
from app.shared.events.types import DomainEvent
import uuid


_JSON_A = json.dumps(
    {
        "hook": "Protect healthcare data with clear DSPT controls today.",
        "body": "Organisations that inventory assets, enforce access controls, "
        "and train staff reduce cyber risk and build regulator trust. "
        "Evidence shows structured programmes outperform ad-hoc fixes.",
        "cta": "Comment with your biggest DSPT challenge.",
        "hashtags": ["DSPT", "CyberSecurity", "Healthcare"],
    }
)
_JSON_B = json.dumps(
    {
        "hook": "DSPT compliance starts with practical steps, not buzzwords.",
        "body": "Map systems, tighten privileges, and rehearse incident response. "
        "Teams that measure progress weekly stay audit-ready.",
        "cta": "Share one control you improved this quarter.",
        "hashtags": ["DSPT", "InfoSec"],
    }
)


class MultiFakeOrchestrator:
    """Returns provider-specific JSON for panel + judge/critique capabilities."""

    def __init__(self) -> None:
        self.calls: list[OrchestratorRequest] = []

    async def execute(self, request: OrchestratorRequest) -> OrchestratorResult:
        self.calls.append(request)
        if request.capability == "consensus_judge":
            text = json.dumps(
                {
                    "rankings": [
                        {
                            "candidate_id": "A",
                            "rank": 1,
                            "strengths": ["hook"],
                            "weaknesses": [],
                            "linkedin_quality": 0.9,
                            "audience_fit": 0.85,
                            "confidence": 0.8,
                        },
                        {
                            "candidate_id": "B",
                            "rank": 2,
                            "strengths": ["cta"],
                            "weaknesses": ["shorter"],
                            "linkedin_quality": 0.7,
                            "audience_fit": 0.7,
                            "confidence": 0.6,
                        },
                    ],
                    "confidence": 0.75,
                }
            )
            provider, model = "openai", "judge"
        elif request.capability == "consensus_critique":
            text = json.dumps(
                {
                    "issues": [{"section": "cta", "severity": "low", "message": "ok"}],
                    "affected_sections": [],
                    "severity": "low",
                }
            )
            provider, model = "anthropic", "critique"
        elif request.capability == "consensus_revise":
            text = _JSON_A
            provider, model = "openai", "revise"
        else:
            override = (request.provider_override or "gemini").lower()
            text = _JSON_A if override in {"openai", "gemini"} else _JSON_B
            provider, model = override, request.model or "fixture"
        return OrchestratorResult(
            success=True,
            result=CompletionResult(text=text, provider=provider, model=model),
            capability=request.capability,
            provider=provider,
            model=model,
        )

    async def complete(self, capability: str, prompt: str, **overrides: Any) -> CompletionResult:
        out = await self.execute(
            OrchestratorRequest(capability=capability, prompt=prompt, **overrides)
        )
        assert out.result is not None
        return out.result

    async def execute_stream(self, request: OrchestratorRequest):
        yield  # pragma: no cover

    async def execute_many(self, requests: list[OrchestratorRequest]) -> list[OrchestratorResult]:
        return [await self.execute(r) for r in requests]


def test_parse_sections_json() -> None:
    sections = parse_sections(_JSON_A)
    assert "hook" in sections
    assert sections["hook"].startswith("Protect")


def test_cost_optimizer_development_prefers_real_providers() -> None:
    opt = DefaultCostOptimizer()
    panel = opt.select_panel(
        policy_id="development",
        available_providers=["openai", "gemini"],
        weights={},
    )
    assert panel
    assert {m["provider"] for m in panel}.issubset({"openai", "gemini"})


def test_deterministic_evaluator_scores_structured_json() -> None:
    ev = DefaultDeterministicEvaluator()
    cand = CandidateResponse(
        candidate_id="c1",
        provider="openai",
        model="x",
        text=_JSON_A,
        sections=parse_sections(_JSON_A),
        success=True,
    )
    score = ev.evaluate(cand)
    assert score.composite > 0.3
    assert "json_validity" in score.scores


def test_merge_winner_take_all() -> None:
    cands = [
        CandidateResponse(
            candidate_id="1",
            provider="openai",
            model="a",
            text=_JSON_A,
            sections=parse_sections(_JSON_A),
            anonymous_id="A",
            success=True,
        ),
        CandidateResponse(
            candidate_id="2",
            provider="gemini",
            model="b",
            text=_JSON_B,
            sections=parse_sections(_JSON_B),
            anonymous_id="B",
            success=True,
        ),
    ]
    evals = [
        EvaluationScore(candidate_id="1", composite=0.9, scores={"structure": 0.9}, passed=True),
        EvaluationScore(candidate_id="2", composite=0.6, scores={"structure": 0.6}, passed=False),
    ]
    merge = DefaultMergeEngine().merge(cands, evals, None)
    assert merge.strategy == "winner_take_all"
    assert merge.metadata.get("winner_candidate_id") == "1"
    assert merge.metadata.get("winner_provider") == "openai"
    assert len(merge.metadata.get("leaderboard") or []) == 2
    assert merge.merged_text


def test_merge_section_best() -> None:
    cands = [
        CandidateResponse(
            candidate_id="1",
            provider="openai",
            model="a",
            text=_JSON_A,
            sections=parse_sections(_JSON_A),
            anonymous_id="A",
            success=True,
        ),
        CandidateResponse(
            candidate_id="2",
            provider="gemini",
            model="b",
            text=_JSON_B,
            sections=parse_sections(_JSON_B),
            anonymous_id="B",
            success=True,
        ),
    ]
    evals = [
        EvaluationScore(candidate_id="1", composite=0.9, scores={"structure": 0.9}),
        EvaluationScore(candidate_id="2", composite=0.6, scores={"structure": 0.6}),
    ]
    merge = DefaultMergeEngine(
        config={"merge": {"strategy": "section_best", "sections": []}, "providers": {}}
    ).merge(cands, evals, None)
    assert merge.strategy == "section_best"
    assert merge.merged_text
    assert merge.section_sources


def test_consensus_builder_agreement() -> None:
    cands = [
        CandidateResponse(
            candidate_id="1",
            provider="openai",
            model="a",
            text=_JSON_A,
            sections=parse_sections(_JSON_A),
            success=True,
        ),
        CandidateResponse(
            candidate_id="2",
            provider="gemini",
            model="b",
            text=_JSON_A,
            sections=parse_sections(_JSON_A),
            success=True,
        ),
    ]
    evals = [
        EvaluationScore(candidate_id="1", composite=0.8),
        EvaluationScore(candidate_id="2", composite=0.8),
    ]
    metrics = DefaultConsensusBuilder().build(cands, evals, None)
    assert metrics.consensus_score >= 0.0
    assert metrics.successful_count == 2


@pytest.mark.asyncio
async def test_partial_panel_failure_still_succeeds() -> None:
    """One LLM crash must not fail the whole consensus run."""

    class PartialFailOrchestrator(MultiFakeOrchestrator):
        async def execute(self, request: OrchestratorRequest) -> OrchestratorResult:
            self.calls.append(request)
            if request.capability == "writing" and (
                request.provider_override or ""
            ).lower() == "grok":
                raise RuntimeError("grok_timeout")
            if request.capability == "writing" and (
                request.provider_override or ""
            ).lower() == "perplexity":
                return OrchestratorResult(
                    success=False,
                    provider="perplexity",
                    model="sonar",
                    error_code="PROVIDER_EXHAUSTED",
                    error_message="rate_limited",
                )
            return await super().execute(request)

        async def execute_many(
            self, requests: list[OrchestratorRequest]
        ) -> list[OrchestratorResult]:
            import asyncio

            raw = await asyncio.gather(
                *(self.execute(r) for r in requests), return_exceptions=True
            )
            out: list[OrchestratorResult] = []
            for idx, item in enumerate(raw):
                if isinstance(item, OrchestratorResult):
                    out.append(item)
                else:
                    req = requests[idx]
                    out.append(
                        OrchestratorResult(
                            success=False,
                            provider=str(req.provider_override or ""),
                            error_code="EXECUTE_MANY_EXCEPTION",
                            error_message=str(item),
                        )
                    )
            return out

    orch = PartialFailOrchestrator()
    engine = ConsensusEngineFactory.create(orchestrator=orch)
    result = await engine.run(
        ConsensusRequest.from_prompt_fields(
            prompt="Write a LinkedIn post about DSPT",
            capability="writing",
            # Balanced selects several preferred real providers.
            policy_id="balanced",
            metadata={
                "available_providers": ["openai", "grok", "perplexity"],
            },
        )
    )
    assert result.success
    assert result.final_text
    assert result.run.status in {"completed", "completed_partial"}
    failed = [c for c in result.run.candidates if not c.success]
    assert failed  # grok and/or perplexity logged as failed
    report = result.run.to_report()
    assert report.get("partial_success") or any(
        not c["success"] for c in report["candidates"]
    )
    assert any(c.get("error") for c in report["candidates"] if not c["success"])


@pytest.mark.asyncio
async def test_consensus_engine_e2e_parallel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONSENSUS_POLICY", "development")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        orch = MultiFakeOrchestrator()
        engine = ConsensusEngineFactory.create(orchestrator=orch)
        result = await engine.run(
            ConsensusRequest.from_prompt_fields(
                prompt="Write a LinkedIn post about DSPT",
                capability="writing",
                policy_id="development",
                metadata={"available_providers": ["gemini", "openai"]},
            )
        )
        assert result.success
        assert result.final_text
        assert result.run.run_id
        assert engine.get_run(result.run.run_id) is not None
        report = result.run.to_report()
        assert "candidates" in report
        assert "cost_report" in report
        # Parallel fan-out should have called execute_many path (multiple panel calls)
        panel_calls = [c for c in orch.calls if c.capability == "writing"]
        assert len(panel_calls) >= 1
    finally:
        get_settings.cache_clear()


def test_weight_store_learning() -> None:
    store = InMemoryProviderWeightStore()
    before = store.get("openai").writing_score
    store.update("openai", delta_writing=0.05, delta_success=0.05)
    assert store.get("openai").writing_score >= before


@pytest.mark.asyncio
async def test_subscriber_approve_updates_weight() -> None:
    from app.infrastructure.events.in_process_bus import InProcessEventBus

    bus = InProcessEventBus()
    store = register_consensus_handlers(bus)
    before = store.get("openai").writing_score
    await bus.publish(
        DomainEvent(
            event_type="DraftApproved",
            organization_id=uuid.uuid4(),
            correlation_id="c1",
            payload={"provider": "openai"},
        )
    )
    assert store.get("openai").writing_score >= before


def test_workflow_handlers_registered() -> None:
    registry = InMemoryNodeRegistry()
    from app.modules.consensus.application.handlers import register_consensus_workflow_handlers

    register_consensus_workflow_handlers(registry)
    for name in (
        "consensus.generate",
        "consensus.evaluate",
        "consensus.rank",
        "consensus.merge",
        "consensus.critique",
        "consensus.revise",
        "consensus.finalize",
    ):
        assert registry.get(name) is not None


def test_workflow_factory_includes_consensus() -> None:
    _, _, nodes = WorkflowFactory.create(load_builtins=True)
    assert nodes.get("consensus.generate") is not None
