"""Local filesystem StorageProvider for development and tests."""

from __future__ import annotations

import hashlib
from pathlib import Path

from app.core.exceptions import NotFoundError
from app.modules.assets.domain.ports import StoredObject


class LocalStorageProvider:
    """Store objects under a configurable root directory (default: data/media)."""

    provider_name = "local"

    def __init__(self, root: str | Path = "data/media") -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def put_bytes(
        self,
        storage_key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> StoredObject:
        path = self._resolve(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return StoredObject(
            storage_key=storage_key,
            content_type=content_type,
            size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
        )

    def get_bytes(self, storage_key: str) -> bytes:
        path = self._resolve(storage_key)
        if not path.is_file():
            raise NotFoundError("Media", storage_key)
        return path.read_bytes()

    def exists(self, storage_key: str) -> bool:
        return self._resolve(storage_key).is_file()

    def delete(self, storage_key: str) -> None:
        path = self._resolve(storage_key)
        if path.is_file():
            path.unlink()

    def _resolve(self, storage_key: str) -> Path:
        if ".." in storage_key.split("/"):
            raise ValueError("Invalid storage key")
        return self._root / storage_key
