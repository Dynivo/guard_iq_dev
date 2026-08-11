"""Azure OpenAI embeddings adapter (httpx) — EmbeddingProvider port."""

from __future__ import annotations

import httpx

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.modules.knowledge.domain.models import EmbeddingResult

logger = get_logger(__name__)


class AzureOpenAIEmbeddingProvider:
    """Azure OpenAI embeddings via deployment endpoint."""

    def __init__(
        self,
        *,
        endpoint: str | None = None,
        api_key: str | None = None,
        api_version: str | None = None,
        deployment: str | None = None,
        dimensions: int | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        settings = get_settings()
        self._endpoint = (endpoint if endpoint is not None else settings.AZURE_OPENAI_ENDPOINT).rstrip(
            "/"
        )
        self._api_key = (
            api_key if api_key is not None else settings.AZURE_OPENAI_API_KEY
        ).strip()
        self._api_version = api_version or settings.AZURE_OPENAI_API_VERSION
        self._deployment = deployment or settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT
        self._dimensions = (
            dimensions if dimensions is not None else settings.AZURE_EMBEDDING_DIMENSION
        )
        self._client = client

    def _require_config(self) -> None:
        if not self._endpoint or not self._api_key or not self._deployment:
            raise AppError(
                "AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, and "
                "AZURE_OPENAI_EMBEDDING_DEPLOYMENT are required when "
                "EMBEDDING_PROVIDER=azure_openai"
            )

    def _url(self) -> str:
        return (
            f"{self._endpoint}/openai/deployments/{self._deployment}/embeddings"
            f"?api-version={self._api_version}"
        )

    async def embed(self, text: str) -> EmbeddingResult:
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        self._require_config()
        if not texts:
            return []
        headers = {
            "api-key": self._api_key,
            "Content-Type": "application/json",
        }
        body: dict = {"input": texts}
        if self._dimensions:
            body["dimensions"] = self._dimensions

        if self._client is not None:
            resp = await self._client.post(self._url(), headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
        else:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(self._url(), headers=headers, json=body)
                resp.raise_for_status()
                data = resp.json()

        items = sorted(data.get("data") or [], key=lambda x: int(x.get("index", 0)))
        if len(items) != len(texts):
            raise AppError("Azure OpenAI embeddings response length mismatch")
        model_version = str(data.get("model") or self._deployment)
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
            "Azure OpenAI embeddings: deployment=%s n=%d dim=%d",
            self._deployment,
            len(out),
            out[0].dimensions if out else 0,
        )
        return out
