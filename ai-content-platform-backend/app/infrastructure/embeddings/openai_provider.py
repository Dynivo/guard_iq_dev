"""OpenAI embeddings adapter (httpx) — EmbeddingProvider port."""

from __future__ import annotations

import httpx

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.modules.knowledge.domain.models import EmbeddingResult

logger = get_logger(__name__)

_BASE_URL = "https://api.openai.com/v1"


class OpenAIEmbeddingProvider:
    """OpenAI text embeddings via /v1/embeddings."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        dimensions: int | None = None,
        base_url: str = _BASE_URL,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        settings = get_settings()
        self._api_key = (api_key if api_key is not None else settings.OPENAI_API_KEY).strip()
        self._model = model or settings.OPENAI_EMBEDDING_MODEL
        self._dimensions = dimensions if dimensions is not None else settings.OPENAI_EMBEDDING_DIMENSION
        self._base_url = base_url.rstrip("/")
        self._client = client

    def _require_key(self) -> None:
        if not self._api_key:
            raise AppError("OPENAI_API_KEY is required when EMBEDDING_PROVIDER=openai")

    async def embed(self, text: str) -> EmbeddingResult:
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        self._require_key()
        if not texts:
            return []
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        body: dict = {"model": self._model, "input": texts}
        if self._dimensions:
            body["dimensions"] = self._dimensions

        if self._client is not None:
            resp = await self._client.post(
                f"{self._base_url}/embeddings", headers=headers, json=body
            )
            resp.raise_for_status()
            data = resp.json()
        else:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self._base_url}/embeddings", headers=headers, json=body
                )
                resp.raise_for_status()
                data = resp.json()

        items = sorted(data.get("data") or [], key=lambda x: int(x.get("index", 0)))
        if len(items) != len(texts):
            raise AppError("OpenAI embeddings response length mismatch")
        model_version = str(data.get("model") or self._model)
        out: list[EmbeddingResult] = []
        for item in items:
            vector = [float(v) for v in item["embedding"]]
            out.append(
                EmbeddingResult(
                    vector=vector,
                    model_version=model_version,
                    dimensions=len(vector),
                )
            )
        logger.info(
            "OpenAI embeddings: model=%s n=%d dim=%d",
            model_version,
            len(out),
            out[0].dimensions if out else 0,
        )
        return out
