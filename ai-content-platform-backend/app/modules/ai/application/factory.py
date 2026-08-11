"""Compose AI Orchestrator + Capability Router + cache + plugins."""

from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings
from app.modules.ai.application.cost import YamlCostEstimator
from app.modules.ai.application.health import ProviderHealthRegistry
from app.modules.ai.application.lifecycle import InMemoryLifecycleStore
from app.modules.ai.application.orchestrator import DefaultAIOrchestrator
from app.modules.ai.application.postgres_recorder import PostgresRequestRecorder
from app.modules.ai.application.plugins import (
    CitationExtractor,
    CompositeValidator,
    JsonValidator,
    LengthValidator,
    OutputFormatter,
    PromptSanitizer,
)
from app.modules.ai_cache.infrastructure.memory_cache import InMemoryAICache
from app.modules.ai_cache.infrastructure.redis_cache import RedisAICache
from app.modules.providers.application.router import DefaultCapabilityRouter
from app.modules.providers.domain.ports import ProviderConfigRepository
from app.modules.providers.infrastructure.model_registry import YamlModelRegistry
from app.modules.providers.infrastructure.provider_factory import DefaultProviderFactory
from app.modules.providers.infrastructure.yaml_capability_config import (
    YamlCapabilityConfigLoader,
)


class AIOrchestratorFactory:
    @staticmethod
    def create(
        *,
        config_path: Path | None = None,
        org_repo: ProviderConfigRepository | None = None,
        use_redis_cache: bool | None = None,
    ) -> DefaultAIOrchestrator:
        settings = get_settings()
        loader = YamlCapabilityConfigLoader(config_path)
        factory = DefaultProviderFactory()
        router = DefaultCapabilityRouter(
            loader,
            org_repo=org_repo,
            model_registry=YamlModelRegistry(),
            provider_factory=factory,
        )

        prefer_redis = (
            settings.AI_CACHE_BACKEND == "redis"
            if use_redis_cache is None
            else use_redis_cache
        )
        if prefer_redis:
            cache = RedisAICache(settings.REDIS_URL)
        else:
            cache = InMemoryAICache()

        return DefaultAIOrchestrator(
            router=router,
            provider_factory=factory,
            cache=cache,
            cost_estimator=YamlCostEstimator(),
            health=ProviderHealthRegistry(),
            lifecycle_store=InMemoryLifecycleStore(),
            recorder=PostgresRequestRecorder(),
            pre_processors=[PromptSanitizer()],
            post_processors=[CitationExtractor(), OutputFormatter()],
            validators=CompositeValidator([JsonValidator(), LengthValidator()]),
        )
