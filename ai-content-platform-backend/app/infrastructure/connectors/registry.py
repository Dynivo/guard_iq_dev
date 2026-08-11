"""Connector registry — resolves connector_type strings to instances.

Connectors are registered at import time.  The registry is the only
place that knows about concrete connector implementations.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.infrastructure.connectors.base import BaseConnector
from app.infrastructure.connectors.currents import CurrentsConnector
from app.infrastructure.connectors.gnews import GNewsConnector
from app.infrastructure.connectors.guardian import GuardianConnector
from app.infrastructure.connectors.hackernews import HackerNewsConnector
from app.infrastructure.connectors.msrc import MSRCConnector
from app.infrastructure.connectors.ncsc import NCSCConnector
from app.infrastructure.connectors.newsdata import NewsDataConnector
from app.infrastructure.connectors.rss import RSSConnector

logger = get_logger(__name__)

_REGISTRY: dict[str, type[BaseConnector]] = {
    "rss": RSSConnector,
    "ncsc": NCSCConnector,
    "msrc": MSRCConnector,
    "news_api": NewsDataConnector,
    "gnews": GNewsConnector,
    "guardian": GuardianConnector,
    "currents": CurrentsConnector,
    "hackernews": HackerNewsConnector,
}


def get_connector(connector_type: str) -> BaseConnector:
    """Return an instance of the connector matching the given type string.

    Raises ValueError if the connector_type is unknown.
    """
    cls = _REGISTRY.get(connector_type)
    if cls is None:
        available = ", ".join(sorted(_REGISTRY.keys()))
        raise ValueError(
            f"Unknown connector type '{connector_type}'. Available: {available}"
        )
    return cls()


def list_connector_types() -> list[str]:
    """Return all registered connector type names."""
    return sorted(_REGISTRY.keys())
