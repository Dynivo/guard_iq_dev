"""Default AI Orchestrator — owns retries, fallback, cache, metrics, streaming, plugins."""

from __future__ import annotations

import asyncio
import hashlib
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from app.core.logging import get_logger
from app.core.observability import ensure_correlation_id
from app.infrastructure.events.factory import get_event_bus
from app.modules.ai.application.circuit_breaker import CircuitBreakerRegistry
from app.modules.ai.application.cost import YamlCostEstimator
from app.modules.ai.application.health import ProviderHealthRegistry
from app.modules.ai.application.lifecycle import (
    AIRequestRecord,
    AIRequestState,
    InMemoryLifecycleStore,
    InMemoryRequestRecorder,
)
from app.modules.ai.application.provider_budgets import (
    ProviderBudgetExceeded,
    ProviderBudgetService,
)
from app.modules.ai.application.plugins import (
    CompositeValidator,
    JsonValidator,
    LengthValidator,
    OutputFormatter,
    PromptSanitizer,
    CitationExtractor,
)
from app.modules.ai.domain.models import OrchestratorRequest, OrchestratorResult, StreamChunk
from app.modules.ai.domain.ports import CostEstimator
from app.modules.ai_cache.domain.ports import AICachePort
from app.modules.ai_cache.infrastructure.memory_cache import InMemoryAICache
from app.modules.providers.domain.models import ProviderTarget, RoutingDecision
from app.modules.providers.domain.ports import CapabilityRouter, ProviderFactory
from app.shared.ai_types import (
    CompletionRequest,
    CompletionResult,
    StreamingUnsupportedError,
)
from app.shared.events import provider_failed

logger = get_logger(__name__)


