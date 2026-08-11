"""Unit tests for Opportunity composer + Strategist briefing (Phase 1)."""

from __future__ import annotations

from uuid import uuid4

from app.modules.content.application.opportunity_composer import (
    build_recommendation,
    clamp_score,
    compute_confidence_factors,
    load_opportunity_ranking_config,
    map_angles,
    opportunity_id_for,
    timeline_bucket_for,
    title_similarity,
    tokenize,
)
from app.modules.content.application.strategist_briefing import (
    build_strategist_briefing,
    clamp_mix,
)


def test_ranking_config_loads() -> None:
    load_opportunity_ranking_config.cache_clear()
    cfg = load_opportunity_ranking_config()
    assert "weights" in cfg
    assert cfg["weights"]["relevance"] > 0


def test_title_similarity_and_tokenize() -> None:
    assert "microsoft" in tokenize("Microsoft Exchange CVE-2024")
    assert title_similarity("Microsoft Exchange Online", "Microsoft Exchange patch") >= 0.3
    assert title_similarity("Azure DNS", "Healthcare compliance") < 0.2


def test_opportunity_id_stable() -> None:
    a, b = uuid4(), uuid4()
    assert opportunity_id_for([a, b]) == opportunity_id_for([b, a])
    assert opportunity_id_for([a]).startswith("opp_")


def test_confidence_factors_blend() -> None:
    conf = compute_confidence_factors(
        relevance=90,
        tags=["security_advisory"],
        tag_weights={"security_advisory": 0.2},
        trend_score=0.9,
        age_hours=8,
        audience="healthcare",
        competition_count=0,
        soft_cap=3,
        weights={
            "relevance": 0.35,
            "opportunity_tags": 0.15,
            "trend": 0.15,
            "freshness": 0.15,
            "audience_fit": 0.1,
            "competition": 0.1,
        },
    )
    assert 0 <= conf["composite"] <= 100
    assert conf["freshness"] >= 90
    assert conf["competition"] >= 80
    # High competition lowers score
    crowded = compute_confidence_factors(
        relevance=90,
        tags=[],
        tag_weights={},
        trend_score=0.5,
        age_hours=8,
        audience="healthcare",
        competition_count=5,
        soft_cap=3,
        weights={
            "relevance": 0.35,
            "opportunity_tags": 0.15,
            "trend": 0.15,
            "freshness": 0.15,
            "audience_fit": 0.1,
            "competition": 0.1,
        },
    )
    assert crowded["competition"] < conf["competition"]


def test_timeline_and_recommendation() -> None:
    bucket, advice = timeline_bucket_for(freshness=96, trend=80, age_hours=6)
    assert bucket == "today"
    assert "today" in advice.lower() or "Post" in advice
    wait_bucket, wait_advice = timeline_bucket_for(freshness=50, trend=90, age_hours=40)
    assert wait_bucket == "this_week"
    assert "evolving" in wait_advice.lower() or "week" in wait_advice.lower()

    rec = build_recommendation(
        {
            "composite": 92,
            "authority": 95,
            "audience_fit": 90,
            "competition": 88,
            "trend": 90,
            "freshness": 96,
            "timing": 90,
        },
        ["Matches profile"],
    )
    assert rec["should_generate"] is True
    assert rec["stars"] == 5
    assert "High authority" in rec["why"]


def test_map_angles() -> None:
    primary, alts = map_angles(
        ["checklist", "myth_vs_fact"],
        {"checklist": "Checklist", "myth_vs_fact": "Myth vs Fact"},
    )
    assert primary == "Checklist"
    assert "Myth vs Fact" in alts


def test_strategist_briefing_narrative() -> None:
    opps = [
        {
            "id": "opp_1",
            "title": "Microsoft Exchange Security",
            "priority": "high",
            "timeline_bucket": "today",
            "timing_advice": "Post today",
            "opportunity_score": 94,
            "audiences": ["healthcare"],
            "primary_angle": "Educational",
            "primary_article_id": str(uuid4()),
            "recommendation": {"should_generate": True, "stars": 5},
            "duplicate": {"already_covered": False},
        }
    ]
    summary = {
        "articles_analysed": 100,
        "opportunities": 1,
        "trends": 2,
        "high_priority": 1,
        "recommended_today": 1,
        "already_scheduled": 0,
        "needs_review": 0,
        "average_opportunity_score": 94,
        "plan_health": {
            "counts": {"educational": 2, "success_story": 0, "personal_achievement": 0},
            "target": {"total": 10},
            "gaps": {"educational": 4, "success_story": 3, "personal_achievement": 1},
        },
        "review_queue": [],
    }
    out = build_strategist_briefing(
        opportunities=opps,
        summary=summary,
        trends=[{"topic_key": "microsoft"}],
        brand={},
        memory=["Healthcare is underrepresented this fortnight."],
        config={"default_strategic_goal": "Be the trusted advisor."},
    )
    assert out["greeting"]
    assert len(out["narrative"]) >= 1
    assert out["recommended_action"]["opportunity_id"] == "opp_1"
    assert out["strategic_goal"]["progress_pct"] == clamp_mix(20, 94)
    assert out["memory"]
    assert clamp_score(150) == 100
    assert isinstance(out["briefing"]["articles_analysed"], int)


def test_clamp_mix() -> None:
    assert 0 <= clamp_mix(50, 80) <= 100
