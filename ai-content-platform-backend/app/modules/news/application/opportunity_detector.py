"""Opportunity Detector — metadata enrichment only; never generates content."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.modules.news.domain.models import (
    ArticleCluster,
    CanonicalArticle,
    NewsScore,
    OpportunitySignals,
    OpportunityType,
    TopicSignals,
)

_DEFAULT_DIR = Path(__file__).resolve().parents[4] / "configs" / "news"


class DefaultOpportunityDetector:
    """Assign content-opportunity tags from topic/score/cluster signals."""

    def __init__(self, config_dir: Path | None = None) -> None:
        self._weights: dict[str, float] = {}
        path = (config_dir or _DEFAULT_DIR) / "opportunities.yaml"
        if path.exists():
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(raw, dict):
                self._weights = {
                    str(k): float(v) for k, v in (raw.get("weights") or {}).items()
                }

    def detect(
        self,
        article: CanonicalArticle,
        *,
        topic: TopicSignals,
        score: NewsScore,
        cluster: ArticleCluster | None = None,
        events: list[str] | None = None,
    ) -> OpportunitySignals:
        text = f"{article.title} {article.summary}".lower()
        types: list[str] = []
        reasons: list[str] = []
        events = events or []

        def add(t: OpportunityType, reason: str) -> None:
            if t.value not in types:
                types.append(t.value)
                reasons.append(reason)

        if topic.framework or "compliance" in text or "dspt" in text:
            add(OpportunityType.COMPLIANCE_UPDATE, "framework/compliance signal")
        if topic.threat or "advisory" in text or "cve-" in text:
            add(OpportunityType.SECURITY_ADVISORY, "threat/advisory signal")
        if topic.urgency >= 0.6 or "alert" in text:
            add(OpportunityType.INDUSTRY_ALERT, "urgency/alert signal")
        if "checklist" in text or "steps" in text:
            add(OpportunityType.CHECKLIST, "checklist language")
        if "best practice" in text or "guidance" in text:
            add(OpportunityType.BEST_PRACTICES, "guidance language")
        if "myth" in text or "vs fact" in text or "misconception" in text:
            add(OpportunityType.MYTH_VS_FACT, "myth/fact framing")
        if "faq" in text or "frequently asked" in text:
            add(OpportunityType.FAQ, "faq framing")
        if " vs " in text or "compared" in text or "comparison" in text:
            add(OpportunityType.COMPARISON, "comparison framing")
        if "how to" in text or "explain" in text or "what is" in text:
            add(OpportunityType.EDUCATIONAL, "educational framing")
        if score.composite >= 0.55 and topic.business_impact >= 0.4:
            add(OpportunityType.THOUGHT_LEADERSHIP, "high impact score")
        if cluster and len(cluster.article_urls) >= 2:
            add(OpportunityType.MULTI_ARTICLE_MERGE, "multi-article cluster")
            if len(cluster.article_urls) >= 3:
                add(OpportunityType.WEEKLY_ROUNDUP, "cluster size suggests roundup")
        if any(e in {"breach", "incident", "vulnerability"} for e in events):
            add(OpportunityType.SECURITY_ADVISORY, "security event detected")

        # Weight-adjusted confidence
        if not types:
            return OpportunitySignals()
        base = min(1.0, 0.4 + 0.1 * len(types) + 0.2 * score.confidence)
        boost = sum(self._weights.get(t, 0.05) for t in types)
        confidence = min(1.0, base + boost * 0.1)
        return OpportunitySignals(
            types=tuple(types), confidence=round(confidence, 4), reasons=tuple(reasons)
        )
