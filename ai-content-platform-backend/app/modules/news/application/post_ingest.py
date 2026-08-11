"""Post-ingest helpers — publish ArticleImported + enqueue AI relevance after commit."""

from __future__ import annotations

import uuid

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
    """Publish ArticleImported for each saved article (call after DB commit)."""
    bus = get_event_bus()
    for aid in article_ids:
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
