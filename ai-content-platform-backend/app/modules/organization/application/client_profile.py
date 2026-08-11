"""Load org-scoped client/brand profile Markdown (relevance + generation memory)."""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.infrastructure.postgres.models.branding import BrandKit

logger = get_logger(__name__)

_BRAND_DIR = Path(__file__).resolve().parents[4] / "configs" / "brand"
_DEFAULT_PROFILE_PATH = _BRAND_DIR / "client-profile.md"

# Sections Claude/GPT must produce so relevance scoring + draft gen stay compatible.
PROFILE_SECTION_HEADINGS = (
    "1. The business",
    "2. Target audience",
    "3. Technical and regulatory scope",
    "4. Credentials and differentiators",
    "5. Positioning",
    "6. Relevance test",
    "7. Weight up / Weight down or exclude",
    "8. Voice and LinkedIn rules",
)

PROFILE_GENERATOR_PROMPT = """You are writing a Client Profile used by an AI content platform to:
1) score news articles for relevance, and
2) write LinkedIn posts in the brand's voice.

Produce ONE Markdown document only (no preamble, no code fences). Use these exact section headings:

# Client Profile — Relevance Screening Reference

## 1. The business
What the company sells, services/tiers, geography, and how they position (e.g. security-led vs generalist).

## 2. Target audience
Who content is FOR (size, sector, role, geography). Explicitly list out-of-scope audiences.

## 3. Technical and regulatory scope
Topics they can credibly speak on (frameworks, stack, vendors). Skip what they would not be called about.

## 4. Credentials and differentiators
Proof points and what makes them different — concrete, not slogans.

## 5. Positioning
Short bullet list of voice/positioning rules.

## 6. Relevance test
4–6 must-pass questions for whether a news item becomes a post idea.

## 7. Weight up / Weight down or exclude
Two lists: topics to prefer, and topics to exclude or down-rank.

## 8. Voice and LinkedIn rules
Tone, length, what to avoid (jargon, fear-mongering, clickbait), CTA style.

Rules:
- Be specific to THIS business; no generic SME filler.
- Prefer UK / local regulatory framing unless the business is elsewhere (then match their market).
- Exclusions matter as much as inclusions — most filtering happens there.
- Keep it under ~3,000 words.
- Output Markdown only.
"""

PROFILE_TEMPLATE_OUTLINE = """# Client Profile — Relevance Screening Reference

## 1. The business
(Describe services, geography, positioning.)

## 2. Target audience
(Who content is for — and who it is not for.)

## 3. Technical and regulatory scope
(Frameworks, stack, vendors in play.)

## 4. Credentials and differentiators
(Proof points.)

## 5. Positioning
- …

## 6. Relevance test
1. …
2. …

## 7. Weight up / Weight down or exclude
**Weight up**
- …

**Weight down or exclude**
- …

## 8. Voice and LinkedIn rules
…
"""


def read_file_fallback_profile() -> str:
    if _DEFAULT_PROFILE_PATH.exists():
        return _DEFAULT_PROFILE_PATH.read_text(encoding="utf-8")
    logger.warning("Client profile file not found at %s", _DEFAULT_PROFILE_PATH)
    return "No client profile configured."


async def load_client_profile(session: AsyncSession, org_id: uuid.UUID) -> str:
    """Prefer DB Markdown on the org brand kit; else shared file; else placeholder."""
    row = (
        await session.execute(
            select(BrandKit.client_profile_md).where(BrandKit.organization_id == org_id).limit(1)
        )
    ).scalar_one_or_none()
    if isinstance(row, str) and row.strip():
        return row
    return read_file_fallback_profile()


_LEARNED_HEADING = "## Learned from admin feedback"


async def append_admin_feedback_to_profile(
    session: AsyncSession,
    org_id: uuid.UUID,
    *,
    relevant: bool,
    title: str,
    category: str | None = None,
    note: str | None = None,
) -> bool:
    """Append a durable like/dislike signal into the org brand profile Markdown.

    Returns True if the brand kit was updated.
    """
    kit = (
        await session.execute(select(BrandKit).where(BrandKit.organization_id == org_id).limit(1))
    ).scalar_one_or_none()
    if kit is None:
        return False

    base = (kit.client_profile_md or "").strip() or read_file_fallback_profile()
    if base == "No client profile configured.":
        base = PROFILE_TEMPLATE_OUTLINE.strip()

    short_title = (title or "Untitled").strip()[:160]
    topic = (category or "general").strip()
    note_bit = f" Note: {note.strip()}" if note and note.strip() else ""
    if relevant:
        bullet = (
            f"- Prefer stories like “{short_title}” (topic: {topic}) — marked relevant by admin."
            f"{note_bit}"
        )
    else:
        bullet = (
            f"- Exclude / down-rank stories like “{short_title}” (topic: {topic}) — marked not relevant by admin."
            f"{note_bit}"
        )

    if _LEARNED_HEADING in base:
        parts = base.split(_LEARNED_HEADING, 1)
        rest = parts[1].lstrip("\n")
        existing_bullets = [
            ln for ln in rest.splitlines() if ln.lstrip().startswith("- ")
        ]
        merged = [bullet, *existing_bullets][:40]
        kit.client_profile_md = (
            f"{parts[0].rstrip()}\n\n{_LEARNED_HEADING}\n" + "\n".join(merged) + "\n"
        )
    else:
        kit.client_profile_md = f"{base.rstrip()}\n\n{_LEARNED_HEADING}\n{bullet}\n"

    await session.flush()
    logger.info(
        "brand_profile.learned org=%s relevant=%s title=%s",
        org_id,
        relevant,
        short_title[:80],
    )
    return True
