"""Image asset store persists through StorageProvider (local or S3)."""

from __future__ import annotations

import asyncio

import pytest

from app.infrastructure.storage.local import LocalStorageProvider
from app.modules.image.application.assets import (
    MemoryImageAssetStore,
    StorageWriteError,
    persist_png,
    storage_backend_name,
)
from app.modules.image.domain.models import OptimizedImageBundle


def _tiny_png() -> bytes:
    # Minimal valid 1x1 PNG
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def test_persist_png_local(tmp_path) -> None:
    storage = LocalStorageProvider(root=tmp_path)
    key = "org/images/job1/optimized.png"
    meta = persist_png(storage, key, _tiny_png())
    assert meta["storage_backend"] == "local"
    assert storage.exists(key)
    assert storage.get_bytes(key).startswith(b"\x89PNG")


def test_persist_png_rejects_empty(tmp_path) -> None:
    storage = LocalStorageProvider(root=tmp_path)
    with pytest.raises(StorageWriteError):
        persist_png(storage, "org/x.png", b"")


def test_asset_store_writes_all_roles(tmp_path) -> None:
    storage = LocalStorageProvider(root=tmp_path)
    store = MemoryImageAssetStore(storage=storage, require_storage=True)
    png = _tiny_png()
    bundle = OptimizedImageBundle(
        original_bytes=png,
        optimized_bytes=png,
        thumbnail_bytes=png,
        width=1,
        height=1,
        thumb_width=1,
        thumb_height=1,
        formats={"png": "image/png"},
    )
    records = asyncio.run(
        store.store(
            organization_id="org-1",
            job_id="job-1",
            draft_id="draft-1",
            bundle=bundle,
            metadata={"test": True},
        )
    )
    assert len(records) == 3
    assert storage_backend_name(storage) == "local"
    for rec in records:
        assert storage.exists(rec.object_key)
        assert rec.metadata.get("storage_backend") == "local"


def test_require_storage_flag() -> None:
    with pytest.raises(StorageWriteError):
        MemoryImageAssetStore(storage=None, require_storage=True)
