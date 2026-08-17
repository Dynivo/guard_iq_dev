"""Post-ingest helpers — publish ArticleImported + enqueue AI relevance after commit."""

from __future__ import annotations

import uuid

from app.core.logging import get_logger
from app.core.observability import ensure_correlation_id
from app.infrastructure.events.factory import get_event_bus
from app.modules.intelligence.application.autoscore_budget import autoscore_budget
from app.shared.events import article_imported

logger = get_logger(__name__)


async def notify_articles_imported(
    *,
    org_id: uuid.UUID,
    source_id: uuid.UUID,
    article_ids: list[str],
) -> None:
    """Publish ArticleImported for as many of the saved articles as the
    process-wide auto-score budget allows (call after DB commit) — each
    publish triggers one LLM relevance-scoring call, so a large burst is
    capped rather than scoring everything at once. The budget is shared
    across every source's ingest run (see autoscore_budget), not reset per
    call, so a burst spread across many sources still shares one cap.
    Articles beyond the budget stay at their post-ingest keyword-only status
    until/unless the relevance-recovery sweep picks them up (see
    RELEVANCE_RECOVERY_ENABLED)."""
    granted = autoscore_budget.reserve(len(article_ids))
    to_score = article_ids[:granted]
    deferred = len(article_ids) - len(to_score)
    if deferred:
        logger.info(
            "Auto-relevance budget: scoring %d/%d imported articles now, %d deferred",
            len(to_score),
            len(article_ids),
            deferred,
        )
    bus = get_event_bus()
    for aid in to_score:
        try:
            await bus.publish(
                article_imported(
                    organization_id=org_id,
                    article_id=uuid.UUID(aid),
                    source_id=source_id,
                    correlation_id=ensure_correlation_id(),
                )
            )
        except Exception:
            logger.exception("Failed to publish ArticleImported for %s", aid)
