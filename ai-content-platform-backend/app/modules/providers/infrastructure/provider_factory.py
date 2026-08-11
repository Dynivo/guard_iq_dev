"""Provider factory — builds AIProvider adapters from config/settings."""

from __future__ import annotations

from app.core.config import get_settings
from app.core.logging import get_logger
from app.infrastructure.llm.anthropic_adapter import AnthropicProvider
from app.infrastructure.llm.azure_openai_adapter import AzureOpenAIProvider
from app.infrastructure.llm.gemini_adapter import GeminiProvider
from app.infrastructure.llm.grok_adapter import GrokProvider
from app.infrastructure.llm.mock_adapter import MockAIProvider
from app.infrastructure.llm.ollama_adapter import OllamaProvider
from app.infrastructure.llm.openai_adapter import OpenAIProvider
from app.infrastructure.llm.openrouter_adapter import OpenRouterProvider
from app.infrastructure.llm.perplexity_adapter import PerplexityProvider
from app.infrastructure.llm.vllm_adapter import VllmProvider
from app.shared.ai_types import AIProvider

logger = get_logger(__name__)


class DefaultProviderFactory:
    """Creates replaceable provider adapters. No retries/cache here."""

    def known_providers(self) -> set[str]:
        return {
            "openai",
            "anthropic",
            "gemini",
            "perplexity",
            "openrouter",
            "ollama",
            "vllm",
            "local",
            "grok",
            "azure_openai",
            "mock",
        }

    def has_credentials(self, provider_name: str) -> bool:
        settings = get_settings()
        name = provider_name.lower()
        if name == "mock":
            return True
        if name == "openai":
            return bool(settings.OPENAI_API_KEY)
        if name == "anthropic":
            return bool(settings.ANTHROPIC_API_KEY)
        if name == "gemini":
            return bool(settings.GEMINI_API_KEY)
        if name == "perplexity":
            return bool(settings.PERPLEXITY_API_KEY)
        if name == "openrouter":
            return bool(settings.OPENROUTER_API_KEY)
        if name == "grok":
            return bool(settings.GROK_API_KEY)
        if name in {"azure_openai", "azure"}:
            return bool(
                settings.AZURE_OPENAI_ENDPOINT
                and settings.AZURE_OPENAI_API_KEY
                and settings.AZURE_OPENAI_DEPLOYMENT_NAME
            )
        if name in {"ollama", "local"}:
            return True  # local URL; no key required
        if name == "vllm":
            return True
        return False

    def create(self, provider_name: str, *, model: str = "") -> AIProvider:
        from app.modules.ai.application.inference import resolve_inference_backend

        settings = get_settings()
        name = provider_name.lower()
        if name == "azure":
            name = "azure_openai"
        backend = resolve_inference_backend(name)
        logger.debug("create provider=%s inference_backend=%s", name, backend.value)

        if name == "mock" or not self.has_credentials(name):
            if name != "mock":
                logger.info(
                    "No credentials for provider '%s', using MockAIProvider",
                    name,
                )
            return MockAIProvider()

        if name == "openai":
            return OpenAIProvider(api_key=settings.OPENAI_API_KEY)
        if name == "anthropic":
            return AnthropicProvider(api_key=settings.ANTHROPIC_API_KEY)
        if name == "gemini":
            return GeminiProvider(api_key=settings.GEMINI_API_KEY)
        if name == "perplexity":
            return PerplexityProvider(api_key=settings.PERPLEXITY_API_KEY)
        if name == "openrouter":
            return OpenRouterProvider(
                api_key=settings.OPENROUTER_API_KEY,
                base_url=settings.OPENROUTER_BASE_URL,
            )
        if name == "grok":
            return GrokProvider(
                api_key=settings.GROK_API_KEY,
                base_url=settings.GROK_BASE_URL or None,
            )
        if name == "azure_openai":
            return AzureOpenAIProvider(
                endpoint=settings.AZURE_OPENAI_ENDPOINT,
                api_key=settings.AZURE_OPENAI_API_KEY,
                api_version=settings.AZURE_OPENAI_API_VERSION,
                deployment=settings.AZURE_OPENAI_DEPLOYMENT_NAME,
            )
        if name in {"ollama", "local"}:
            return OllamaProvider(
                base_url=settings.OLLAMA_BASE_URL,
                api_key=settings.OLLAMA_API_KEY,
            )
        if name == "vllm":
            return VllmProvider(
                base_url=settings.VLLM_BASE_URL,
                api_key=settings.VLLM_API_KEY,
            )

        logger.warning("Unknown provider '%s', using mock", name)
        return MockAIProvider()
