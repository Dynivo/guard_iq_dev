"""M4 AI Orchestrator + Capability Router unit tests."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import pytest

from app.modules.ai.application.circuit_breaker import CircuitBreakerRegistry
from app.modules.ai.application.cost import YamlCostEstimator
from app.modules.ai.application.factory import AIOrchestratorFactory
from app.modules.ai.application.orchestrator import DefaultAIOrchestrator
from app.modules.ai.domain.models import OrchestratorRequest
from app.modules.ai_cache.infrastructure.memory_cache import InMemoryAICache
from app.modules.providers.application.router import DefaultCapabilityRouter
from app.modules.providers.domain.models import normalize_capability
from app.modules.providers.infrastructure.provider_factory import DefaultProviderFactory
from app.modules.providers.infrastructure.yaml_capability_config import (
    YamlCapabilityConfigLoader,
)
from app.shared.ai_types import CompletionRequest, CompletionResult

CONFIGS = Path(__file__).resolve().parents[2] / "configs" / "providers"


class _FailThenSucceed:
    def __init__(self, fail_times: int = 1) -> None:
        self.fail_times = fail_times
        self.calls = 0

    @property
    def provider_name(self) -> str:
        return "flaky"

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("transient")
        return CompletionResult(text='{"ok":true}', model="m", provider="flaky")

    async def complete_stream(self, request: CompletionRequest):
        yield '{"ok":true}'


class _AlwaysFail:
    @property
    def provider_name(self) -> str:
        return "bad"

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        raise RuntimeError("hard fail")

    async def complete_stream(self, request: CompletionRequest):
        raise RuntimeError("hard fail")
        yield  # pragma: no cover


class _StaticProvider:
    def __init__(self, name: str = "test") -> None:
        self._name = name

    @property
    def provider_name(self) -> str:
        return self._name

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        return CompletionResult(text='{"ok":true}', model="test-model", provider=self._name)

    async def complete_stream(self, request: CompletionRequest):
        yield '{"ok":true}'


class _FakeFactory:
    def __init__(self, mapping: dict) -> None:
        self._mapping = mapping

    def create(self, provider_name: str, *, model: str = ""):
        return self._mapping[provider_name]

    def known_providers(self) -> set[str]:
        return set(self._mapping)


def test_normalize_capability_aliases() -> None:
    assert normalize_capability("relevance") == "relevance_scoring"
    assert normalize_capability("copywriting") == "writing"
    assert normalize_capability("image_prompt") == "image_prompting"


def test_yaml_config_loads_capabilities() -> None:
    loader = YamlCapabilityConfigLoader(CONFIGS / "default.yaml")
    cfg = loader.get("writing")
    assert cfg is not None
    assert cfg.provider in {"openai", "gemini"}
    assert loader.get("relevance") is not None  # alias key or normalized


def test_router_resolves_yaml() -> None:
    router = DefaultCapabilityRouter(YamlCapabilityConfigLoader(CONFIGS / "default.yaml"))
    decision = asyncio.run(router.resolve("copywriting"))
    assert decision.capability == "writing"
    assert decision.primary.provider  # mixed or yaml primary
    assert decision.source in {"yaml", "yaml_mix"}


def test_router_mix_rotates_among_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-writing capabilities can still rotate; writing uses consensus scoring."""
    monkeypatch.setenv("PROVIDER_MIX_ENABLED", "true")
    from app.core.config.settings import get_settings

    get_settings.cache_clear()

    class _CredFactory(DefaultProviderFactory):
        def has_credentials(self, provider_name: str) -> bool:
            return provider_name.lower() in {"openai", "gemini", "grok"}

    router = DefaultCapabilityRouter(
        YamlCapabilityConfigLoader(CONFIGS / "default.yaml"),
        provider_factory=_CredFactory(),
    )
    # Writing stays on YAML primary (consensus picks best across models later)
    writing = asyncio.run(router.resolve("writing"))
    assert writing.source == "yaml"
    assert writing.primary.provider == "openai"

    seen: set[str] = set()
    for _ in range(9):
        d = asyncio.run(router.resolve("planning"))
        assert d.source == "yaml_mix"
        seen.add(d.primary.provider)
        assert d.primary.provider in {"openai", "gemini", "grok"}
    assert seen == {"openai", "gemini", "grok"}
    get_settings.cache_clear()


def test_router_unknown_uses_configured_default() -> None:
    router = DefaultCapabilityRouter(YamlCapabilityConfigLoader(CONFIGS / "default.yaml"))
    decision = asyncio.run(router.resolve("totally_unknown_capability_xyz"))
    assert decision.primary.provider == "gemini"
    assert decision.source == "default"


def test_router_replaces_legacy_mock_org_provider_and_model() -> None:
    class _LegacyOrgRepo:
        async def get_for_capability(self, org_id, capability):
            return {
                "provider": "mock",
                "model": "mock-v1",
                "config_json": {"model_id": "mock-v1"},
            }

    router = DefaultCapabilityRouter(
        YamlCapabilityConfigLoader(CONFIGS / "default.yaml"),
        org_repo=_LegacyOrgRepo(),
    )
    decision = asyncio.run(router.resolve("writing", organization_id=uuid.uuid4()))
    assert decision.primary.provider == "gemini"
    assert decision.primary.model == "gemini-flash-latest"
    assert decision.model_id == ""


def test_provider_factory_rejects_removed_mock_provider() -> None:
    with pytest.raises(ValueError, match="Unknown AI provider"):
        DefaultProviderFactory().create("mock")


