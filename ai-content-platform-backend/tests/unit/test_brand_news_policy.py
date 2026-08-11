"""Unit tests for Brand → news policy query building and scoring boosts."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.modules.brand_intelligence.application.news_policy_service import (
    BrandNewsPolicyService,
    build_search_query,
    topic_overlap_score,
)
from app.modules.brand_intelligence.domain.news_policy import BrandNewsPolicy
from app.modules.news.application.scorer import DeterministicNewsScorer
from app.modules.news.domain.models import CanonicalArticle, NewsPolicy, TopicSignals


def test_build_search_query_quotes_phrases() -> None:
    q = build_search_query(["cybersecurity", "Microsoft 365", "DSPT"], max_terms=8)
    assert "cybersecurity" in q
    assert '"Microsoft 365"' in q
    assert " OR " in q


def test_topic_overlap_score_detects_brand_terms() -> None:
    score = topic_overlap_score(
        "NHS care home hit by ransomware phishing email",
        ["ransomware", "care home", "DSPT", "VoIP"],
    )
    assert score > 0.2


def test_relevance_profile_has_weight_sections() -> None:
    policy = BrandNewsPolicy(
        organization_id=uuid.uuid4(),
        brand_profile_id=uuid.uuid4(),
        topics=["cyber", "dspt"],
        industries=["cybersecurity"],
        audience="care providers",
        strategic_goal="Trusted MSP",
        weight_up=["DSPT", "Cyber Essentials"],
        weight_down=["celebrity"],
        primary_query="cybersecurity OR DSPT",
        source="test",
    )
    md = BrandNewsPolicyService.relevance_profile_markdown(
        BrandNewsPolicyService.__new__(BrandNewsPolicyService),
        policy,
        brand_name="Guard IQ",
    )
    assert "## 7. Weight up / Weight down or exclude" in md
    assert "DSPT" in md
    assert "Guard IQ" in md


def test_deterministic_scorer_boosts_brand_hits() -> None:
    art = CanonicalArticle(
        title="Care provider DSPT ransomware phishing attack",
        url="https://example.com/a",
        canonical_url="https://example.com/a",
        summary="Microsoft 365 email security failure",
        body_text="",
        published_at=datetime.now(timezone.utc),
        organization_id=uuid.uuid4(),
        content_hash="abc",
    )
    topic = TopicSignals(
        category="threat",
        industry="healthcare",
        threat="ransomware",
        technology="microsoft",
        country="UK",
        company="",
        framework="dspt",
        urgency=0.7,
        trend=0.5,
        business_impact=0.6,
        confidence=0.5,
    )
    scorer = DeterministicNewsScorer()
    base = scorer.score(art, topic=topic, source=None, policy=NewsPolicy())
    boosted = scorer.score(
        art,
        topic=topic,
        source=None,
        policy=NewsPolicy(),
        brand_terms=["dspt", "ransomware", "phishing", "microsoft 365", "care"],
        exclude_terms=["celebrity"],
    )
    assert boosted.organization_relevance >= base.organization_relevance
    assert boosted.composite >= base.composite
