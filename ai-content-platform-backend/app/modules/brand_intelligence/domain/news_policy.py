"""Brand-derived news / relevance / planning policy (replaceable port)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class BrandNewsPolicy:
    """Canonical org news policy projected from Brand Memory + Brand Kit."""

    organization_id: uuid.UUID
    brand_profile_id: uuid.UUID | None
    topics: list[str] = field(default_factory=list)
    industries: list[str] = field(default_factory=list)
    audience: str = ""
    strategic_goal: str = ""
    in_scope_terms: list[str] = field(default_factory=list)
    exclude_terms: list[str] = field(default_factory=list)
    primary_query: str = ""
    alternate_queries: list[str] = field(default_factory=list)
    weight_up: list[str] = field(default_factory=list)
    weight_down: list[str] = field(default_factory=list)
    source: str = "defaults"

    def to_dict(self) -> dict[str, Any]:
        return {
            "organization_id": str(self.organization_id),
            "brand_profile_id": str(self.brand_profile_id) if self.brand_profile_id else None,
            "topics": list(self.topics),
            "industries": list(self.industries),
            "audience": self.audience,
            "strategic_goal": self.strategic_goal,
            "in_scope_terms": list(self.in_scope_terms),
            "exclude_terms": list(self.exclude_terms),
            "primary_query": self.primary_query,
            "alternate_queries": list(self.alternate_queries),
            "weight_up": list(self.weight_up),
            "weight_down": list(self.weight_down),
            "source": self.source,
        }


class BrandNewsPolicyPort(Protocol):
    async def get_for_org(
        self, org_id: uuid.UUID, *, profile_id: uuid.UUID | None = None
    ) -> BrandNewsPolicy: ...

    async def sync_news_sources(
        self, org_id: uuid.UUID, *, profile_id: uuid.UUID | None = None
    ) -> dict[str, Any]: ...

    def relevance_profile_markdown(self, policy: BrandNewsPolicy) -> str: ...
