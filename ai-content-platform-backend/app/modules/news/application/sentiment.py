"""Article sentiment analysis — multi-label axes for security/IT news.

Uses a lightweight lexicon classifier by default (same enrichment path as
relevance). When an AI orchestrator is provided, optionally refine via LLM
and fall back to the lexicon result on failure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.modules.news.domain.models import CanonicalArticle

# Axis → cue words (lowercase). Confidence scales with hit density.
_AXES: dict[str, tuple[str, ...]] = {
    "risk": (
        "breach",
        "ransomware",
        "exploit",
        "vulnerability",
        "attack",
        "threat",
        "malware",
        "compromise",
        "zero-day",
        "cve-",
    ),
    "urgency": (
        "critical",
        "immediate",
        "urgent",
        "emergency",
        "actively exploited",
        "patch now",
        "outage",
        "breaking",
    ),
    "opportunity": (
        "launch",
        "funding",
        "growth",
        "partnership",
        "innovation",
        "adoption",
        "award",
        "milestone",
    ),
    "regulatory": (
        "gdpr",
        "nis2",
        "cqc",
        "ofsted",
        "ico",
        "compliance",
        "regulation",
        "fine",
        "enforcement",
    ),
    "reassurance": (
        "mitigation",
        "resolved",
        "patched",
        "secure",
        "protected",
        "guidance",
        "best practice",
        "recovery",
    ),
}

_POSITIVE = ("secure", "protect", "improve", "success", "award", "growth", "resolved", "patched")
_NEGATIVE = ("breach", "attack", "fail", "fine", "ransomware", "outage", "exploit", "threat")


@dataclass(frozen=True, slots=True)
class SentimentResult:
    label: str  # positive | negative | neutral | mixed
    confidence: float
    axes: dict[str, float]
    source: str = "lexicon"

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "confidence": round(self.confidence, 4),
            "axes": {k: round(v, 4) for k, v in self.axes.items()},
            "source": self.source,
        }


def analyze_sentiment(article: CanonicalArticle) -> SentimentResult:
    """Lexicon multi-label sentiment for an article."""
    text = f"{article.title} {article.summary} {article.body_text}".lower()
    axes: dict[str, float] = {}
    for axis, cues in _AXES.items():
        hits = sum(1 for c in cues if c in text)
        axes[axis] = min(1.0, hits / max(3.0, len(cues) * 0.25))

    pos = sum(1 for w in _POSITIVE if w in text)
    neg = sum(1 for w in _NEGATIVE if w in text)
    if pos and neg:
        label = "mixed"
        confidence = min(0.9, 0.45 + 0.1 * min(pos, neg))
    elif neg > pos:
        label = "negative"
        confidence = min(0.95, 0.5 + 0.08 * neg)
    elif pos > neg:
        label = "positive"
        confidence = min(0.95, 0.5 + 0.08 * pos)
    else:
        # Fall back to dominant axis
        top_axis = max(axes, key=axes.get) if axes else "risk"
        if axes.get(top_axis, 0) >= 0.35:
            label = "negative" if top_axis in ("risk", "urgency") else "neutral"
            confidence = 0.4 + 0.3 * axes.get(top_axis, 0)
        else:
            label = "neutral"
            confidence = 0.35

    return SentimentResult(label=label, confidence=confidence, axes=axes, source="lexicon")


async def analyze_sentiment_llm(
    article: CanonicalArticle,
    *,
    orchestrator: Any,
    org_id: Any | None = None,
) -> SentimentResult:
    """Optional LLM refinement; falls back to lexicon on any failure."""
    base = analyze_sentiment(article)
    try:
        prompt = (
            "Classify LinkedIn-suitable sentiment for this UK security/IT news article.\n"
            "Return JSON only: {\"label\":\"positive|negative|neutral|mixed\","
            "\"confidence\":0.0-1.0,\"axes\":{\"risk\":0-1,\"urgency\":0-1,"
            "\"opportunity\":0-1,\"regulatory\":0-1,\"reassurance\":0-1}}\n\n"
            f"Title: {article.title}\nSummary: {(article.summary or '')[:800]}\n"
        )
        from app.core.observability import ensure_correlation_id

        result = await orchestrator.complete(
            capability="relevance",
            prompt=prompt,
            correlation_id=ensure_correlation_id(),
            organization_id=org_id,
        )
        text = (getattr(result, "text", None) or getattr(result, "content", None) or "") or ""
        import json
        import re

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return base
        data = json.loads(match.group(0))
        label = str(data.get("label") or base.label).lower()
        if label not in ("positive", "negative", "neutral", "mixed"):
            label = base.label
        conf = float(data.get("confidence") or base.confidence)
        axes = data.get("axes") if isinstance(data.get("axes"), dict) else base.axes
        return SentimentResult(
            label=label,
            confidence=max(0.0, min(1.0, conf)),
            axes={str(k): float(v) for k, v in axes.items()},
            source="llm",
        )
    except Exception:
        return base
