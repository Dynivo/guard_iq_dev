"""Workflow node handlers for knowledge.* types — no business logic in the engine."""

from __future__ import annotations

import uuid
from typing import Any

from app.modules.knowledge.application.factory import KnowledgeEngineFactory
from app.modules.knowledge.domain.models import (
    FilteredKnowledge,
    KnowledgeItem,
    KnowledgeQuery,
    KnowledgeType,
    RankedKnowledge,
    SearchMode,
)
from app.modules.workflow.domain.models import NodeOutcome, WorkflowContext, WorkflowNode


def _parse_query(context: WorkflowContext, node: WorkflowNode) -> KnowledgeQuery:
    cfg = node.config or {}
    org_raw = context.organization_id or context.get("organization_id")
    if isinstance(org_raw, str):
        org_id = uuid.UUID(org_raw)
    elif isinstance(org_raw, uuid.UUID):
        org_id = org_raw
    else:
        org_id = uuid.UUID(int=0)
    types_raw = cfg.get("types") or context.get("knowledge_types") or []
    types = tuple(KnowledgeType(t) for t in types_raw) if types_raw else ()
    mode = SearchMode(str(cfg.get("search_mode") or context.get("search_mode") or "hybrid"))
    return KnowledgeQuery(
        organization_id=org_id,
        query_text=str(
            cfg.get("query")
            or context.get("query_text")
            or context.get("article_title")
            or ""
        ),
        correlation_id=context.correlation_id,
        types=types,
        search_mode=mode,
        top_k=int(cfg.get("top_k") or context.get("top_k") or 20),
        token_budget=int(cfg.get("token_budget") or context.get("token_budget") or 4000),
        policy_id=str(cfg.get("policy_id") or context.get("policy_id") or "default"),
    )


def _serialize_items(items: tuple[KnowledgeItem, ...]) -> list[dict[str, Any]]:
    return [
        {
            "id": i.id,
            "type": i.type.value,
            "title": i.title,
            "content": i.content,
            "rank_score": i.rank_score,
            "similarity": i.similarity,
            "reliability": i.reliability,
            "confidence": i.confidence,
            "freshness": i.freshness,
            "authority": i.authority,
            "organization_relevance": i.organization_relevance,
            "source_name": i.source_name,
            "metadata": i.metadata,
            "organization_id": str(i.organization_id) if i.organization_id else None,
            "created_at": i.created_at.isoformat() if i.created_at else None,
        }
        for i in items
    ]


def _items_from_raw(raw: list, query: KnowledgeQuery) -> tuple[KnowledgeItem, ...]:
    out: list[KnowledgeItem] = []
    for r in raw:
        org = query.organization_id
        if r.get("organization_id"):
            try:
                org = uuid.UUID(str(r["organization_id"]))
            except ValueError:
                org = query.organization_id
        created = None
        if r.get("created_at"):
            from datetime import datetime

            try:
                created = datetime.fromisoformat(str(r["created_at"]))
            except ValueError:
                created = None
        out.append(
            KnowledgeItem(
                id=str(r["id"]),
                type=KnowledgeType(r.get("type", "document")),
                organization_id=org,
                title=str(r.get("title") or ""),
                content=str(r.get("content") or ""),
                metadata=dict(r.get("metadata") or {}),
                similarity=r.get("similarity"),
                rank_score=r.get("rank_score"),
                reliability=float(r.get("reliability", 0.5)),
                confidence=float(r.get("confidence", 0.5)),
                freshness=float(r.get("freshness", 0.5)),
                authority=float(r.get("authority", 0.5)),
                organization_relevance=float(r.get("organization_relevance", 0.5)),
                source_name=str(r.get("source_name") or ""),
                created_at=created,
            )
        )
    return tuple(out)


