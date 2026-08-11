"""Capability Router and provider configuration ports."""

from __future__ import annotations

import uuid
from typing import Protocol

from app.modules.providers.domain.models import RoutingDecision
from app.shared.ai_types import AIProvider


class ProviderConfigRepository(Protocol):
    """Port for provider configuration persistence."""

    async def list_by_org(self, org_id: uuid.UUID) -> list[dict]: ...

    async def get_for_capability(self, org_id: uuid.UUID, capability: str) -> dict | None: ...

    async def upsert(self, org_id: uuid.UUID, config: dict) -> uuid.UUID: ...


class CapabilityRouter(Protocol):
    """Selection only — never executes LLM calls."""

    async def resolve(
        self,
        capability: str,
        *,
        organization_id: uuid.UUID | None = None,
    ) -> RoutingDecision: ...


class ProviderFactory(Protocol):
    def create(self, provider_name: str, *, model: str = "") -> AIProvider: ...

    def known_providers(self) -> set[str]: ...
