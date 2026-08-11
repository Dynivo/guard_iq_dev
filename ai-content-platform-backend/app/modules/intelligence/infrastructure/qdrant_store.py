"""Compatibility shim — prefer app.infrastructure.vector.qdrant_store."""

from __future__ import annotations

from app.infrastructure.vector.qdrant_store import QdrantVectorStore

__all__ = ["QdrantVectorStore"]
