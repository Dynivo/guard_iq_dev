"""Unit tests for Brand Intelligence engines, connectors, and merge."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from app.modules.brand_intelligence.application.engines.core import (
    DefaultCompletenessEngine,
    DefaultHealthEngine,
    DefaultRecommendationEngine,
    DefaultSemanticMergeEngine,
    HeuristicCtaAnalyzer,
    HeuristicEngagementAnalyzer,
    HeuristicHookAnalyzer,
    HeuristicTopicAnalyzer,
    HeuristicVocabularyAnalyzer,
    HeuristicWritingAnalyzer,
    fingerprint_text,
)
from app.modules.brand_intelligence.domain.models import (
    CanonicalBrandObject,
    CboObjectType,
    CboSourceType,
)
from app.modules.brand_intelligence.infrastructure.connectors.registry import (
    ConnectorRegistry,
    LinkedInConnector,
    UploadConnector,
)
from app.modules.typography.application.renderer import _logo_box
from app.modules.typography.domain.models import LogoPlacementOptions as TyLogoOptions


def _cbo(**kwargs) -> CanonicalBrandObject:
    org = kwargs.pop("organization_id", uuid.uuid4())
    profile = kwargs.pop("brand_profile_id", uuid.uuid4())
    return CanonicalBrandObject(
        id=kwargs.pop("id", uuid.uuid4()),
        organization_id=org,
        brand_profile_id=profile,
        import_id=kwargs.pop("import_id", None),
        object_type=kwargs.pop("object_type", CboObjectType.POST),
        source_type=kwargs.pop("source_type", CboSourceType.LINKEDIN),
        fingerprint=kwargs.pop("fingerprint", fingerprint_text("t", str(uuid.uuid4()))),
        title=kwargs.pop("title", None),
        body_text=kwargs.pop("body_text", None),
        engagement=kwargs.pop("engagement", {}),
        metadata_json=kwargs.pop("metadata_json", {}),
        **kwargs,
    )


def test_fingerprint_stable() -> None:
    a = fingerprint_text("li", "https://linkedin.com/in/x", "hello")
    b = fingerprint_text("li", "https://linkedin.com/in/x", "hello")
    assert a == b
    assert len(a) == 40


def test_writing_and_topic_analyzers() -> None:
    objects = [
        _cbo(
            body_text="Why cloud security matters for compliance teams. Book a demo today.",
            object_type=CboObjectType.POST,
        ),
        _cbo(
            title="About",
            body_text="We help healthcare and cyber clients with identity.",
            object_type=CboObjectType.PROFILE,
        ),
    ]

    async def _run() -> None:
        writing = await HeuristicWritingAnalyzer().analyze(objects)
        topics = await HeuristicTopicAnalyzer().analyze(objects)
        vocab = await HeuristicVocabularyAnalyzer().analyze(objects)
        hooks = await HeuristicHookAnalyzer().analyze(objects)
        ctas = await HeuristicCtaAnalyzer().analyze(objects)
        eng = await HeuristicEngagementAnalyzer().analyze(objects)
        assert writing["tone"] == "professional"
        assert any(
            t["label"] in ("security", "cloud", "compliance", "healthcare", "cyber", "identity")
            for t in topics
        )
        assert vocab["preferred"]
        assert hooks
        assert ctas
        assert eng["post_count"] == 1

    asyncio.run(_run())


def test_semantic_merge_completeness_health_recs() -> None:
    org = uuid.uuid4()
    profile = uuid.uuid4()
    objects = [
        _cbo(
            organization_id=org,
            brand_profile_id=profile,
            body_text="How to stop phishing. Learn more about identity security.",
            object_type=CboObjectType.POST,
            source_type=CboSourceType.LINKEDIN,
            engagement={"reactions": 10, "comments": 2},
        ),
        _cbo(
            organization_id=org,
            brand_profile_id=profile,
            title="Mission",
            body_text="Our mission is secure cloud for every SMB.",
            object_type=CboObjectType.PAGE,
            source_type=CboSourceType.WEBSITE,
        ),
    ]

    async def _run() -> dict:
        writing = await HeuristicWritingAnalyzer().analyze(objects)
        topics = await HeuristicTopicAnalyzer().analyze(objects)
        vocab = await HeuristicVocabularyAnalyzer().analyze(objects)
        hooks = await HeuristicHookAnalyzer().analyze(objects)
        ctas = await HeuristicCtaAnalyzer().analyze(objects)
        engagement = await HeuristicEngagementAnalyzer().analyze(objects)
        return {
            "writing": writing,
            "topics": topics,
            "vocabulary": vocab,
            "hooks": hooks,
            "ctas": ctas,
            "engagement": engagement,
            "vision": [],
        }

    analyses = asyncio.run(_run())
    draft = DefaultSemanticMergeEngine().merge(objects, analyses, org, profile)
    assert draft.confidence > 0
    assert draft.writing_dna
    comp = DefaultCompletenessEngine().score(
        draft, {"sources": ["linkedin", "website"], "has_logo": False, "has_guidelines": False}
    )
    assert 0 <= comp.overall_brand_score <= 100
    health = DefaultHealthEngine().evaluate(draft, comp)
    assert isinstance(health.missing_assets, list)
    assert "logo" in health.missing_assets
    recs = DefaultRecommendationEngine().recommend(draft, comp, health)
    assert isinstance(recs, list)
    assert recs
    assert all(hasattr(r, "code") for r in recs)


def test_linkedin_connector_url_seed() -> None:
    org = uuid.uuid4()
    profile = uuid.uuid4()

    async def _run() -> list:
        return await LinkedInConnector().fetch(
            {
                "organization_id": str(org),
                "brand_profile_id": str(profile),
                "linkedin_url": "https://www.linkedin.com/company/example",
                "about": "We sell security.",
                "headline": "Cyber MSP",
                "posts": ["Stop invoice fraud today. Book a call."],
            }
        )

    objects = asyncio.run(_run())
    assert len(objects) >= 2
    assert objects[0].source_type == CboSourceType.LINKEDIN
    assert objects[0].object_type == CboObjectType.PROFILE


def test_upload_connector_artifacts() -> None:
    org = uuid.uuid4()
    profile = uuid.uuid4()

    async def _run() -> list:
        return await UploadConnector().fetch(
            {
                "organization_id": str(org),
                "brand_profile_id": str(profile),
                "artifacts": [
                    {
                        "kind": "guideline",
                        "filename": "brand.pdf",
                        "storage_key": "org/brand.pdf",
                        "extracted_text": "Never say cheap. Prefer enterprise.",
                    },
                    {"kind": "logo", "storage_key": "org/logo.png", "variant": "primary"},
                ],
            }
        )

    objects = asyncio.run(_run())
    assert any(o.object_type == CboObjectType.GUIDELINE for o in objects)
    assert any(o.object_type == CboObjectType.MEDIA for o in objects)


def test_connector_registry_future_stubs() -> None:
    reg = ConnectorRegistry()
    assert reg.get("linkedin")
    assert reg.get("website")
    assert reg.get("upload")
    assert reg.get("youtube")  # stub present, not a scraper
    with pytest.raises(KeyError):
        reg.get("not-a-real-source")


def test_logo_box_positions() -> None:
    opts = TyLogoOptions(position="top_right", size="m", margin=0.04)
    x, y, w, h = _logo_box(width=1000, height=1000, options=opts)
    assert w == h
    assert x > 500
    assert y < 100
    custom = TyLogoOptions(position="custom", custom_x=0.1, custom_y=0.2, size="s")
    cx, cy, _, _ = _logo_box(width=1000, height=1000, options=custom)
    assert abs(cx - 100) < 1
    assert abs(cy - 200) < 1


def test_typography_logo_options_roundtrip() -> None:
    opts = TyLogoOptions.from_dict(
        {
            "include_logo": True,
            "position": "bottom_left",
            "size": "L",
            "opacity": 0.8,
            "margin": 0.05,
        }
    )
    assert opts.size == "l"
    assert opts.opacity == 0.8
    assert opts.to_dict()["position"] == "bottom_left"
