"""Unit tests for M10 Visual Intelligence Engine."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.infrastructure.image_generation.deterministic_test_generator import (
    DeterministicTestImageGenerator,
)
from app.infrastructure.image_generation.workflow_registry import FileComfyWorkflowRegistry
from app.modules.image.application.brief import DefaultVisualBriefEnricher
from app.modules.image.application.composition import DefaultCompositionPlanner
from app.modules.image.application.factory import VisualIntelligenceFactory
from app.modules.image.application.optimizer import DefaultImageOptimizer
from app.modules.image.application.policy import DefaultVisualPolicyEngine
from app.modules.image.application.prompt_builder import DefaultImagePromptBuilder
from app.modules.image.application.scene import DefaultScenePlanner
from app.modules.image.application.validator import DefaultImageValidator
from app.modules.image.domain.models import (
    EnrichedVisualBrief,
    ImagePipelineRequest,
    ImagePromptRequest,
)
from app.modules.image.domain.ports import ImageGenerationRequest
from app.modules.workflow.application.factory import WorkflowFactory
from app.modules.workflow.domain.models import WorkflowContext


@pytest.fixture
def draft() -> dict:
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


def test_visual_brief_enrich_never_returns_pixels(draft: dict) -> None:
    brief = DefaultVisualBriefEnricher().enrich(draft, content_plan={"audience": "it_managers"})
    assert brief.theme
    assert brief.audience == "it_managers"
    assert brief.metadata.get("never_generates_images") is True
    blob = str(brief.to_dict())
    assert "http://" not in blob
    assert "data:image" not in blob


def test_scene_and_composition_planners(draft: dict) -> None:
    brief = DefaultVisualBriefEnricher().enrich(draft)
    scene = DefaultScenePlanner().plan(brief, content_plan={"format": "carousel"})
    assert scene.layout
    assert scene.charts
    composition = DefaultCompositionPlanner().plan(brief, scene)
    assert composition.width == 1080
    assert composition.aspect_ratio == "1:1"


def test_policy_and_prompt_builder(draft: dict) -> None:
    brief = DefaultVisualBriefEnricher().enrich(draft)
    scene = DefaultScenePlanner().plan(brief)
    composition = DefaultCompositionPlanner().plan(brief, scene)
    policy = DefaultVisualPolicyEngine().validate(
        brief, scene, composition, brand={"primary_color": "#0A1F2B", "name": "GuardIQ"}
    )
    assert policy.passed
    prompt = DefaultImagePromptBuilder().build(brief, scene, composition, brand={"name": "GuardIQ"})
    assert "no readable text" in prompt.positive_prompt.lower() or "illustration" in prompt.positive_prompt.lower()
    assert prompt.negative_prompt
    assert prompt.metadata.get("never_calls_providers") is True


def test_comfy_registry_loads_without_hardcoded_graph() -> None:
    reg = FileComfyWorkflowRegistry()
    desc = reg.get("flux_dev")
    assert desc.model == "flux-dev"
    graph = reg.load_graph(desc)
    assert "prompt" in graph
    rendered = reg.render_graph(
        desc,
        {
            "positive_prompt": "test scene",
            "negative_prompt": "text",
            "width": 512,
            "height": 512,
            "seed": 1,
            "steps": 4,
            "cfg": 1.0,
        },
    )
    # placeholders substituted
    text = str(rendered)
    assert "{{positive_prompt}}" not in text
    assert "test scene" in text


def test_deterministic_test_generator_and_validator_optimizer() -> None:
    async def _run() -> None:
        gen = DeterministicTestImageGenerator()
        result = await gen.generate(
            ImageGenerationRequest(prompt="secure cloud", width=1080, height=1350)
        )
        assert result.image_bytes[:8] == b"\x89PNG\r\n\x1a\n"
        brief = EnrichedVisualBrief(
            typography_safe_area="bottom_third",
            color_palette=("#0A1F2B", "#1A5CB0"),
            negative_prompt="text, watermark",
        )
        from app.modules.image.domain.models import CompositionPlan

        composition = CompositionPlan(width=1080, height=1350)
        validation = DefaultImageValidator().validate(
            result.image_bytes, composition=composition, brief=brief
        )
        assert validation.file_integrity_ok
        assert validation.passed
        bundle = DefaultImageOptimizer().optimize(
            result.image_bytes, width=1080, height=1350
        )
        assert bundle.thumbnail_bytes
        assert "png" in bundle.formats

    asyncio.run(_run())


def test_full_pipeline_memory(draft: dict) -> None:
    async def _run() -> None:
        eng = VisualIntelligenceFactory.create_memory()
        result = await eng.run(
            ImagePipelineRequest(
                organization_id="org1",
                draft_id="d1",
                draft=draft,
                brand={"name": "GuardIQ", "primary_color": "#0A1F2B"},
            )
        )
        assert result.status == "completed"
        assert result.assets
        assert result.provider == "deterministic_test"
        assert result.prompt_hash
        assert result.quality_score > 0
        # no typography artifacts
        roles = {a.role for a in result.assets}
        assert "original" in roles and "optimized" in roles and "thumbnail" in roles
        assert "branded_png" not in roles

    asyncio.run(_run())


def test_image_diff_and_replay(draft: dict) -> None:
    async def _run() -> None:
        eng = VisualIntelligenceFactory.create_memory()
        a = await eng.run(
            ImagePipelineRequest(organization_id="o", draft_id="d", draft=draft, brand={})
        )
        b = await eng.run(
            ImagePipelineRequest(organization_id="o", draft_id="d", draft=draft, brand={})
        )
        diff = eng.diff_service.diff(a, b)
        assert diff.left_job_id != diff.right_job_id
        assert eng.replay_store.get  # store populated
        assert len(eng.replay_store._items) >= 2

    asyncio.run(_run())


def test_workflow_handlers_registered() -> None:
    _, _, nodes = WorkflowFactory.create(load_builtins=True)
    for name in (
        "visual.brief",
        "visual.scene",
        "visual.compose",
        "image.prompt",
        "image.generate",
        "image.validate",
        "image.optimize",
        "image.store",
    ):
        assert nodes.get(name) is not None


def test_workflow_brief_scene_prompt_nodes(draft: dict) -> None:
    async def _run() -> None:
        from app.modules.image.application.handlers import (
            ImagePromptHandler,
            VisualBriefHandler,
            VisualComposeHandler,
            VisualSceneHandler,
        )

        eng = VisualIntelligenceFactory.create_memory()
        ctx = WorkflowContext(correlation_id="c1", data={"content.draft": draft, "organization_id": "o"})
        from app.modules.workflow.domain.models import WorkflowNode

        node = WorkflowNode(id="n", name="n", type="visual.brief")
        r1 = await VisualBriefHandler(eng).execute(node, ctx)
        assert r1.success
        r2 = await VisualSceneHandler(eng).execute(node, ctx)
        assert r2.success
        r3 = await VisualComposeHandler(eng).execute(node, ctx)
        assert r3.success
        r4 = await ImagePromptHandler(eng).execute(node, ctx)
        assert r4.success
        assert ctx.get("image.prompt_request")

    asyncio.run(_run())


def test_prompt_request_hash_stable() -> None:
    a = ImagePromptRequest(positive_prompt="x", negative_prompt="y", width=10, height=10)
    b = ImagePromptRequest(positive_prompt="x", negative_prompt="y", width=10, height=10)
    assert a.prompt_hash() == b.prompt_hash()
