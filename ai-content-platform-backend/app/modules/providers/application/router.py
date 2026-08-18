"""Default Capability Router — YAML + Model Registry + optional org DB overrides.

PROVIDER_MIX_ENABLED can rotate non-writing capabilities. Draft writing uses
multi-LLM consensus scoring when CONSENSUS_ENABLED (best content wins).
"""

from __future__ import annotations

import itertools
import threading
import uuid

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.providers.domain.models import (
    ProviderTarget,
    RetryConfig,
    RoutingDecision,
    normalize_capability,
)
from app.modules.providers.domain.ports import ProviderConfigRepository
from app.modules.providers.infrastructure.model_registry import YamlModelRegistry
from app.modules.providers.infrastructure.provider_factory import DefaultProviderFactory
from app.modules.providers.infrastructure.yaml_capability_config import YamlCapabilityConfigLoader

logger = get_logger(__name__)

# Optional light mix for non-draft capabilities (draft writing uses consensus scoring)
_MIX_CAPABILITIES = frozenset(
    {
        "planning",
        "analysis",
        "prompt_building",
        "image_prompting",
    }
)

# Preferred chat models per provider (used when mixing)
_CHAT_POOL: tuple[ProviderTarget, ...] = (
    ProviderTarget(provider="openai", model="gpt-4o-mini"),
    ProviderTarget(provider="gemini", model="gemini-flash-latest"),
    ProviderTarget(provider="grok", model="llama-3.3-70b-versatile"),
    ProviderTarget(provider="azure_openai", model="gpt-4"),
    ProviderTarget(provider="perplexity", model="sonar"),
    ProviderTarget(provider="anthropic", model="claude-3-5-haiku-latest"),
)

_mix_lock = threading.Lock()
_mix_counter = itertools.count()


