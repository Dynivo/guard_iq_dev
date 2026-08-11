"""Visual embeddings — similarity, duplicate detection, recommendations."""

from __future__ import annotations

import hashlib
import io
import math
from pathlib import Path

from PIL import Image

from app.modules.image.application.config_loader import load_yaml
from app.modules.image.domain.models import VisualEmbedding


def _cosine(a: tuple[float, ...] | list[float], b: tuple[float, ...] | list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class InMemoryVisualEmbeddingStore:
    def __init__(self) -> None:
        self._items: dict[str, VisualEmbedding] = {}

    def put(self, embedding: VisualEmbedding) -> None:
        self._items[embedding.job_id] = embedding

    def get(self, job_id: str) -> VisualEmbedding | None:
        return self._items.get(job_id)

    def all_for_org(self, organization_id: str) -> list[VisualEmbedding]:
        return [e for e in self._items.values() if e.organization_id == organization_id]


class DefaultVisualEmbeddingService:
    def __init__(
        self,
        store: InMemoryVisualEmbeddingStore | None = None,
        config_dir: Path | None = None,
    ) -> None:
        self._cfg = load_yaml("embeddings.yaml", config_dir)
        self._store = store or InMemoryVisualEmbeddingStore()
        self._dims = int(self._cfg.get("dimensions") or 384)
        self._model = str(self._cfg.get("model_id") or "visual-hash-v1")

    @property
    def store(self) -> InMemoryVisualEmbeddingStore:
        return self._store

    def embed_image(
        self,
        image_bytes: bytes,
        *,
        job_id: str,
        organization_id: str,
        asset_id: str = "",
    ) -> VisualEmbedding:
        features = self._histogram_embed(image_bytes)
        emb = VisualEmbedding(
            job_id=job_id,
            asset_id=asset_id,
            vector=tuple(features),
            model_id=self._model,
            dimensions=len(features),
            organization_id=organization_id,
            metadata={"source": "histogram_hash"},
        )
        self._store.put(emb)
        return emb

    def similar(self, job_id: str, *, top_k: int | None = None) -> list[tuple[str, float]]:
        k = top_k or int(self._cfg.get("recommend_top_k") or 5)
        base = self._store.get(job_id)
        if base is None:
            return []
        scored: list[tuple[str, float]] = []
        for other in self._store.all_for_org(base.organization_id):
            if other.job_id == job_id:
                continue
            scored.append((other.job_id, _cosine(base.vector, other.vector)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]

    def duplicates(self, job_id: str) -> list[tuple[str, float]]:
        thresh = float(self._cfg.get("duplicate_cosine_threshold") or 0.97)
        return [(jid, score) for jid, score in self.similar(job_id, top_k=50) if score >= thresh]

    def recommend(self, job_id: str, *, top_k: int | None = None) -> list[tuple[str, float]]:
        return self.similar(job_id, top_k=top_k)

    def _histogram_embed(self, image_bytes: bytes) -> list[float]:
        try:
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((32, 32))
            hist = img.histogram()  # 768 bins
        except Exception:
            hist = [0] * 768
            digest = hashlib.sha256(image_bytes).digest()
            for i, b in enumerate(digest):
                hist[i % 768] = b

        # Map histogram + hash into fixed dims
        features: list[float] = []
        for i in range(self._dims):
            h = hashlib.sha256(f"vis:{i}".encode() + image_bytes[:64]).digest()
            # Use integer bytes — struct.unpack("f") can yield NaN/Inf which JSONB rejects.
            base = ((h[0] << 8) | h[1]) / 32767.5 - 1.0
            hist_term = hist[i % len(hist)] / 255.0 if hist else 0.0
            value = base * 0.5 + (hist_term - 0.5) * 0.5
            if not math.isfinite(value):
                value = 0.0
            features.append(value)
        norm = math.sqrt(sum(x * x for x in features)) or 1.0
        return [x / norm for x in features]
