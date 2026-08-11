"""Base connector class and shared helpers for all news connectors."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.modules.news.domain.models import CircuitState, SourceHealth
from app.modules.news.domain.ports import NormalizedArticle


class BaseConnector(ABC):
    """Abstract base for news connectors. Every concrete connector
    declares its `connector_type` and implements `fetch`."""

    connector_type: str = ""

    @abstractmethod
    async def fetch(self, config: dict) -> list[NormalizedArticle]:
        """Fetch articles from the source using the given config dict."""
        ...

    async def validate_config(self, config: dict) -> tuple[bool, str]:
        return True, ""

    async def health(self) -> SourceHealth:
        return SourceHealth(
            source_id=self.connector_type,
            healthy=True,
            circuit_state=CircuitState.CLOSED,
        )