def test_cache_hit() -> None:
    cache = InMemoryAICache()
    loader = YamlCapabilityConfigLoader(CONFIGS / "default.yaml")
    router = DefaultCapabilityRouter(loader)
    factory = _FakeFactory({"gemini": _StaticProvider("gemini")})
    orch = DefaultAIOrchestrator(router=router, provider_factory=factory, cache=cache)

    req = OrchestratorRequest(capability="summarization", prompt="summarize this article")
    r1 = asyncio.run(orch.execute(req))
    assert r1.success
    assert r1.cache_hit is False
    r2 = asyncio.run(orch.execute(req))
    assert r2.success
    assert r2.cache_hit is True


def test_sensitive_not_cached() -> None:
    cache = InMemoryAICache()
    loader = YamlCapabilityConfigLoader(CONFIGS / "default.yaml")
    router = DefaultCapabilityRouter(loader)
    factory = _FakeFactory(
        {"gemini": _StaticProvider("gemini"), "openai": _StaticProvider("openai")}
    )
    orch = DefaultAIOrchestrator(router=router, provider_factory=factory, cache=cache)
    req = OrchestratorRequest(
        capability="preference_learning",
        prompt="user preference sensitive",
    )
    r1 = asyncio.run(orch.execute(req))
    assert r1.success
    r2 = asyncio.run(orch.execute(req))
    assert r2.cache_hit is False


def test_retry_then_success() -> None:
    flaky = _FailThenSucceed(fail_times=1)
    loader = YamlCapabilityConfigLoader(CONFIGS / "default.yaml")
    router = DefaultCapabilityRouter(loader)

    class OneShotRouter:
        async def resolve(self, capability, *, organization_id=None):
            d = await router.resolve("writing")
            from app.modules.providers.domain.models import ProviderTarget, RetryConfig

            return d.__class__(
                capability=d.capability,
                primary=ProviderTarget(provider="flaky", model="m"),
                fallbacks=(),
                temperature=d.temperature,
                max_tokens=d.max_tokens,
                timeout_ms=5_000,
                retry=RetryConfig(max_attempts=3, strategy="fixed_delay", delay_ms=1),
                cacheable=False,
                cache_ttl_seconds=0,
                sensitive=True,
                failure_threshold=99,
                recovery_timeout_ms=1,
                source="test",
            )

    orch = DefaultAIOrchestrator(
        router=OneShotRouter(),
        provider_factory=_FakeFactory({"flaky": flaky}),
        cache=InMemoryAICache(),
    )
    result = asyncio.run(
        orch.execute(OrchestratorRequest(capability="writing", prompt="hello"))
    )
    assert result.success
    assert flaky.calls == 2


def test_fallback_provider() -> None:
    from app.modules.providers.domain.models import ProviderTarget, RetryConfig, RoutingDecision

    class FBRouter:
        async def resolve(self, capability, *, organization_id=None):
            return RoutingDecision(
                capability="writing",
                primary=ProviderTarget(provider="bad", model="x"),
                fallbacks=(ProviderTarget(provider="backup", model="backup-v1"),),
                temperature=0.5,
                max_tokens=100,
                timeout_ms=5_000,
                retry=RetryConfig(max_attempts=1),
                cacheable=False,
                cache_ttl_seconds=0,
                sensitive=True,
                failure_threshold=99,
                recovery_timeout_ms=1,
                source="test",
            )

    orch = DefaultAIOrchestrator(
        router=FBRouter(),
        provider_factory=_FakeFactory(
            {"bad": _AlwaysFail(), "backup": _StaticProvider("backup")}
        ),
        cache=InMemoryAICache(),
    )
    result = asyncio.run(
        orch.execute(OrchestratorRequest(capability="writing", prompt="hello world"))
    )
    assert result.success
    assert result.provider == "backup"


def test_circuit_breaker_opens() -> None:
    cb = CircuitBreakerRegistry()
    cb.record_failure("openai", failure_threshold=2)
    assert not cb.is_open("openai", failure_threshold=2, recovery_timeout_ms=60_000)
    cb.record_failure("openai", failure_threshold=2)
    assert cb.is_open("openai", failure_threshold=2, recovery_timeout_ms=60_000)


def test_cost_estimator() -> None:
    est = YamlCostEstimator(CONFIGS / "pricing.yaml")
    # gpt-4o-mini: $0.15/$0.60 per 1M → $0.00015/$0.0006 per 1K
    cost = est.estimate(provider="openai", model="gpt-4o-mini", tokens_in=1000, tokens_out=1000)
    assert cost == pytest.approx(0.00075)
    # Dated API model ids should still resolve
    dated = est.estimate(
        provider="openai",
        model="gpt-4o-mini-2024-07-18",
        tokens_in=1000,
        tokens_out=1000,
    )
    assert dated == pytest.approx(0.00075)


def test_test_provider_streaming() -> None:
    provider = _StaticProvider()
    chunks = []

    async def collect():
        async for c in provider.complete_stream(
            CompletionRequest(prompt="Write a LinkedIn post")
        ):
            chunks.append(c)

    asyncio.run(collect())
    assert "".join(chunks)


def test_orchestrator_streaming() -> None:
    orch = AIOrchestratorFactory.create(config_path=CONFIGS / "default.yaml")
    chunks = []

    async def collect():
        async for ch in orch.execute_stream(
            OrchestratorRequest(capability="writing", prompt="Write a LinkedIn post")
        ):
            chunks.append(ch)

    asyncio.run(collect())
    assert any(c.done for c in chunks) or any(c.text for c in chunks)


def test_provider_factory_known() -> None:
    names = DefaultProviderFactory().known_providers()
    assert {
        "openai",
        "anthropic",
        "gemini",
        "perplexity",
        "openrouter",
        "ollama",
        "vllm",
    }.issubset(names)


def test_factory_create_returns_orchestrator() -> None:
    orch = AIOrchestratorFactory.create()
    assert isinstance(orch, DefaultAIOrchestrator)
