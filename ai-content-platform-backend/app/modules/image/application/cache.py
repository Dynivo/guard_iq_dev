"""In-memory caches for prompts, workflows, assets, thumbnails."""

from __future__ import annotations

from typing import Any

from app.modules.image.domain.models import ImagePromptRequest, WorkflowDescriptor


class InMemoryImagePromptCache:
    def __init__(self) -> None:
        self._store: dict[str, ImagePromptRequest] = {}

    def get(self, prompt_hash: str) -> ImagePromptRequest | None:
        return self._store.get(prompt_hash)

    def put(self, prompt_hash: str, request: ImagePromptRequest) -> None:
        self._store[prompt_hash] = request


class InMemoryWorkflowCache:
    def __init__(self) -> None:
        self._desc: dict[str, WorkflowDescriptor] = {}
        self._graphs: dict[str, dict[str, Any]] = {}

    def get_descriptor(self, key: str) -> WorkflowDescriptor | None:
        return self._desc.get(key)

    def put_descriptor(self, key: str, descriptor: WorkflowDescriptor) -> None:
        self._desc[key] = descriptor

    def get_graph(self, key: str) -> dict[str, Any] | None:
        return self._graphs.get(key)

    def put_graph(self, key: str, graph: dict[str, Any]) -> None:
        self._graphs[key] = graph


class InMemoryAssetCache:
    def __init__(self) -> None:
        self._bytes: dict[str, bytes] = {}

    def get(self, key: str) -> bytes | None:
        return self._bytes.get(key)

    def put(self, key: str, data: bytes) -> None:
        self._bytes[key] = data


class InMemoryThumbnailCache(InMemoryAssetCache):
    pass
