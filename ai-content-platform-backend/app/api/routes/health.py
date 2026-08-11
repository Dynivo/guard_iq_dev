"""Health check endpoint — no auth required."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.schemas.envelope import success_response
from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """Return 200 if the API process is alive."""
    settings = get_settings()
    keyed: list[str] = []
    try:
        from app.modules.providers.infrastructure.provider_factory import DefaultProviderFactory

        factory = DefaultProviderFactory()
        keyed = [
            name
            for name in ("openai", "gemini", "grok", "azure_openai", "perplexity", "anthropic")
            if factory.has_credentials(name)
        ]
    except Exception:  # noqa: BLE001
        keyed = []
    return success_response(
        {
            "status": "healthy",
            "consensus_enabled": bool(settings.CONSENSUS_ENABLED),
            "consensus_policy": settings.CONSENSUS_POLICY,
            "keyed_providers": keyed,
        }
    )