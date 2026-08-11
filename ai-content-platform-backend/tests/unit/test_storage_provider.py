"""Unit tests for LocalStorageProvider and DeliveryStrategy."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.exceptions import NotFoundError
from app.infrastructure.storage.backend_stream import BackendStreamDeliveryStrategy
from app.infrastructure.storage.local import LocalStorageProvider


def test_local_storage_put_get_roundtrip(tmp_path: Path) -> None:
    storage = LocalStorageProvider(root=tmp_path)
    stored = storage.put_bytes("org/a/test.png", b"png-bytes", "image/png")
    assert stored.storage_key == "org/a/test.png"
    assert stored.size_bytes == 9
    assert len(stored.sha256) == 64
    assert storage.get_bytes("org/a/test.png") == b"png-bytes"
    assert storage.exists("org/a/test.png") is True


def test_local_storage_missing_raises(tmp_path: Path) -> None:
    storage = LocalStorageProvider(root=tmp_path)
    with pytest.raises(NotFoundError):
        storage.get_bytes("missing/key.bin")


def test_local_storage_rejects_path_traversal(tmp_path: Path) -> None:
    storage = LocalStorageProvider(root=tmp_path)
    with pytest.raises(ValueError):
        storage.put_bytes("../escape.png", b"x")


def test_backend_stream_delivery_url() -> None:
    strategy = BackendStreamDeliveryStrategy()
    desc = strategy.resolve("org-id/images/job.png", content_type="image/png")
    assert desc.strategy == "backend_stream"
    assert desc.url == "/api/v1/media/objects/org-id/images/job.png"
    assert desc.content_type == "image/png"
