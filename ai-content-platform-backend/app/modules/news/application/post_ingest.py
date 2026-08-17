"""Post-ingest helpers — publish ArticleImported + enqueue AI relevance after commit."""

from __future__ import annotations

import uuid

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.observability import ensure_correlation_id
from app.infrastructure.events.factory import get_event_bus
from app.shared.events import article_imported

logger = get_logger(__name__)


async def notify_articles_imported(
    *,
    org_id: uuid.UUID,
    source_id: uuid.UUID,
    article_ids: list[str],
) -> None:
    """Publish ArticleImported for up to RELEVANCE_AUTOSCORE_BATCH_CAP of the
    saved articles (call after DB commit) — each publish triggers one LLM
    relevance-scoring call, so a large burst is capped rather than scoring
    everything at once. Articles beyond the cap stay at their post-ingest
    keyword-only status until/unless the relevance-recovery sweep picks them
    up (see RELEVANCE_RECOVERY_ENABLED)."""
    cap = get_settings().RELEVANCE_AUTOSCORE_BATCH_CAP
    to_score = article_ids[:cap] if cap > 0 else article_ids
    deferred = len(article_ids) - len(to_score)
    if deferred:
        logger.info(
            "Auto-relevance batch cap: scoring %d/%d imported articles now, %d deferred",
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
