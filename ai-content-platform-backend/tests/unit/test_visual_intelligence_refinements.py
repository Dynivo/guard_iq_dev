"""Unit tests for M10r Visual Intelligence refinements."""

from __future__ import annotations

import asyncio

from app.modules.image.application.factory import VisualIntelligenceFactory
from app.modules.image.application.layout import DefaultLayoutPlanner
from app.modules.image.domain.models import (
    CompositionPlan,
    EnrichedVisualBrief,
    ImagePipelineRequest,
    ScenePlan,
)
from app.modules.workflow.application.factory import WorkflowFactory


def _draft() -> dict:
    return {
        "id": "d1",
        "hook": "Stop invoice fraud before it hits finance",
        "body": "Practical controls for BEC.",
        "cta": "Follow for more",
        "content_type": "security_alert",
        "format": "single",
        "visual_brief": {
            "illustration_style": "branded_illustration",
            "scene": "finance desk with alert cues",
            "negative_prompt": "text, watermark, logo, blurry",
            "typography_safe_area": "bottom_third",
            "color_palette": ["#0A1F2B", "#1A5CB0"],
            "visual_intent": "inform_and_engage",
            "emotion": "calm_confidence",
            "icon_suggestions": ["shield", "invoice"],
        },
        "metadata": {},
    }


def test_layout_plan_regions_never_renders_text() -> None:
    brief = EnrichedVisualBrief(
        typography_safe_area="bottom_third",
        icons=("shield", "invoice"),
    )
    scene = ScenePlan(icons=("shield", "invoice"), reading_direction="ltr_top_to_bottom")
    composition = CompositionPlan(width=1080, height=1350)
    layout = DefaultLayoutPlanner().plan(
        brief=brief, scene=scene, composition=composition, image_width=1080, image_height=1350
    )
    assert layout.title is not None
    assert layout.subtitle is not None
    assert layout.cta is not None
    assert layout.logo is not None
    assert layout.footer is not None
    assert layout.illustration_safe is not None
    assert layout.icon_regions
    assert layout.whitespace_map
    assert layout.alignment_guides
    assert layout.metadata.get("never_renders_text") is True
    # Ensure no typography module import path
    import app.modules.image.application.layout as layout_mod

    assert "typography" not in layout_mod.__file__


def test_quality_breakdown_independent_scores() -> None:
    async def _run() -> None:
        eng = VisualIntelligenceFactory.create_memory()
        result = await eng.run(
            ImagePipelineRequest(
                organization_id="org1",
                draft_id="d1",
                draft=_draft(),
                brand={"name": "GuardIQ", "primary_color": "#0A1F2B"},
            )
        )
        assert result.status == "completed"
        assert result.quality is not None
        q = result.quality.to_dict()
        for key in (
            "composition",
            "contrast",
            "brand_alignment",
            "whitespace",
            "typography_safety",
            "aesthetic",
            "artifact",
        ):
            assert key in q
        assert result.quality_score == result.quality.composite()
        assert result.validation.breakdown is not None

    asyncio.run(_run())


def test_asset_intelligence_and_embedding() -> None:
    async def _run() -> None:
        eng = VisualIntelligenceFactory.create_memory()
        result = await eng.run(
            ImagePipelineRequest(
                organization_id="org1",
                draft_id="d1",
                draft=_draft(),
                brand={"primary_color": "#0A1F2B", "accent_color": "#1A5CB0"},
            )
        )
        assert result.layout is not None
        assert result.asset_intelligence is not None
        assert result.asset_intelligence.dominant_colors
        assert result.asset_intelligence.ocr_regions
        assert result.asset_intelligence.safe_crop_areas
        assert result.asset_intelligence.metadata.get("no_ocr_engine") is True
        assert result.embedding is not None
        assert result.embedding.dimensions > 0
        assert result.seed is not None

    asyncio.run(_run())


def test_similarity_and_duplicates() -> None:
    async def _run() -> None:
        eng = VisualIntelligenceFactory.create_memory()
        a = await eng.run(
            ImagePipelineRequest(organization_id="org1", draft_id="d1", draft=_draft(), brand={})
        )
        b = await eng.run(
            ImagePipelineRequest(organization_id="org1", draft_id="d2", draft=_draft(), brand={})
        )
        assert a.embedding and b.embedding
        similar = eng.embedding_service.similar(a.job_id)
        assert any(jid == b.job_id for jid, _ in similar)
        # Same prompt/mock image → high similarity; duplicates may or may not exceed threshold
        eng.embedding_service.duplicates(a.job_id)
        eng.embedding_service.recommend(a.job_id)

    asyncio.run(_run())


def test_visual_replay_brief_workflow_seed_prompt() -> None:
    async def _run() -> None:
        eng = VisualIntelligenceFactory.create_memory()
        first = await eng.run(
            ImagePipelineRequest(
                organization_id="org1",
                draft_id="d1",
                draft=_draft(),
                brand={"primary_color": "#0A1F2B"},
            )
        )
        assert first.status == "completed"
        record = eng.replay_store.get_by_job(first.job_id)
        assert record is not None
        assert record.visual_brief
        assert record.seed is not None
        assert record.prompt_request
        assert record.workflow_id
        assert record.layout

        second = await eng.replay(job_id=first.job_id)
        assert second.status == "completed"
        assert second.metadata.get("replay_of_job_id") == first.job_id
        assert second.seed == first.seed
        assert second.workflow_id == first.workflow_id
        assert second.prompt_request.positive_prompt == first.prompt_request.positive_prompt

    asyncio.run(_run())


def test_refinement_workflow_nodes_registered() -> None:
    _, _, nodes = WorkflowFactory.create(load_builtins=True)
    for name in ("visual.layout", "image.analyze", "image.embed"):
        assert nodes.get(name) is not None
