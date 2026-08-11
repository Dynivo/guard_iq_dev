"""Mock AI provider — returns deterministic JSON for relevance/content when no API keys available.

CRITICAL for local demo: produces valid structured output so the full pipeline
can run end-to-end without real provider credentials.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import AsyncIterator

from app.core.logging import get_logger
from app.infrastructure.llm.base import CompletionRequest, CompletionResult

logger = get_logger(__name__)


def _deterministic_seed(text: str) -> int:
    return int(hashlib.md5(text.encode()).hexdigest()[:8], 16)


def _mock_relevance_response(prompt: str) -> str:
    seed = _deterministic_seed(prompt)
    score = (seed % 5) + 1
    sectors = ["care", "healthcare", "legal", "accountancy", "cross-sector"]
    frameworks = ["DSPT", "CyberEssentials", "GDPR", "SRA", "FRC", "CQC", "none"]
    audiences = ["reactive", "managed", "both"]

    return json.dumps({
        "relevant": score >= 3,
        "score": score,
        "sector": sectors[seed % len(sectors)],
        "framework": frameworks[seed % len(frameworks)],
        "audience": audiences[seed % len(audiences)],
        "angle": "Mock angle: demonstrates platform capability without real AI provider",
        "reason": f"Mock scoring — deterministic score {score} based on content hash",
    })


def _extract_topic(prompt: str) -> str:
    """Best-effort topic extraction from writing prompts for grounded mock drafts."""
    import re

    for pattern in (
        r"Topic:\s*(.+)",
        r"Write a LinkedIn\s+\w+\s+post about:\s*(.+)",
        r"about:\s*(.+)",
    ):
        m = re.search(pattern, prompt, re.IGNORECASE)
        if m:
            topic = m.group(1).strip().splitlines()[0].strip()
            if topic and len(topic) > 8:
                return topic[:180]
    # Fall back to first non-empty substantial line
    for line in prompt.splitlines():
        clean = line.strip().lstrip("#").strip()
        if len(clean) > 40 and "json" not in clean.lower():
            return clean[:180]
    return "this week's industry news"


def _mock_content_response(prompt: str) -> str:
    seed = _deterministic_seed(prompt)
    topic = _extract_topic(prompt)
    hooks = [
        f"Big move this week: {topic}",
        f"What {topic} means for operators and investors",
        f"A closer look at {topic}",
    ]
    ctas = [
        "What do you make of this — opportunity or noise? Comment below.",
        "Save this for your next market briefing.",
        "Follow for more practical breakdowns of industry news.",
    ]
    hashtags = ["#Business", "#Leadership", "#MarketNews", "#LinkedIn", "#Insights"]
    body = (
        f"{topic}\n\n"
        "Here's the practical takeaway: the headline matters less than the operating "
        "implications underneath it — who benefits, what changes for customers, and "
        "where execution risk sits.\n\n"
        "If you lead a team in this space, use this as a prompt to pressure-test your "
        "assumptions: capacity, partnerships, and capital allocation.\n\n"
        "The firms that win here usually act on signal early — not after the narrative "
        "is already priced in."
    )

    return json.dumps({
        "hook": hooks[seed % len(hooks)][:220],
        "body": body,
        "cta": ctas[seed % len(ctas)],
        "hashtags": hashtags[: (seed % 3) + 3],
        "variations": [
            {
                "hook": hooks[(seed + 1) % len(hooks)][:220],
                "body": f"Alternative angle on {topic}: focus on the customer impact first.",
            },
            {
                "hook": hooks[(seed + 2) % len(hooks)][:220],
                "body": f"Different take on {topic}: what operators should watch next quarter.",
            },
        ],
    })


def _wants_relevance(prompt: str) -> bool:
    """Detect relevance-scoring prompts without false-matching writing prompts.

    Writing templates often contain words like "scored article" or "relevance_angle",
    which previously caused empty drafts (relevance JSON has no hook/body/cta).
    """
    p = prompt.lower()
    content_markers = (
        "linkedin",
        '"hook"',
        "hashtags",
        "write a linkedin",
        "content_type",
        "cta",
        "carousel",
    )
    if any(m in p for m in content_markers):
        return False
    relevance_markers = (
        "score an article",
        "relevance screening",
        "relevance scoring",
        '"relevant"',
        '"sector"',
        '"framework"',
        "evaluate the article against",
    )
    if any(m in p for m in relevance_markers):
        return True
    # Narrow fallback: both words appear as scoring intent, not writing context
    return "relevance" in p and "score" in p and "hook" not in p


class MockAIProvider:
    """Deterministic mock provider for demo/testing without real API keys."""

    @property
    def provider_name(self) -> str:
        return "mock"

    def _render(self, request: CompletionRequest) -> str:
        if _wants_relevance(request.prompt):
            return _mock_relevance_response(request.prompt)
        return _mock_content_response(request.prompt)

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        start = time.perf_counter_ns()
        text = self._render(request)
        latency_ms = (time.perf_counter_ns() - start) // 1_000_000
        logger.info(
            "Mock completion: correlation_id=%s latency=%dms",
            request.correlation_id,
            latency_ms,
        )
        return CompletionResult(
            text=text,
            model="mock-v1",
            provider=self.provider_name,
            latency_ms=latency_ms,
            tokens_in=len(request.prompt.split()),
            tokens_out=len(text.split()),
            cost_estimate=0.0,
        )

    async def complete_stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        text = self._render(request)
        chunk_size = max(8, len(text) // 4)
        for i in range(0, len(text), chunk_size):
            yield text[i : i + chunk_size]
