"""Extract LinkedIn post message signals for visual planning (no LLM)."""

from __future__ import annotations

import re
from typing import Any


def _clean(text: str, limit: int = 180) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    t = re.sub(r"#\w+", "", t).strip()
    return t[:limit].strip(" ,.-")


def extract_message(
    *,
    hook: str = "",
    body: str = "",
    cta: str = "",
    content_type: str = "",
    audience_hint: str = "",
) -> dict[str, Any]:
    """Return structured message fields used by VisualPatternEngine / story."""
    blob = " ".join(p for p in (hook, body, cta) if p)
    lower = blob.lower()
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", body or "") if s.strip()]
    primary = _clean(hook or (sentences[0] if sentences else ""), 160)
    supporting = _clean(sentences[1] if len(sentences) > 1 else (body or "")[:200], 160)
    takeaway = _clean(sentences[-1] if sentences else cta or primary, 140)

    pain = "compliance and operational risk"
    if any(k in lower for k in ("noise", "filter", "deluge", "overwhelm")):
        pain = "news overload / irrelevant headlines"
    elif any(k in lower for k in ("breach", "malware", "vulnerability", "cve-")):
        pain = "undetected security exposure"
    elif any(k in lower for k in ("lawsuit", "due diligence", "partner")):
        pain = "weak partner due diligence"

    audience = audience_hint or "UK care, legal, and accountancy practice managers"
    if any(k in lower for k in ("care", "cqc", "dspt")):
        audience = "UK care / healthcare practice managers"
    elif any(k in lower for k in ("sra", "solicitor", "legal")):
        audience = "UK legal practice managers"
    elif any(k in lower for k in ("fca", "accountanc")):
        audience = "UK accountancy practice managers"

    emotion = "calm_clarity"
    if any(k in lower for k in ("urgent", "critical", "expose", "serious risk")):
        emotion = "vigilant_urgency"
    elif any(k in lower for k in ("proud", "helped", "outcome")):
        emotion = "confident_proof"

    urgency = 0.7 if emotion == "vigilant_urgency" else 0.4
    confidence = 0.75
    complexity = min(1.0, max(0.2, len(blob) / 900))
    words = max(1, len(blob.split()))
    reading_time_sec = max(8, int(words / 3.5))

    business_value = "Protect focus on what regulates and secures the practice"
    if "due diligence" in lower:
        business_value = "Stronger vendor / provider due diligence"
    elif "malware" in lower or "threat" in lower:
        business_value = "Find and resolve hidden software risk"
    elif "filter" in lower or "noise" in lower:
        business_value = "Filter noise; act on UK-relevant compliance signals"

    return {
        "primary_message": primary,
        "supporting_message": supporting,
        "key_takeaway": takeaway,
        "audience": audience,
        "pain_point": pain,
        "desired_emotion": emotion,
        "urgency": urgency,
        "confidence": confidence,
        "complexity": round(complexity, 3),
        "reading_time_sec": reading_time_sec,
        "business_value": business_value,
        "content_type": (content_type or "educational").strip().lower(),
    }
