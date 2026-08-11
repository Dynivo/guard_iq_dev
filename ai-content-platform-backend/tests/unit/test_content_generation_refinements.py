"""Unit tests for M9r Content Generation Engine refinements."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.modules.content.application.generation.engine import (
    DefaultContentGenerationEngine,
    FakeOrchestrator,
)
from app.modules.content.application.generation.factory import ContentGenerationFactory
from app.modules.content.application.generation.regenerator import DefaultDraftRegenerator
from app.modules.content.application.generation.safety import DefaultContentSafetyValidator
from app.modules.content.application.generation.visual_brief import DefaultVisualBriefGenerator
from app.modules.content.domain.models import (
    GenerationRequest,
    RegenSection,
    StructuredDraft,
)
from app.modules.prompts.domain.models import PromptRequest

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
async def test_visual_brief_never_generates_images() -> None:
    engine = ContentGenerationFactory.create_memory()
    result = await engine.generate(
        GenerationRequest(
            prompt_request=_prompt(),
            source_text="DSPT compliance guidance for healthcare.",
            content_plan={
                "image_style": "branded_illustration",
                "visual_direction": "calm professional scene",
                "tone": "professional",
                "content_type": "compliance_update",
            },
            context_metadata={
                "entities": ["microsoft"],
                "topics": ["DSPT"],
                "trend_score": 0.7,
                "opportunity_types": ["compliance_update"],
                "audience": "healthcare",
            },
        )
    )
    assert result.success
    assert result.draft is not None
    brief = result.draft.visual_brief
    assert brief is not None
    assert hasattr(brief, "to_dict")
    d = brief.to_dict()
    assert d["illustration_style"]
    assert d["scene"]
    assert d["negative_prompt"]
    assert "http" not in d["scene"].lower()
    assert result.draft.metadata.get("image_brief")
    assert result.draft.metadata["visual_brief"]["metadata"]["never_generates_images"] is True


@pytest.mark.asyncio
async def test_quality_breakdown_independent_scores() -> None:
    engine = ContentGenerationFactory.create_memory()
    result = await engine.generate(
        GenerationRequest(
            prompt_request=_prompt(),
            source_text="DSPT compliance guidance for healthcare organisations.",
        )
    )
    assert result.success
    q = result.quality
    assert q is not None
    data = q.to_dict()
    for key in (
        "grammar",
        "readability",
        "brand",
        "fact",
        "tone",
        "engagement",
        "originality",
        "structure",
    ):
        assert key in data
        assert 0.0 <= data[key] <= 1.0
    assert "composite" in data
    assert result.draft is not None
    assert result.draft.quality_score == q.composite()


@pytest.mark.asyncio
async def test_draft_metadata_from_context() -> None:
    engine = ContentGenerationFactory.create_memory()
    result = await engine.generate(
        GenerationRequest(
            prompt_request=_prompt(),
            source_text="DSPT guidance.",
            content_plan={"audience": "it_managers", "tone": "professional", "cta": "comment"},
            context_metadata={
                "entities": ["azure", "CVE-2024-1"],
                "topics": ["cloud security"],
                "trend_score": 0.82,
                "opportunity_types": ["security_advisory"],
            },
        )
    )
    assert result.success
    meta = result.draft.draft_metadata
    assert meta is not None
    d = meta.to_dict()
    assert "azure" in d["entities"]
    assert d["trend_score"] == 0.82
    assert "security_advisory" in d["opportunity_types"]
    assert d["prompt_version"] == "1.0"
    assert d["generation_metadata"].get("replay_id")


@pytest.mark.asyncio
async def test_content_safety_flags_sensitive_language() -> None:
    safety = DefaultContentSafetyValidator(CONFIGS / "content" / "generation")
    draft = StructuredDraft(
        hook="A calm professional tip",
        body="This contains hate speech and should be blocked.",
        cta="Comment below.",
    )
    out = safety.validate(draft)
    assert out.safe is False
    assert out.sensitive_language is True


@pytest.mark.asyncio
async def test_content_safety_blocks_generation() -> None:
    bad = FakeOrchestrator(
        response_text=(
            '{"hook":"Serious security update for teams everywhere today.",'
            '"body":"Our product is 100% secure forever and never be breached under any condition.",'
            '"cta":"Comment with your thoughts on this topic.",'
            '"hashtags":["Security"]}'
        )
    )
    engine = DefaultContentGenerationEngine(bad)
    result = await engine.generate(
        GenerationRequest(
            prompt_request=_prompt(),
            source_text="A routine advisory about patching endpoints.",
        )
    )
    assert result.success is False
    assert result.safety is not None
    assert result.safety.safe is False or result.draft.lifecycle_status == "rejected"


@pytest.mark.asyncio
async def test_regenerate_hook_only() -> None:
    orch = FakeOrchestrator(
        response_text='{"hook":"Fresh hook about DSPT for care leaders."}'
    )
    engine = DefaultContentGenerationEngine(orch)
    # Seed a draft via full generate with separate orch first
    base_engine = ContentGenerationFactory.create_memory()
    base = await base_engine.generate(
        GenerationRequest(
            prompt_request=_prompt(),
            source_text="DSPT compliance guidance for healthcare.",
        )
    )
    assert base.success and base.draft
    original_body = base.draft.body
    original_cta = base.draft.cta
    regen = DefaultDraftRegenerator(orch, engine)
    updated = await regen.regenerate(base.draft, RegenSection.HOOK)
    assert updated.hook == "Fresh hook about DSPT for care leaders."
    assert updated.body == original_body
    assert updated.cta == original_cta
    versions = engine.lifecycle.list_versions(updated.metadata["draft_id"])
    assert any(v.change_summary.startswith("regenerated:") for v in versions)


@pytest.mark.asyncio
async def test_visual_brief_generator_standalone() -> None:
    gen = DefaultVisualBriefGenerator(CONFIGS / "content" / "generation")
    brief = gen.generate(
        StructuredDraft(hook="Hook", body="Body", content_type="checklist", format="carousel"),
        content_plan={"image_style": "flat_vector", "tone": "educational"},
    )
    assert brief.illustration_style == "flat_vector"
    assert "checklist" in brief.icon_suggestions or brief.icon_suggestions
    assert "url" not in brief.to_dict()
