"""Post-ingest helpers for the command-driven relevance queue."""

from __future__ import annotations

import uuid

from app.core.logging import get_logger

logger = get_logger(__name__)


async def notify_articles_imported(
    *,
    org_id: uuid.UUID,
    source_id: uuid.UUID,
    article_ids: list[str],
) -> None:
    """Leave imported articles durably queued until the user starts a batch.

    Ingest already persists each new article with status ``scored``.  That is
    now the queue state: pulling news never spends LLM calls or starts a batch
    implicitly.  ``source_id`` remains in the signature for existing callers
    and useful logging context.
    """
    logger.info(
        "Queued %d imported articles for command-driven relevance screening "
        "org=%s source=%s",
        len(article_ids),
        org_id,
        source_id,
    )