class DefaultCapabilityRouter:
    """Selection only. Never executes LLM calls."""

    def __init__(
        self,
        loader: YamlCapabilityConfigLoader | None = None,
        *,
        org_repo: ProviderConfigRepository | None = None,
        model_registry: YamlModelRegistry | None = None,
        provider_factory: DefaultProviderFactory | None = None,
    ) -> None:
        self._loader = loader or YamlCapabilityConfigLoader()
        self._org_repo = org_repo
        self._models = model_registry or YamlModelRegistry()
        self._factory = provider_factory or DefaultProviderFactory()

    def _apply_registry(
        self, provider: str, model: str, model_id: str
    ) -> tuple[str, str, str, int | None]:
        """Resolve model_id through registry when present."""
        mid = model_id
        context_window = None
        if mid:
            spec = self._models.get(mid)
            if spec:
                return spec.provider, spec.model, mid, spec.context_window
        for sid, spec in self._models.all().items():
            if spec.model == model and (not provider or spec.provider == provider):
                return spec.provider, spec.model, sid, spec.context_window
        return provider, model, mid, context_window

    def _available_chat_pool(self) -> list[ProviderTarget]:
        """Providers with credentials configured."""
        pool: list[ProviderTarget] = []
        for target in _CHAT_POOL:
            if self._factory.has_credentials(target.provider):
                pool.append(target)
        return pool

    def _default_target(self) -> ProviderTarget:
        """Return the configured real default with its normal chat model."""
        settings = get_settings()
        provider = str(settings.DEFAULT_LLM_PROVIDER).strip().lower()
        if provider not in self._factory.known_providers():
            provider = "gemini"
        return next(
            (target for target in _CHAT_POOL if target.provider == provider),
            ProviderTarget(provider=provider, model=""),
        )

    def _mix_targets(
        self,
        *,
        yaml_primary: ProviderTarget,
        yaml_fallbacks: tuple[ProviderTarget, ...],
    ) -> tuple[ProviderTarget, tuple[ProviderTarget, ...]]:
        """Round-robin primary among configured providers; others become fallbacks."""
        pool = self._available_chat_pool()
        if len(pool) <= 1:
            # Keep YAML primary if it has credentials; else first available / yaml
            if pool:
                primary = pool[0]
                rest = tuple(t for t in yaml_fallbacks if t.provider != primary.provider)
                return primary, rest
            return yaml_primary, yaml_fallbacks

        with _mix_lock:
            idx = next(_mix_counter) % len(pool)
        primary = pool[idx]
        # Fallbacks: remaining configured providers (preserve variety), then yaml extras
        seen = {primary.provider}
        fallbacks: list[ProviderTarget] = []
        for t in pool:
            if t.provider not in seen:
                fallbacks.append(t)
                seen.add(t.provider)
        for t in yaml_fallbacks:
            if t.provider not in seen and self._factory.has_credentials(t.provider):
                fallbacks.append(t)
                seen.add(t.provider)
        logger.info(
            "provider_mix capability_pool=%s primary=%s fallbacks=%s",
            [t.provider for t in pool],
            primary.provider,
            [t.provider for t in fallbacks],
        )
        return primary, tuple(fallbacks)

    async def resolve(
        self,
        capability: str,
        *,
        organization_id: uuid.UUID | None = None,
    ) -> RoutingDecision:
        canonical = normalize_capability(capability)
        settings = get_settings()
        mix_enabled = bool(getattr(settings, "PROVIDER_MIX_ENABLED", True))

        if organization_id is not None and self._org_repo is not None:
            override = await self._org_repo.get_for_capability(organization_id, canonical)
            if override is None:
                override = await self._org_repo.get_for_capability(organization_id, capability)
            if override:
                cfg_json = override.get("config_json") or {}
                fallbacks = tuple(
                    ProviderTarget(provider=str(f["provider"]), model=str(f.get("model") or ""))
                    for f in (cfg_json.get("fallbacks") or [])
                    if str(f.get("provider") or "").lower()
                    in self._factory.known_providers()
                )
                yaml_cfg = self._loader.get(canonical)
                mid = str(cfg_json.get("model_id") or (yaml_cfg.model_id if yaml_cfg else ""))
                override_provider = str(override["provider"]).strip().lower()
                if override_provider not in self._factory.known_providers():
                    default_target = self._default_target()
                    provider, model, mid, ctx = self._apply_registry(
                        default_target.provider,
                        default_target.model,
                        "",
                    )
                else:
                    provider, model, mid, ctx = self._apply_registry(
                        override_provider,
                        str(override.get("model") or ""),
                        mid,
                    )
                return RoutingDecision(
                    capability=canonical,
                    primary=ProviderTarget(provider=provider, model=model),
                    fallbacks=fallbacks or (yaml_cfg.fallbacks if yaml_cfg else ()),
                    temperature=float(
                        cfg_json.get("temperature", yaml_cfg.temperature if yaml_cfg else 0.5)
                    ),
                    max_tokens=int(
                        cfg_json.get("max_tokens", yaml_cfg.max_tokens if yaml_cfg else 4096)
                    ),
                    timeout_ms=int(
                        cfg_json.get("timeout_ms", yaml_cfg.timeout_ms if yaml_cfg else 60_000)
                    ),
                    retry=yaml_cfg.retry if yaml_cfg else RetryConfig(),
                    cacheable=bool(
                        cfg_json.get("cacheable", yaml_cfg.cacheable if yaml_cfg else True)
                    ),
                    cache_ttl_seconds=int(
                        cfg_json.get(
                            "cache_ttl_seconds",
                            yaml_cfg.cache_ttl_seconds if yaml_cfg else 3_600,
                        )
                    ),
                    sensitive=bool(
                        cfg_json.get("sensitive", yaml_cfg.sensitive if yaml_cfg else False)
                    ),
                    failure_threshold=int(
                        cfg_json.get(
                            "failure_threshold",
                            yaml_cfg.failure_threshold if yaml_cfg else 5,
                        )
                    ),
                    recovery_timeout_ms=int(
                        cfg_json.get(
                            "recovery_timeout_ms",
                            yaml_cfg.recovery_timeout_ms if yaml_cfg else 30_000,
                        )
                    ),
                    source="org_db",
                    model_id=mid,
                    context_window=ctx,
                )

        cfg = self._loader.get(canonical)
        if cfg is None:
            default_target = self._default_target()
            provider, model, mid, ctx = self._apply_registry(
                default_target.provider,
                default_target.model,
                "",
            )
            return RoutingDecision(
                capability=canonical,
                primary=ProviderTarget(provider=provider, model=model),
                fallbacks=(),
                temperature=0.5,
                max_tokens=4096,
                timeout_ms=60_000,
                retry=RetryConfig(),
                cacheable=False,
                cache_ttl_seconds=0,
                sensitive=True,
                failure_threshold=5,
                recovery_timeout_ms=30_000,
                source="default",
                model_id=mid,
                context_window=ctx,
            )

        provider, model, mid, ctx = self._apply_registry(cfg.provider, cfg.model, cfg.model_id)
        primary = ProviderTarget(provider=provider, model=model)
        fallbacks = cfg.fallbacks
        source = "yaml"

        if mix_enabled and canonical in _MIX_CAPABILITIES:
            primary, fallbacks = self._mix_targets(
                yaml_primary=primary,
                yaml_fallbacks=cfg.fallbacks,
            )
            source = "yaml_mix"
            # Refresh model_id for chosen primary when possible
            _, _, mid, ctx = self._apply_registry(primary.provider, primary.model, "")

        return RoutingDecision(
            capability=cfg.name,
            primary=primary,
            fallbacks=fallbacks,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
            timeout_ms=cfg.timeout_ms,
            retry=cfg.retry,
            cacheable=cfg.cacheable,
            cache_ttl_seconds=cfg.cache_ttl_seconds,
            sensitive=cfg.sensitive,
            failure_threshold=cfg.failure_threshold,
            recovery_timeout_ms=cfg.recovery_timeout_ms,
            source=source,
            model_id=mid,
            context_window=ctx,
        )
