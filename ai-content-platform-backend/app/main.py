"""FastAPI application entry point.

Wires middleware, routers, and lifecycle events. All business logic
lives in modules — this file only performs composition.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.api.middleware.error_handler import ErrorHandlerMiddleware
from app.api.middleware.request_id import RequestIdMiddleware
from app.api.routes import (
    analytics,
    articles,
    auth,
    brand_intelligence,
    brand_kits,
    capture,
    carousels,
    consensus,
    diagnostics,
    drafts,
    health,
    images,
    intelligence,
    jobs,
    learning,
    media,
    organizations,
    opportunities,
    prompts,
    publishing_plan,
    review,
    sources,
    typography,
)
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.infrastructure.events.factory import get_event_bus
from app.modules.analytics.application.subscribers import register_analytics_handlers
from app.modules.consensus.application.subscribers import register_consensus_handlers
from app.modules.intelligence.application.subscribers import register_intelligence_handlers
from app.modules.learning.application.subscribers import register_learning_handlers

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifecycle."""
    get_settings.cache_clear()
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL, log_dir=settings.LOG_DIR)
    try:
        from app.modules.consensus.application.config_loader import load_consensus_config

        load_consensus_config.cache_clear()
    except Exception:  # noqa: BLE001
        pass
    bus = get_event_bus()
    register_learning_handlers(bus)
    register_analytics_handlers(bus)
    register_consensus_handlers(bus)
    from app.infrastructure.postgres.session import async_session_factory

    register_intelligence_handlers(bus, session_factory=async_session_factory)

    keyed: list[str] = []
    try:
        from app.modules.providers.infrastructure.provider_factory import DefaultProviderFactory

        factory = DefaultProviderFactory()
        keyed = [
            name
            for name in ("openai", "gemini", "grok", "azure_openai", "perplexity", "anthropic")
            if factory.has_credentials(name)
        ]
    except Exception:  # noqa: BLE001
        keyed = []

    logger.info(
        "Starting AI Content Platform Backend — env=%s debug=%s consensus=%s policy=%s keyed=%s",
        settings.APP_ENV,
        settings.APP_DEBUG,
        settings.CONSENSUS_ENABLED,
        settings.CONSENSUS_POLICY,
        keyed,
        extra={
            "app_module": "main",
            "operation": "startup",
            "outcome": "success",
        },
    )
    try:
        import asyncio

        from app.modules.image.application.orphan_recovery import (
            recover_orphaned_image_batches_startup,
        )

        asyncio.create_task(recover_orphaned_image_batches_startup(async_session_factory))
    except Exception:  # noqa: BLE001
        logger.exception("Failed to schedule image orphan recovery")

    try:
        import asyncio

        from app.modules.intelligence.application.screening_batches import (
            resume_screening_batches_startup,
        )

        asyncio.create_task(resume_screening_batches_startup(async_session_factory))
    except Exception:  # noqa: BLE001
        logger.exception("Failed to resume relevance screening batches")

    try:
        import asyncio

        from app.modules.news.application.source_cron import source_cron_loop

        asyncio.create_task(source_cron_loop(async_session_factory))
    except Exception:  # noqa: BLE001
        logger.exception("Failed to schedule source cron loop")

    try:
        import asyncio

        from app.modules.news.application.article_retention import article_retention_loop

        asyncio.create_task(article_retention_loop(async_session_factory))
    except Exception:  # noqa: BLE001
        logger.exception("Failed to schedule article retention loop")
    yield
    logger.info(
        "Shutting down AI Content Platform Backend",
        extra={"app_module": "main", "operation": "shutdown", "outcome": "success"},
    )


def create_app() -> FastAPI:
    """Build and return the FastAPI application instance."""
    settings = get_settings()

    app = FastAPI(
        title="AI Content Intelligence Platform",
        version="0.1.0",
        description="Enterprise LinkedIn content automation backend",
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )

    app.add_middleware(ErrorHandlerMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api_prefix = "/api/v1"
    app.include_router(health.router, prefix=api_prefix)
    app.include_router(auth.router, prefix=api_prefix)
    app.include_router(organizations.router, prefix=api_prefix)
    app.include_router(brand_kits.router, prefix=api_prefix)
    app.include_router(brand_kits.alias_router, prefix=api_prefix)
    app.include_router(brand_intelligence.router, prefix=api_prefix)
    # Register static intelligence endpoints before the generic
    # ``/articles/{article_id}`` route. Otherwise FastAPI treats paths such as
    # ``/articles/screening-status`` as an article UUID and returns 422 before
    # the intended handler can run.
    app.include_router(intelligence.router, prefix=api_prefix)
    app.include_router(articles.router, prefix=api_prefix)
    app.include_router(sources.router, prefix=api_prefix)
    app.include_router(drafts.router, prefix=api_prefix)
    app.include_router(capture.router, prefix=api_prefix)
    app.include_router(publishing_plan.router, prefix=api_prefix)
    app.include_router(opportunities.router, prefix=api_prefix)
    app.include_router(images.router, prefix=api_prefix)
    app.include_router(typography.router, prefix=api_prefix)
    app.include_router(carousels.router, prefix=api_prefix)
    app.include_router(review.router, prefix=api_prefix)
    app.include_router(learning.router, prefix=api_prefix)
    app.include_router(prompts.router, prefix=api_prefix)
    app.include_router(analytics.router, prefix=api_prefix)
    app.include_router(consensus.router, prefix=api_prefix)
    app.include_router(jobs.router, prefix=api_prefix)
    app.include_router(diagnostics.router, prefix=api_prefix)
    app.include_router(media.router, prefix=api_prefix)

    return app


app = create_app()
