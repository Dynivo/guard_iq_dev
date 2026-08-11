"""Unit tests for Milestone 9 Content Generation Engine."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.modules.content.application.generation.content_validator import (
    DefaultContentDraftValidator,
)
from app.modules.content.application.generation.diff import DefaultDraftDiffService
from app.modules.content.application.generation.engine import (
    DefaultContentGenerationEngine,
    FakeOrchestrator,
)
from app.modules.content.application.generation.factory import ContentGenerationFactory
from app.modules.content.application.generation.formatter import DefaultContentFormatter
from app.modules.content.application.generation.fact_validator import DefaultFactValidator
from app.modules.content.domain.models import (
    DraftSlide,
    GenerationRequest,
    StructuredDraft,
)
from app.modules.prompts.domain.models import PromptRequest
from app.modules.workflow.application.factory import WorkflowFactory
from app.modules.workflow.domain.models import WorkflowContext

CONFIGS = Path(__file__).resolve().parents[2] / "configs"


def _prompt(**kwargs) -> PromptRequest:
    base = dict(
        prompt="Write a LinkedIn post about DSPT compliance for care homes.",
        capability="writing",
        prompt_version="1.0",
        response_format="json",
        schema_id="json",
        valid=True,
    )
    base.update(kwargs)
    return PromptRequest(**base)


@pytest.mark.asyncio
async def test_engine_rejects_missing_prompt_request() -> None:
    engine = ContentGenerationFactory.create_memory()
    result = await engine.generate(GenerationRequest(prompt_request=None))
    assert result.success is False
    assert any("PromptRequest" in e for e in result.errors)


@pytest.mark.asyncio
async def test_engine_rejects_invalid_prompt_request() -> None:
    engine = ContentGenerationFactory.create_memory()
    result = await engine.generate(
        GenerationRequest(prompt_request=_prompt(valid=False, errors=("bad",), prompt=""))
    )
    assert result.success is False


@pytest.mark.asyncio
async def test_engine_never_builds_prompts_uses_orchestrator() -> None:
    orch = FakeOrchestrator()
    engine = DefaultContentGenerationEngine(orch)
    pr = _prompt()
    result = await engine.generate(
        GenerationRequest(
            prompt_request=pr,
            source_text="DSPT compliance guidance for healthcare organisations.",
        )
    )
    assert result.success
    assert result.draft is not None
    assert result.draft.hook
    assert result.draft.lifecycle_status == "finalized"
    assert len(orch.calls) == 1
    assert orch.calls[0].prompt == pr.prompt
    assert result.raw is not None
    # Raw never returned as the primary client payload — draft is structured
    assert "hook" in result.draft.to_dict()


@pytest.mark.asyncio
async def test_validation_failure_blocks_finalize() -> None:
    bad = FakeOrchestrator(
        response_text='{"hook":"x","body":"short","cta":"","hashtags":[]}'
    )
    engine = DefaultContentGenerationEngine(bad)
    result = await engine.generate(GenerationRequest(prompt_request=_prompt()))
    assert result.success is False
    assert result.draft is not None
    assert result.draft.lifecycle_status == "rejected"


@pytest.mark.asyncio
async def test_fact_validator_flags_unverified_numbers() -> None:
    v = DefaultFactValidator()
    draft = StructuredDraft(
        hook="Major breach",
        body="Over 1,234,567 records were exposed last week.",
        cta="Comment below.",
    )
    out = v.validate(draft, source_text="A data breach occurred.")
    assert out.valid is False
    assert out.fact_score < 1.0


@pytest.mark.asyncio
async def test_brand_forbidden_phrase() -> None:
    from app.modules.content.application.generation.brand_validator import (
        DefaultBrandValidator,
    )
    from app.modules.content.application.generation.policy_loader import (
        load_generation_policy,
    )

    policy = load_generation_policy(CONFIGS / "content" / "generation")
    draft = StructuredDraft(
        hook="You won't believe this security tip",
        body="A practical guide for healthcare compliance teams and regulators.",
        cta="Follow for more.",
    )
    out = DefaultBrandValidator().validate(draft, policy=policy)
    assert out.valid is False


@pytest.mark.asyncio
async def test_formatter_linkedin_and_carousel() -> None:
    fmt = DefaultContentFormatter()
    single = fmt.format(
        StructuredDraft(hook="H", body="Body text here", cta="CTA", hashtags=("DSPT",))
    )
    assert "H" in single.markdown
    assert single.lifecycle_status == "formatted"

    carousel = fmt.format(
        StructuredDraft(
            format="carousel",
            slides=(
                DraftSlide(1, "Intro", "Point A"),
                DraftSlide(2, "Steps", "Point B"),
                DraftSlide(3, "Close", "Point C"),
            ),
        )
    )
    assert "Slide 1" in carousel.markdown


@pytest.mark.asyncio
async def test_draft_diff_and_replay() -> None:
    engine = ContentGenerationFactory.create_memory()
    result = await engine.generate(
        GenerationRequest(
            prompt_request=_prompt(),
            source_text="DSPT compliance guidance for healthcare.",
        )
    )
    assert result.success
    assert result.replay_id
    assert engine.replay_store.get(result.replay_id) is not None
    left = result.draft
    assert left is not None
    right = StructuredDraft(hook="Other", body=left.body, cta=left.cta)
    diff = DefaultDraftDiffService().diff(left, right)
    assert any(c["field"] == "hook" for c in diff.changes)


@pytest.mark.asyncio
async def test_content_validator_carousel_structure() -> None:
    from app.modules.content.application.generation.policy_loader import (
        load_generation_policy,
    )

    policy = load_generation_policy(CONFIGS / "content" / "generation")
    draft = StructuredDraft(
        hook="Carousel intro that is long enough",
        body="Body " * 20,
        cta="Comment with your thoughts today.",
        format="carousel",
        slides=(DraftSlide(1, "One", "a"), DraftSlide(2, "Two", "b")),
    )
    out = DefaultContentDraftValidator().validate(draft, policy)
    assert out.valid is False
    assert any("few slides" in e for e in out.errors)


@pytest.mark.asyncio
async def test_workflow_generation_nodes() -> None:
    engine, wreg, nreg = WorkflowFactory.create(workflows_dir=CONFIGS / "workflows")
    for t in (
        "content.generate",
        "content.validate_draft",
        "content.format",
        "content.finalize",
    ):
        assert t in nreg.known_types()
    assert "content_generation" in wreg.list_names()

    result = await engine.run(
        "content_generation",
        initial_context=WorkflowContext(
            correlation_id="m9-gen",
            data={
                "article_summary": "Weekly industry update for SMB IT managers.",
                "knowledge.optimized_context": {
                    "text": "A practical professional update on endpoint security for SMBs."
                },
                "relevance_score": 0.4,
                "prompt.request": {
                    "prompt": "Write a LinkedIn post about endpoint security.",
                    "capability": "writing",
                    "prompt_version": "1.0",
                    "response_format": "json",
                    "valid": True,
                },
            },
        ),
    )
    assert result.success
    assert result.context.get("content.finalized") is True or result.context.get(
        "content.generation_ok"
    )
