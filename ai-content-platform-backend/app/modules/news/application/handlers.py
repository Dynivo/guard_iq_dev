"""Workflow handlers for News Intelligence (M8)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.modules.news.application.factory import NewsPipelineFactory
from app.modules.news.domain.models import NormalizedArticle, SourceDefinition
from app.modules.workflow.domain.models import NodeOutcome, WorkflowContext, WorkflowNode


def _source_from_context(context: WorkflowContext, node: WorkflowNode) -> SourceDefinition:
    cfg = node.config or {}
    raw = context.get("news.source") or {}
    if not isinstance(raw, dict):
        raw = {}
    return SourceDefinition(
        source_id=str(
            cfg.get("source_id")
            or raw.get("source_id")
            or context.get("source_id")
            or "workflow"
        ),
        name=str(cfg.get("name") or raw.get("name") or "workflow-source"),
        connector_type=str(
            cfg.get("connector_type") or raw.get("connector_type") or "rss"
        ),
        config=dict(cfg.get("config") or raw.get("config") or {}),
        schedule_cron=str(cfg.get("schedule_cron") or ""),
        enabled=True,
        organization_id=str(context.organization_id or context.get("organization_id") or ""),
        authority=float(cfg.get("authority") or raw.get("authority") or 0.5),
        reliability=float(cfg.get("reliability") or raw.get("reliability") or 0.5),
        trust=float(cfg.get("trust") or raw.get("trust") or 0.5),
    )


def _items_from_context(context: WorkflowContext) -> list[NormalizedArticle] | None:
    raw = context.get("news.raw_items")
    if not isinstance(raw, list):
        return None
    items: list[NormalizedArticle] = []
    for item in raw:
        if isinstance(item, NormalizedArticle):
            items.append(item)
            continue
        if not isinstance(item, dict):
            continue
        published = item.get("published_at")
        if isinstance(published, str):
            try:
                published = datetime.fromisoformat(published.replace("Z", "+00:00"))
            except ValueError:
                published = None
        items.append(
            NormalizedArticle(
                title=str(item.get("title") or ""),
                url=str(item.get("url") or ""),
                summary=item.get("summary"),
                body_text=item.get("body_text"),
                published_at=published if isinstance(published, datetime) else None,
                author=item.get("author"),
                raw_payload=dict(item.get("raw_payload") or item),
            )
        )
    return items


def _org(context: WorkflowContext) -> uuid.UUID | None:
    raw = context.organization_id or context.get("organization_id")
    if isinstance(raw, uuid.UUID):
        return raw
    if isinstance(raw, str) and raw:
        try:
            return uuid.UUID(raw)
        except ValueError:
            return None
    return None


class _PipelineHolder:
    pipeline = None

    @classmethod
    def get(cls):
        if cls.pipeline is None:
            cls.pipeline = NewsPipelineFactory.create_memory()
        return cls.pipeline


class NewsFetchHandler:
    def __init__(self, pipeline=None) -> None:
        self._pipeline = pipeline

    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        source = _source_from_context(context, node)
        existing = context.get("news.raw_items")
        if isinstance(existing, list) and existing:
            payload = {
                "news.source": {
                    "source_id": source.source_id,
                    "name": source.name,
                    "connector_type": source.connector_type,
                    "config": source.config,
                    "authority": source.authority,
                    "reliability": source.reliability,
                    "trust": source.trust,
                },
                "news.raw_items": existing,
                "news.fetched": len(existing),
            }
            context.update(payload)
            return NodeOutcome(success=True, outputs=payload)

        from app.modules.news.infrastructure.connector_factory import DefaultConnectorRegistry

        registry = DefaultConnectorRegistry()
        try:
            connector = registry.get(source.connector_type)
            items = await connector.fetch(source.config)
        except Exception as exc:  # noqa: BLE001
            payload = {"news.fetch_error": str(exc), "news.raw_items": []}
            context.update(payload)
            return NodeOutcome(success=False, outputs=payload, error_message=str(exc))

        serialized = [
            {
                "title": i.title,
                "url": i.url,
                "summary": i.summary,
                "body_text": i.body_text,
                "published_at": i.published_at.isoformat() if i.published_at else None,
                "author": i.author,
                "raw_payload": i.raw_payload,
            }
            for i in items
        ]
        payload = {
            "news.source": {
                "source_id": source.source_id,
                "name": source.name,
                "connector_type": source.connector_type,
                "config": source.config,
                "authority": source.authority,
                "reliability": source.reliability,
                "trust": source.trust,
            },
            "news.raw_items": serialized,
            "news.fetched": len(serialized),
        }
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class NewsParseHandler:
    """Parse is folded into connector fetch for RSS/NewsData; pass-through."""

    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        items = context.get("news.raw_items") or []
        payload = {"news.parsed": len(items) if isinstance(items, list) else 0}
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class NewsNormalizeHandler:
    def __init__(self, pipeline=None) -> None:
        self._pipeline = pipeline

    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        pipe = self._pipeline or _PipelineHolder.get()
        source = _source_from_context(context, node)
        items = _items_from_context(context) or []
        arts = [
            pipe._normalizer.normalize(i, source=source, organization_id=_org(context))
            for i in items
        ]
        payload = {
            "news.normalized_articles": [a.to_dict() for a in arts],
            "news.normalized": len(arts),
        }
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class NewsDedupeHandler:
    def __init__(self, pipeline=None) -> None:
        self._pipeline = pipeline

    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        pipe = self._pipeline or _PipelineHolder.get()
        source = _source_from_context(context, node)
        items = _items_from_context(context)
        result = await pipe.run(
            source, organization_id=_org(context), items=items or []
        )
        # Store full pipeline result for subsequent nodes when running partial graphs
        payload = {
            "news.pipeline_result": result.to_dict(),
            "news.duplicates": result.duplicates,
            "news.articles": [a.to_dict() for a in result.articles],
            "news.normalized": result.normalized,
        }
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class NewsClusterHandler:
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        result = context.get("news.pipeline_result")
        if isinstance(result, dict):
            payload = {
                "news.clusters": result.get("clusters") or [],
                "news.clustered": result.get("clustered") or 0,
            }
            context.update(payload)
            return NodeOutcome(success=True, outputs=payload)
        payload = {"news.clusters": [], "news.clustered": 0}
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class NewsScoreHandler:
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        result = context.get("news.pipeline_result")
        if isinstance(result, dict):
            payload = {
                "news.scores": result.get("scores") or [],
                "news.scored": result.get("scored") or 0,
            }
            context.update(payload)
            return NodeOutcome(success=True, outputs=payload)
        payload = {"news.scores": [], "news.scored": 0}
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class NewsEnrichHandler:
    """Expose post-score enrichment (entities/events/opportunities/trends/timelines)."""

    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        result = context.get("news.pipeline_result")
        metrics = result.get("metrics") if isinstance(result, dict) else {}
        if not isinstance(metrics, dict):
            metrics = {}
        arts = context.get("news.articles") or (
            result.get("articles") if isinstance(result, dict) else []
        )
        payload = {
            "news.enriched": True,
            "news.opportunities": metrics.get("opportunities") or [],
            "news.trends": metrics.get("trends") or [],
            "news.story_timelines": metrics.get("story_timelines") or [],
            "news.entities_stored": metrics.get("entities_stored") or 0,
            "news.articles": arts,
        }
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class NewsStoreHandler:
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        arts = context.get("news.articles") or []
        n = len(arts) if isinstance(arts, list) else 0
        enriched = bool(context.get("news.enriched"))
        result = context.get("news.pipeline_result")
        if not enriched and isinstance(result, dict):
            metrics = result.get("metrics") or {}
            if isinstance(metrics, dict):
                enriched = bool(metrics.get("ready_for_knowledge"))
        payload = {
            "news.stored": n,
            "news.store_status": "memory",
            "news.ready_for_knowledge": enriched,
        }
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


def register_news_handlers(node_registry, pipeline=None) -> None:
    pipe = pipeline or NewsPipelineFactory.create_memory()
    node_registry.register("news.fetch", NewsFetchHandler(pipe))
    node_registry.register("news.parse", NewsParseHandler())
    node_registry.register("news.normalize", NewsNormalizeHandler(pipe))
    node_registry.register("news.dedupe", NewsDedupeHandler(pipe))
    node_registry.register("news.cluster", NewsClusterHandler())
    node_registry.register("news.score", NewsScoreHandler())
    node_registry.register("news.enrich", NewsEnrichHandler())
    node_registry.register("news.store", NewsStoreHandler())
