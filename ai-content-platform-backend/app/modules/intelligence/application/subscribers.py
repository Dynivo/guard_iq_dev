"""Intelligence event subscribers — auto-relevance after article ingest."""

from __future__ import annotations

import asyncio
import uuid

from app.core.logging import get_logger
from app.shared.events.ports import EventBus
from app.shared.events.types import DomainEvent

logger = get_logger(__name__)

# Caps concurrent inline relevance-scoring calls (shared with the orphan-recovery
# sweep in orphan_recovery.py) so a burst of ingested articles — or a sweep
# catching up a backlog — can't hold more DB connections than the pool allows.
# Same fix already applied to inline image ingest earlier this session.
relevance_semaphore = asyncio.Semaphore(5)


def register_intelligence_handlers(bus: EventBus, session_factory=None) -> None:
    """Subscribe ArticleImported → enqueue AI relevance (non-blocking)."""

    async def _handle(event: DomainEvent) -> None:
        article_id_raw = (event.payload or {}).get("article_id")
        if not article_id_raw:
            return
        try:
            article_id = uuid.UUID(str(article_id_raw))
        except ValueError:
            logger.warning("intelligence.invalid_article_id payload=%s", article_id_raw)
            return

        org_id = event.organization_id
        # Never block ingest on LLM scoring — enqueue a background task.
        asyncio.create_task(
            _score_in_background(org_id, article_id, session_factory),
            name=f"relevance-{article_id}",
        )

    bus.subscribe("ArticleImported", _handle)
    logger.info("Registered intelligence handlers for ArticleImported")


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
