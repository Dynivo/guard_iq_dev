"""Connector registry/factory for news module (wraps infrastructure adapters)."""

from __future__ import annotations

from typing import Any, Callable

from app.infrastructure.connectors.registry import (
    get_connector as infra_get_connector,
)
from app.infrastructure.connectors.registry import list_connector_types


class DefaultConnectorRegistry:
    """Resolve connectors by type. New connectors register without changing callers."""

    def __init__(self) -> None:
        self._extra: dict[str, Callable[[], Any]] = {}

    def get(self, connector_type: str) -> Any:
        if connector_type in self._extra:
            return self._extra[connector_type]()
        return infra_get_connector(connector_type)

    def list_types(self) -> list[str]:
        types = set(list_connector_types())
        types.update(self._extra.keys())
        return sorted(types)

    def register(self, connector_type: str, factory: Callable[[], Any]) -> None:
        self._extra[connector_type] = factory


class ConnectorFactory:
    def __init__(self, registry: DefaultConnectorRegistry | None = None) -> None:
        self._registry = registry or DefaultConnectorRegistry()

    def create(self, connector_type: str) -> Any:
        return self._registry.get(connector_type)

    def supported(self) -> list[str]:
        return self._registry.list_types()
