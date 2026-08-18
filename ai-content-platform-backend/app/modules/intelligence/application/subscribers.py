"""Intelligence event subscribers — auto-relevance after article ingest."""

from __future__ import annotations

import asyncio
import uuid

from app.core.logging import get_logger
from app.shared.events.ports import EventBus

logger = get_logger(__name__)

# Caps the legacy single-article event path. Command-driven batches use their
# own equivalent concurrency control in screening_batches.py.
relevance_semaphore = asyncio.Semaphore(5)


def register_intelligence_handlers(bus: EventBus, session_factory=None) -> None:
    """Keep imports queued until the user explicitly starts a batch.

    The former ``ArticleImported`` subscriber immediately invoked the LLM for
    every saved article, bypassing the durable command-driven queue. The
    single-article scoring helpers remain below for compatibility with direct
    callers, but ingest no longer subscribes them to the event bus.
    """
    logger.info("Automatic ArticleImported relevance screening is disabled")


async def _score_in_background(
    org_id: uuid.UUID,
    article_id: uuid.UUID,
    session_factory,
) -> None:
    async with relevance_semaphore:
        await _score_one(org_id, article_id, session_factory)


async def _score_one(
    org_id: uuid.UUID,
    article_id: uuid.UUID,
    session_factory,
) -> None:
    factory = session_factory
    if factory is None:
        from app.infrastructure.postgres.session import async_session_factory

        factory = async_session_factory

    try:
        async with factory() as session:
            from app.modules.ai.application.factory import AIOrchestratorFactory
            from app.modules.intelligence.application.workflow import IntelligenceWorkflow

            workflow = IntelligenceWorkflow(session, AIOrchestratorFactory.create())
            result = await workflow.run(org_id=org_id, article_id=article_id)
            await session.commit()
            logger.info(
                "intelligence.auto_relevance article=%s score=%s status=%s",
                article_id,
                result.get("score"),
                result.get("status"),
            )
    except Exception:
        logger.exception(
            "intelligence.auto_relevance_failed article=%s", article_id
        )
