"""In-memory node type → handler registry."""

from __future__ import annotations

from app.modules.workflow.domain.ports import NodeHandler


class InMemoryNodeRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, NodeHandler] = {}

    def register(self, type_name: str, handler: NodeHandler) -> None:
        self._handlers[type_name] = handler

    def get(self, type_name: str) -> NodeHandler:
        if type_name not in self._handlers:
            raise KeyError(f"No handler registered for node type '{type_name}'")
        return self._handlers[type_name]

    def known_types(self) -> set[str]:
        return set(self._handlers.keys())
