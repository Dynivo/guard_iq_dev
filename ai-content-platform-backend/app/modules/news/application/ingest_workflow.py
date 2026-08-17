"""IngestWorkflow — DB-backed facade over News Intelligence Pipeline (M8)."""

from __future__ import annotations

import uuid

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.infrastructure.connectors.registry import get_connector
from app.modules.news.application.factory import NewsPipelineFactory
from app.modules.news.domain.models import SourceDefinition
from app.modules.news.infrastructure.enrichment_store import PgEnrichmentWriter
from app.modules.news.infrastructure.repositories import (
    PgArticleRepository,
    PgDeduplicator,
    PgNewsSourceRepository,
)
from app.shared.url_utils import normalize_url

logger = get_logger(__name__)


class IngestWorkflow:
    """Orchestrates ingest for a single news source via the M8 pipeline."""

    def __init__(
        self,
        source_repo: PgNewsSourceRepository,
        article_repo: PgArticleRepository,
        deduplicator: PgDeduplicator,
        enrichment_writer: PgEnrichmentWriter | None = None,
    ) -> None:
        self._source_repo = source_repo
        self._article_repo = article_repo
        self._dedup = deduplicator
        self._enrichment = enrichment_writer

    async def execute(self, org_id: uuid.UUID, source_id: uuid.UUID) -> dict:
        source = await self._source_repo.get_by_id(source_id, org_id)
        if source is None:
            raise NotFoundError("NewsSource", str(source_id))

        if not source.enabled:
            logger.info("Source %s is disabled, skipping ingest", source.name)
            return {
                "source_id": str(source_id),
                "fetched": 0,
                "saved": 0,
                "duplicates": 0,
                "article_ids": [],
            }

        connector = get_connector(source.connector_type)
        articles = await connector.fetch(source.config_json or {})

        definition = SourceDefinition(
            source_id=str(source.id),
            name=source.name,
            connector_type=source.connector_type,
            config=dict(source.config_json or {}),
            schedule_cron=source.schedule_cron or "",
            enabled=source.enabled,
            organization_id=str(org_id),
        )
        brand_terms: list[str] = []
        exclude_terms: list[str] = []
        try:
            from app.modules.brand_intelligence.application.news_policy_service import (
                BrandNewsPolicyService,
            )

            session = getattr(self._article_repo, "_session", None)
            if session is not None:
                policy = await BrandNewsPolicyService(session).get_for_org(org_id)
                brand_terms = list(policy.in_scope_terms)
                exclude_terms = list(policy.exclude_terms)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Brand news policy unavailable for ingest: %s", exc)

        pipeline = NewsPipelineFactory.create_memory(
            brand_terms=brand_terms,
            exclude_terms=exclude_terms,
        )
        result = await pipeline.run(
            definition, organization_id=org_id, items=articles
        )

        saved = 0
        saved_ids: list[str] = []
        score_by_url = {
            (art.canonical_url or art.url): score.to_dict()
            for art, score in zip(result.articles, result.scores, strict=False)
        }

        writer = self._enrichment
        if writer is None and hasattr(self._article_repo, "_session"):
            writer = PgEnrichmentWriter(self._article_repo._session)

        from app.core.config import get_settings

        save_cap = get_settings().MAX_ARTICLES_PER_SOURCE_RUN

        for art in result.articles:
            if save_cap > 0 and saved >= save_cap:
                break
            canonical = art.canonical_url or normalize_url(art.url)
            if await self._article_repo.exists_by_url(org_id, canonical):
                continue
            if await self._dedup.is_duplicate(org_id, canonical, art.content_hash):
                continue
            from app.modules.news.domain.models import NormalizedArticle

            meta = dict(art.metadata or {})
            score_payload = (
                score_by_url.get(canonical)
                or score_by_url.get(art.url)
                or score_by_url.get(art.canonical_url or "")
                or {}
            )
            if isinstance(score_payload, dict) and meta.get("sentiment"):
                score_payload = {**score_payload, "sentiment": meta["sentiment"]}

            legacy = NormalizedArticle(
                title=art.title,
                url=canonical,
                summary=art.summary or None,
                body_text=art.body_text or None,
                published_at=art.published_at,
                author=art.author or None,
                raw_payload={
                    **art.raw_payload,
                    "canonical_url": art.canonical_url,
                    "language": art.language,
                    "category": art.category,
                    "tags": list(art.tags),
                    "content_hash": art.content_hash,
                    "topic_ready": True,
                    "topic_json": meta.get("taxonomy") or meta.get("topic"),
                    "score_json": score_payload,
                    "metadata": meta,
                },
            )
            article_id = await self._article_repo.save(legacy, org_id, source.id)
            # Mark as scored (keyword) until AI relevance runs
            await self._article_repo.update_status(article_id, org_id, "scored")
            await self._dedup.mark_seen(org_id, canonical)
            saved += 1
            saved_ids.append(str(article_id))

            if writer is not None:
                try:
                    await writer.persist_article_enrichment(
                        org_id=org_id,
                        article_id=article_id,
                        article_url=canonical,
                        metadata=meta,
                    )
                except Exception:
                    logger.exception(
                        "Failed to persist enrichment for article %s", article_id
                    )

        # Durable org-level trends + timelines for this run
        if writer is not None:
            metrics = result.metrics or {}
            try:
                trends = metrics.get("trends") or []
                if trends:
                    await writer.persist_trends(
                        org_id=org_id,
                        trends=list(trends),
                        window_label=f"source:{source.name}",
                    )
                timelines = metrics.get("story_timelines") or []
                if timelines:
                    await writer.persist_timelines(
                        org_id=org_id, timelines=list(timelines)
                    )
            except Exception:
                logger.exception("Failed to persist trends/timelines for org %s", org_id)

        await self._source_repo.update_last_fetched(source.id)

        logger.info(
            "Ingest complete: source=%s fetched=%d saved=%d duplicates=%d clusters=%d",
            source.name,
            result.fetched,
            saved,
            result.duplicates,
            result.clustered,
        )
        return {
            "source_id": str(source_id),
            "source_name": source.name,
            "fetched": result.fetched,
            "saved": saved,
            "duplicates": result.duplicates,
            "clustered": result.clustered,
            "scored": result.scored,
            "article_ids": saved_ids,
            "metrics": result.metrics,
        }
