"""Query Planner — plans retrieval before Retriever (no LLM)."""

from __future__ import annotations

from app.modules.knowledge.domain.models import (
    KnowledgePolicy,
    KnowledgeQuery,
    PlannedQuery,
    SearchMode,
)


class DefaultQueryPlanner:
    def __init__(self, policy: KnowledgePolicy | None = None) -> None:
        self._policy = policy or KnowledgePolicy()

    def plan(self, query: KnowledgeQuery) -> PlannedQuery:
        policy = self._policy
        filters: dict = {"organization_id": str(query.organization_id)}
        filters.update({k: v for k, v in query.metadata_filters.items()})
        if policy.allowed_types:
            filters["allowed_types"] = list(policy.allowed_types)
        if policy.allowed_languages:
            filters["allowed_languages"] = list(policy.allowed_languages)

        search_type = query.search_mode
        depth = max(1, query.top_k)
        # Deeper fetch for hybrid to allow filter/rank headroom
        if search_type == SearchMode.HYBRID:
            depth = max(depth, query.top_k)

        return PlannedQuery(
            search_type=search_type,
            search_depth=depth,
            filters=filters,
            collections=("knowledge",),
            policy_id=query.policy_id or policy.policy_id,
            query=query,
        )