def _cache_key(
    *,
    org_id: str,
    capability: str,
    model: str,
    prompt: str,
    system: str,
    response_format: str,
) -> str:
    digest = hashlib.sha256(
        f"{org_id}|{capability}|{model}|{system}|{response_format}|{prompt}".encode()
    ).hexdigest()
    return f"ai:{org_id}:{capability}:{digest}"


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class DefaultAIOrchestrator:
    def __init__(
        self,
        *,
        router: CapabilityRouter,
        provider_factory: ProviderFactory,
        cache: AICachePort | None = None,
        cost_estimator: CostEstimator | None = None,
        circuit_breaker: CircuitBreakerRegistry | None = None,
        health: ProviderHealthRegistry | None = None,
        lifecycle_store: InMemoryLifecycleStore | None = None,
        recorder: Any = None,
        pre_processors: list | None = None,
        post_processors: list | None = None,
        validators: CompositeValidator | None = None,
        budget_guard: ProviderBudgetService | None = None,
    ) -> None:
        self._router = router
        self._factory = provider_factory
        self._cache = cache or InMemoryAICache()
        self._cost = cost_estimator or YamlCostEstimator()
        self._health = health or ProviderHealthRegistry(
            breaker=circuit_breaker or CircuitBreakerRegistry()
        )
        self._breaker = self._health.breaker
        self._lifecycle = lifecycle_store or InMemoryLifecycleStore()
        self._recorder = recorder or InMemoryRequestRecorder()
        self._pre = list(pre_processors or [PromptSanitizer()])
        self._post = list(post_processors or [CitationExtractor(), OutputFormatter()])
        self._validators = validators or CompositeValidator(
            [JsonValidator(), LengthValidator()]
        )
        # Tests and embedded callers may omit durable accounting; the
        # production factory always supplies the real guard.
        self._budgets = budget_guard

    async def complete(self, capability: str, prompt: str, **overrides: Any) -> CompletionResult:
        req = OrchestratorRequest(
            capability=capability,
            prompt=prompt,
            organization_id=overrides.get("organization_id"),
            correlation_id=str(overrides.get("correlation_id") or ""),
            system_message=str(overrides.get("system_message") or ""),
            response_format=str(overrides.get("response_format") or "json"),
            model=overrides.get("model"),
            temperature=overrides.get("temperature"),
            max_tokens=overrides.get("max_tokens"),
            prompt_version=str(overrides.get("prompt_version") or ""),
            bypass_cache=bool(overrides.get("bypass_cache", False)),
        )
        outcome = await self.execute(req)
        if not outcome.success or outcome.result is None:
            raise RuntimeError(outcome.error_message or "AI orchestrator call failed")
        return outcome.result

    async def execute(self, request: OrchestratorRequest) -> OrchestratorResult:
        correlation_id = ensure_correlation_id(request.correlation_id or None)
        request.correlation_id = correlation_id
        for pre in self._pre:
            request = await pre.process(request)

        life = AIRequestRecord(
            request_id=str(uuid.uuid4()),
            correlation_id=correlation_id,
            capability=request.capability,
            organization_id=request.organization_id,
            prompt_hash=_hash_text(request.prompt),
        )
        life.transition(AIRequestState.QUEUED)
        life.transition(AIRequestState.RUNNING)
        await self._lifecycle.save(life)

        started = time.perf_counter()
        decision = await self._router.resolve(
            request.capability,
            organization_id=request.organization_id,
        )

        # Consensus / pinned-provider fan-out: override primary target without rewriting router.
        if request.provider_override:
            override = request.provider_override.strip().lower()
            model = request.model or decision.primary.model
            decision = RoutingDecision(
                capability=decision.capability,
                primary=ProviderTarget(provider=override, model=model or ""),
                fallbacks=() if request.skip_fallbacks else decision.fallbacks,
                temperature=decision.temperature,
                max_tokens=decision.max_tokens,
                timeout_ms=decision.timeout_ms,
                retry=decision.retry,
                cacheable=False if request.bypass_cache else decision.cacheable,
                cache_ttl_seconds=decision.cache_ttl_seconds,
                sensitive=decision.sensitive,
                failure_threshold=decision.failure_threshold,
                recovery_timeout_ms=decision.recovery_timeout_ms,
                source="provider_override",
                model_id=decision.model_id,
                context_window=decision.context_window,
            )
        elif request.skip_fallbacks:
            decision = RoutingDecision(
                capability=decision.capability,
                primary=decision.primary,
                fallbacks=(),
                temperature=decision.temperature,
                max_tokens=decision.max_tokens,
                timeout_ms=decision.timeout_ms,
                retry=decision.retry,
                cacheable=decision.cacheable,
                cache_ttl_seconds=decision.cache_ttl_seconds,
                sensitive=decision.sensitive,
                failure_threshold=decision.failure_threshold,
                recovery_timeout_ms=decision.recovery_timeout_ms,
                source=decision.source,
                model_id=decision.model_id,
                context_window=decision.context_window,
            )

        org_key = str(request.organization_id or "global")
        model_hint = request.model or decision.primary.model
        cache_key = _cache_key(
            org_id=org_key,
            capability=decision.capability,
            model=model_hint,
            prompt=request.prompt,
            system=request.system_message,
            response_format=request.response_format,
        )

        if (
            not request.bypass_cache
            and decision.cacheable
            and not decision.sensitive
        ):
            cached = await self._cache.get(cache_key)
            if cached:
                result = CompletionResult(
                    text=str(cached.get("text", "")),
                    model=str(cached.get("model", model_hint)),
                    provider=str(cached.get("provider", "")),
                    latency_ms=int(cached.get("latency_ms", 0)),
                    tokens_in=int(cached.get("tokens_in", 0)),
                    tokens_out=int(cached.get("tokens_out", 0)),
                    cost_estimate=float(cached.get("cost_estimate", 0.0)),
                    cache_hit=True,
                )
                life.cache_hit = True
                life.provider = result.provider
                life.model = result.model
                life.output_hash = _hash_text(result.text)
                life.transition(AIRequestState.COMPLETED, detail="cache_hit")
                await self._lifecycle.save(life)
                await self._recorder.record(
                    {
                        "request_id": life.request_id,
                        "correlation_id": correlation_id,
                        "organization_id": str(request.organization_id)
                        if request.organization_id
                        else None,
                        "capability": decision.capability,
                        "provider": result.provider,
                        "model": result.model,
                        "prompt_hash": life.prompt_hash,
                        "output_hash": life.output_hash,
                        "cache_hit": True,
                        "latency_ms": result.latency_ms,
                        "tokens_in": result.tokens_in,
                        "tokens_out": result.tokens_out,
                        "cost_estimate": result.cost_estimate,
                        "success": True,
                        "evaluation_status": "pending",
                    }
                )
                outcome = OrchestratorResult(
                    success=True,
                    result=result,
                    capability=decision.capability,
                    provider=result.provider,
                    model=result.model,
                    cache_hit=True,
                    metrics=self._metrics(
                        decision,
                        result,
                        started,
                        cache_hit=True,
                        retries=0,
                        correlation_id=correlation_id,
                    ),
                )
                for post in self._post:
                    outcome = await post.process(request, outcome)
                return outcome

        targets = (decision.primary, *decision.fallbacks)
        total_retries = 0
        last_error = "All providers failed"
        using_fallback = False

        for target in targets:
            if using_fallback:
                life.transition(AIRequestState.FALLBACK, detail=target.provider)
                await self._lifecycle.save(life)
            if self._breaker.is_open(
                target.provider,
                failure_threshold=decision.failure_threshold,
                recovery_timeout_ms=decision.recovery_timeout_ms,
            ):
                logger.info(
                    "circuit_open",
                    extra={
                        "app_module": "ai",
                        "operation": "execute",
                        "provider": target.provider,
                        "correlation_id": correlation_id,
                    },
                )
                using_fallback = True
                continue

            provider = self._factory.create(target.provider, model=target.model)
            attempts = max(1, decision.retry.max_attempts)
            for attempt in range(1, attempts + 1):
                reservation = None
                paid_cost = 0.0
                if attempt > 1:
                    life.transition(AIRequestState.RETRYING, detail=f"attempt={attempt}")
                    await self._lifecycle.save(life)
                try:
                    completion_req = self._build_completion_request(
                        request, decision, target
                    )
                    # Reserve a conservative worst-case amount before making a
                    # paid call. The actual token cost replaces it on success.
                    estimated_input_tokens = max(1, len(request.prompt) // 4)
                    estimated_output_tokens = int(
                        request.max_tokens or decision.max_tokens or 4096
                    )
                    reservation = (
                        await self._budgets.reserve(
                            request.organization_id,
                            provider=target.provider,
                            model=target.model,
                            estimated_cost_usd=self._cost.estimate(
                                provider=target.provider,
                                model=target.model,
                                tokens_in=estimated_input_tokens,
                                tokens_out=estimated_output_tokens,
                            ),
                        )
                        if self._budgets is not None
                        else None
                    )
                    result = await asyncio.wait_for(
                        provider.complete(completion_req),
                        timeout=max(0.001, decision.timeout_ms / 1000.0),
                    )
                    result.cost_estimate = self._cost.estimate(
                        provider=result.provider or target.provider,
                        model=result.model or target.model,
                        tokens_in=result.tokens_in,
                        tokens_out=result.tokens_out,
                    )
                    paid_cost = float(result.cost_estimate or 0.0)
                    result.retries = total_retries

                    ok, verr = self._validators.validate(
                        result.text, response_format=request.response_format
                    )
                    if not ok:
                        raise RuntimeError(verr or "validation_failed")

                    self._health.record_success(
                        target.provider, latency_ms=result.latency_ms
                    )

                    if decision.cacheable and not decision.sensitive:
                        await self._cache.set(
                            cache_key,
                            {
                                "text": result.text,
                                "model": result.model,
                                "provider": result.provider,
                                "latency_ms": result.latency_ms,
                                "tokens_in": result.tokens_in,
                                "tokens_out": result.tokens_out,
                                "cost_estimate": result.cost_estimate,
                            },
                            decision.cache_ttl_seconds,
                        )

                    life.provider = result.provider
                    life.model = result.model
                    life.latency_ms = result.latency_ms
                    life.cost_estimate = result.cost_estimate
                    life.output_hash = _hash_text(result.text)
                    life.transition(AIRequestState.COMPLETED)
                    await self._lifecycle.save(life)
                    await self._recorder.record(
                        {
                            "request_id": life.request_id,
                            "correlation_id": correlation_id,
                            "organization_id": str(request.organization_id)
                            if request.organization_id
                            else None,
                            "capability": decision.capability,
                            "provider": result.provider,
                            "model": result.model,
                            "model_id": decision.model_id,
                            "prompt_hash": life.prompt_hash,
                            "output_hash": life.output_hash,
                            "cache_hit": False,
                            "latency_ms": result.latency_ms,
                            "tokens_in": result.tokens_in,
                            "tokens_out": result.tokens_out,
                            "cost_estimate": result.cost_estimate,
                            "retries": total_retries,
                            "success": True,
                            "evaluation_status": "pending",
                        }
                    )
                    if self._budgets is not None:
                        await self._budgets.settle(
                            reservation,
                            actual_cost_usd=paid_cost,
                        )

                    outcome = OrchestratorResult(
                        success=True,
                        result=result,
                        capability=decision.capability,
                        provider=result.provider,
                        model=result.model,
                        cache_hit=False,
                        retries=total_retries,
                        metrics=self._metrics(
                            decision,
                            result,
                            started,
                            cache_hit=False,
                            retries=total_retries,
                            correlation_id=correlation_id,
                        ),
                    )
                    for post in self._post:
                        outcome = await post.process(request, outcome)
                    return outcome
                except ProviderBudgetExceeded as exc:
                    # A model at its ceiling may fall back to another configured
                    # model, but retrying the same model cannot help.
                    last_error = str(exc)
                    logger.warning(
                        "model_budget_exceeded",
                        extra={
                            "provider": target.provider,
                            "model": target.model,
                            "organization_id": str(request.organization_id or ""),
                        },
                    )
                    break
                except Exception as exc:  # noqa: BLE001
                    if reservation is not None and self._budgets is not None:
                        if paid_cost > 0:
                            await self._budgets.settle(
                                reservation,
                                actual_cost_usd=paid_cost,
                            )
                        else:
                            await self._budgets.cancel(reservation)
                    last_error = str(exc)
                    total_retries += 1
                    self._health.record_failure(
                        target.provider,
                        error=last_error,
                        failure_threshold=decision.failure_threshold,
                    )
                    await self._emit_provider_failed(
                        request,
                        provider_name=getattr(provider, "provider_name", target.provider),
                        capability=decision.capability,
                        error=last_error,
                        correlation_id=correlation_id,
                    )
                    if attempt < attempts:
                        delay = decision.retry.delay_ms / 1000.0
                        if decision.retry.strategy == "exponential_backoff":
                            delay = min(
                                decision.retry.max_delay_ms / 1000.0,
                                delay * (2 ** (attempt - 1)),
                            )
                        await asyncio.sleep(delay)
                        continue
                    break
            using_fallback = True

        life.error_message = last_error
        life.provider = decision.primary.provider
        life.model = decision.primary.model
        life.transition(AIRequestState.FAILED, detail=last_error)
        await self._lifecycle.save(life)
        await self._recorder.record(
            {
                "request_id": life.request_id,
                "correlation_id": correlation_id,
                "organization_id": str(request.organization_id)
                if request.organization_id
                else None,
                "capability": decision.capability,
                "provider": decision.primary.provider,
                "model": decision.primary.model,
                "model_id": decision.model_id,
                "prompt_hash": life.prompt_hash,
                "cache_hit": False,
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "retries": total_retries,
                "success": False,
                "error_message": last_error,
                "evaluation_status": "failed",
            }
        )
        return OrchestratorResult(
            success=False,
            capability=decision.capability,
            provider=decision.primary.provider,
            model=decision.primary.model,
            error_code="PROVIDER_EXHAUSTED",
            error_message=last_error,
            retries=total_retries,
            metrics={
                "correlation_id": correlation_id,
                "capability": decision.capability,
                "provider": decision.primary.provider,
                "retries": total_retries,
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "cache_hit": False,
                "success": False,
            },
        )

    async def execute_stream(
        self, request: OrchestratorRequest
    ) -> AsyncIterator[StreamChunk]:
        correlation_id = ensure_correlation_id(request.correlation_id or None)
        request.correlation_id = correlation_id
        for pre in self._pre:
            request = await pre.process(request)
        decision = await self._router.resolve(
            request.capability,
            organization_id=request.organization_id,
        )
        targets = (decision.primary, *decision.fallbacks)
        last_error = "Streaming failed"

        for target in targets:
            provider = self._factory.create(target.provider, model=target.model)
            completion_req = self._build_completion_request(request, decision, target)
            try:
                stream = provider.complete_stream(completion_req)
                async for chunk in stream:
                    yield StreamChunk(
                        text=chunk,
                        done=False,
                        provider=target.provider,
                        model=target.model or completion_req.model,
                    )
                yield StreamChunk(
                    text="",
                    done=True,
                    provider=target.provider,
                    model=target.model or completion_req.model,
                )
                return
            except StreamingUnsupportedError:
                if request.allow_nonstream_fallback:
                    outcome = await self.execute(request)
                    if outcome.success and outcome.result:
                        yield StreamChunk(
                            text=outcome.result.text,
                            done=True,
                            provider=outcome.provider,
                            model=outcome.model,
                        )
                        return
                last_error = f"Streaming unsupported for {target.provider}"
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                continue

        raise RuntimeError(last_error)

    async def execute_many(
        self, requests: list[OrchestratorRequest]
    ) -> list[OrchestratorResult]:
        """Run requests in parallel. One failure does not cancel siblings."""
        raw = await asyncio.gather(
            *(self.execute(r) for r in requests),
            return_exceptions=True,
        )
        outcomes: list[OrchestratorResult] = []
        for idx, item in enumerate(raw):
            if isinstance(item, OrchestratorResult):
                outcomes.append(item)
                continue
            err = str(item) if item is not None else "unknown_error"
            req = requests[idx] if idx < len(requests) else None
            logger.error(
                "orchestrator.execute_many_item_failed",
                extra={
                    "app_module": "ai",
                    "operation": "execute_many",
                    "index": idx,
                    "capability": getattr(req, "capability", ""),
                    "provider_override": getattr(req, "provider_override", None),
                    "correlation_id": getattr(req, "correlation_id", ""),
                    "error": err,
                    "outcome": "failure",
                },
            )
            outcomes.append(
                OrchestratorResult(
                    success=False,
                    capability=getattr(req, "capability", "") if req else "",
                    provider=str(getattr(req, "provider_override", "") or ""),
                    model=str(getattr(req, "model", "") or ""),
                    error_code="EXECUTE_MANY_EXCEPTION",
                    error_message=err,
                    metrics={"success": False, "exception": True},
                )
            )
        return outcomes

    def _build_completion_request(
        self,
        request: OrchestratorRequest,
        decision: RoutingDecision,
        target: ProviderTarget,
    ) -> CompletionRequest:
        return CompletionRequest(
            prompt=request.prompt,
            model=request.model or target.model or decision.primary.model,
            temperature=(
                request.temperature if request.temperature is not None else decision.temperature
            ),
            max_tokens=(
                request.max_tokens if request.max_tokens is not None else decision.max_tokens
            ),
            system_message=request.system_message,
            response_format=request.response_format,
            correlation_id=request.correlation_id,
        )

    def _metrics(
        self,
        decision: RoutingDecision,
        result: CompletionResult,
        started: float,
        *,
        cache_hit: bool,
        retries: int,
        correlation_id: str,
    ) -> dict[str, Any]:
        return {
            "correlation_id": correlation_id,
            "capability": decision.capability,
            "provider": result.provider,
            "model": result.model,
            "model_id": decision.model_id,
            "context_window": decision.context_window,
            "latency_ms": result.latency_ms,
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "tokens_in": result.tokens_in,
            "tokens_out": result.tokens_out,
            "cost_estimate": result.cost_estimate,
            "cache_hit": cache_hit,
            "retries": retries,
            "success": True,
            "provider_health": self._health.snapshot(
                result.provider,
                failure_threshold=decision.failure_threshold,
                recovery_timeout_ms=decision.recovery_timeout_ms,
            ),
        }

    async def _emit_provider_failed(
        self,
        request: OrchestratorRequest,
        *,
        provider_name: str,
        capability: str,
        error: str,
        correlation_id: str,
    ) -> None:
        try:
            await get_event_bus().publish(
                provider_failed(
                    organization_id=request.organization_id or uuid.UUID(int=0),
                    provider=provider_name,
                    capability=capability,
                    error_message=error,
                    correlation_id=correlation_id,
                )
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to publish ProviderFailed event")