class KnowledgePlanHandler:
    def __init__(self, engine=None) -> None:
        self._engine = engine or KnowledgeEngineFactory.create_memory()

    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        query = _parse_query(context, node)
        planned = await self._engine.plan(query)
        payload = {
            "knowledge.planned_query": {
                "search_type": planned.search_type.value,
                "search_depth": planned.search_depth,
                "filters": planned.filters,
                "collections": list(planned.collections),
                "policy_id": planned.policy_id,
            },
        }
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class KnowledgeRetrieveHandler:
    def __init__(self, engine=None) -> None:
        self._engine = engine or KnowledgeEngineFactory.create_memory()

    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        query = _parse_query(context, node)
        planned = None
        raw_plan = context.get("knowledge.planned_query")
        if isinstance(raw_plan, dict):
            from app.modules.knowledge.domain.models import PlannedQuery

            planned = PlannedQuery(
                search_type=SearchMode(str(raw_plan.get("search_type") or query.search_mode.value)),
                search_depth=int(raw_plan.get("search_depth") or query.top_k),
                filters=dict(raw_plan.get("filters") or {}),
                collections=tuple(raw_plan.get("collections") or ("knowledge",)),
                policy_id=str(raw_plan.get("policy_id") or "default"),
                query=query,
            )
        result = await self._engine.retrieve(query, planned=planned)
        payload = {
            "knowledge.candidates": _serialize_items(result.items),
            "knowledge.retrieval_ms": result.duration_ms,
        }
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class KnowledgeRankHandler:
    def __init__(self, engine=None) -> None:
        self._engine = engine or KnowledgeEngineFactory.create_memory()

    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        query = _parse_query(context, node)
        raw = context.get("knowledge.candidates") or []
        items = _items_from_raw(raw, query)
        ranked = await self._engine.rank(items, query)
        payload = {
            "knowledge.ranked": _serialize_items(ranked.items),
            "knowledge.ranking_ms": ranked.duration_ms,
        }
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class KnowledgeFilterHandler:
    def __init__(self, engine=None) -> None:
        self._engine = engine or KnowledgeEngineFactory.create_memory()

    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        query = _parse_query(context, node)
        raw = context.get("knowledge.ranked") or context.get("knowledge.candidates") or []
        items = _items_from_raw(raw, query)
        filtered = await self._engine.filter(RankedKnowledge(items=items), query)
        payload = {
            "knowledge.filtered": _serialize_items(filtered.items),
            "knowledge.filter_dropped": filtered.dropped_count,
            "knowledge.filter_reasons": filtered.drop_reasons,
            "knowledge.filter_ms": filtered.duration_ms,
        }
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class KnowledgeCompressHandler:
    def __init__(self, engine=None) -> None:
        self._engine = engine or KnowledgeEngineFactory.create_memory()

    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        query = _parse_query(context, node)
        raw = (
            context.get("knowledge.filtered")
            or context.get("knowledge.ranked")
            or context.get("knowledge.candidates")
            or []
        )
        items = _items_from_raw(raw, query)
        compressed = await self._engine.compress(
            FilteredKnowledge(items=items),
            token_budget=query.token_budget,
        )
        payload = {
            "knowledge.compressed": _serialize_items(compressed.items),
            "knowledge.tokens_before": compressed.tokens_before,
            "knowledge.tokens_after": compressed.tokens_after,
            "knowledge.compression_ms": compressed.duration_ms,
        }
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class KnowledgeContextHandler:
    def __init__(self, engine=None) -> None:
        self._engine = engine or KnowledgeEngineFactory.create_memory()

    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        query = _parse_query(context, node)
        optimized = await self._engine.prepare_context(query)
        payload = {
            "knowledge.optimized_context": optimized.text,
            "knowledge.citations": list(optimized.citations),
            "knowledge.citation_map": [
                {
                    "citation_id": e.citation_id,
                    "knowledge_id": e.knowledge_id,
                    "type": e.type,
                    "title": e.title,
                    "source": e.source,
                }
                for e in optimized.citation_map.entries
            ],
            "knowledge.sources": list(optimized.knowledge_sources),
            "knowledge.token_estimate": optimized.token_estimate,
            "knowledge.metrics": optimized.metrics,
        }
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


def register_knowledge_handlers(node_registry, engine=None) -> None:
    eng = engine or KnowledgeEngineFactory.create_memory()
    node_registry.register("knowledge.plan", KnowledgePlanHandler(eng))
    node_registry.register("knowledge.retrieve", KnowledgeRetrieveHandler(eng))
    node_registry.register("knowledge.rank", KnowledgeRankHandler(eng))
    node_registry.register("knowledge.filter", KnowledgeFilterHandler(eng))
    node_registry.register("knowledge.compress", KnowledgeCompressHandler(eng))
    node_registry.register("knowledge.context", KnowledgeContextHandler(eng))
