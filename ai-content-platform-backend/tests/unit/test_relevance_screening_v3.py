"""Precision-first relevance classification and batch invariants."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from app.core.constants import ArticleStatus
from app.modules.intelligence.application.scorer import RelevanceScorer
from app.modules.intelligence.application.screening_batches import (
    BATCH_SIZE,
    SCREENING_CONCURRENCY,
)
from app.modules.intelligence.application.workflow import (
    _resolve_article_status,
    _same_story,
)


def test_batch_is_100_with_safe_concurrency() -> None:
    assert BATCH_SIZE == 100
    assert 5 <= SCREENING_CONCURRENCY <= 10


def test_binary_outcome_keeps_useful_score_three_articles() -> None:
    assert _resolve_article_status(5, decision="relevant") == ArticleStatus.RELEVANT
    assert _resolve_article_status(4, decision="relevant") == ArticleStatus.RELEVANT
    assert _resolve_article_status(3, decision="relevant") == ArticleStatus.RELEVANT
    assert _resolve_article_status(2, decision="relevant") == ArticleStatus.IRRELEVANT
    assert _resolve_article_status(5, decision="recommended") == ArticleStatus.RELEVANT
    assert _resolve_article_status(5, decision="reference") == ArticleStatus.IRRELEVANT
    assert _resolve_article_status(5, decision="rejected") == ArticleStatus.IRRELEVANT


def test_local_duplicate_guard_matches_same_cve_and_similar_story() -> None:
    assert _same_story(
        "Critical SharePoint RCE CVE-2026-63520 fixed",
        "Rapid7 analysis of CVE-2026-63520 SharePoint remote code execution",
    )
    assert _same_story(
        "Microsoft August Patch Tuesday fixes actively exploited Windows zero-day",
        "Actively exploited Windows zero-day fixed in Microsoft August Patch Tuesday",
    )
    assert not _same_story(
        "Microsoft Teams credential theft through hotel Wi-Fi portals",
        "macOS infostealer bypasses default endpoint protections",
    )


def test_parser_rejects_contradictory_low_score_recommendation() -> None:
    scorer = RelevanceScorer(None, orchestrator=object())  # type: ignore[arg-type]
    result = scorer._parse_response(
        json.dumps(
            {
                "decision": "relevant",
                "score": 2,
                "sector": "cross-sector",
                "framework": "none",
                "audience": "both",
                "article_type": "standalone",
                "quality": {"subject_fit": 4},
                "angle": "Generic patching reminder",
                "reason": "Cyber-related but thin",
            }
        )
    )
    assert result.decision == "rejected"
    assert result.score == 2
    assert result.article_type == "reject"


def test_prompt_v4_requires_binary_editorial_quality_gates_and_article_body() -> None:
    path = Path(__file__).resolve().parents[2] / "configs" / "prompts" / "relevance_scoring.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["version"] == "4.2"
    body = data["body"]
    for phrase in (
        "audience_fit",
        "actionability",
        "educational_value",
        "freshness",
        "distinctiveness",
        "brand_authority",
        "5–70 person regulated firm",
        "decision\": \"relevant | rejected",
        "Body: {article_body}",
        "ACCEPTED-NEWS BENCHMARK",
    ):
        assert phrase in body


def test_original_three_news_sources_are_top_priority() -> None:
    path = (
        Path(__file__).resolve().parents[2]
        / "configs"
        / "news"
        / "sources"
        / "enterprise_free_sources.yaml"
    )
    catalog = yaml.safe_load(path.read_text(encoding="utf-8"))["sources"]
    by_id = {item["catalog_id"]: item for item in catalog}

    assert by_id["ncsc_uk"]["priority"] == 300
    assert by_id["msrc_security"]["priority"] == 290
    assert by_id["the_hacker_news"]["priority"] == 280
    assert by_id["ncsc_uk"]["config"]["feed_url"].endswith("all-rss-feed.xml")
    assert by_id["msrc_security"]["connector_type"] == "msrc"
    assert max(
        item["priority"]
        for item in catalog
        if item["catalog_id"] not in {"ncsc_uk", "msrc_security", "the_hacker_news"}
    ) < 280
