"""Default Prompt Builder — compose only; Policy/Security/Lint are separate stages.

Pipeline: Lint → Compile → Optimize → Validate → Security → Policy → PromptRequest
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any

from app.modules.ai_cache.application.namespaced import PromptCache
from app.modules.prompts.domain.models import (
    PromptBuildInput,
    PromptExplanation,
    PromptRequest,
    PromptReplayRecord,
    PromptSectionPresence,
)
from app.modules.prompts.domain.ports import (
    OutputSchemaRegistry,
    PromptCompiler,
    PromptLinter,
    PromptOptimizer,
    PromptPolicyEngine,
    PromptRegistry,
    PromptReplayStore,
    PromptSecurityScanner,
    PromptValidator,
)


class DefaultPromptBuilder:
    def __init__(
        self,
        registry: PromptRegistry,
        compiler: PromptCompiler,
        optimizer: PromptOptimizer,
        validator: PromptValidator,
        schema_registry: OutputSchemaRegistry | None = None,
        replay_store: PromptReplayStore | None = None,
        prompt_cache: PromptCache | None = None,
        analytics: Any | None = None,
        linter: PromptLinter | None = None,
        security_scanner: PromptSecurityScanner | None = None,
        policy_engine: PromptPolicyEngine | None = None,
        partials_dir: Path | None = None,
        policy_id: str = "default",
    ) -> None:
        self._registry = registry
        self._compiler = compiler
        self._optimizer = optimizer
        self._validator = validator
        self._schemas = schema_registry
        self._replay = replay_store
        self._cache = prompt_cache
        self._analytics = analytics
        self._linter = linter
        self._security = security_scanner
        self._policy = policy_engine
        self._partials_dir = partials_dir
        self._policy_id = policy_id

    async def build(self, inp: PromptBuildInput) -> PromptRequest:
        return await self._compose(inp, persist_replay=True, use_cache=True)

    async def preview(self, inp: PromptBuildInput) -> PromptRequest:
        """Render PromptRequest for debugging — no provider calls, no replay."""
        return await self._compose(inp, persist_replay=False, use_cache=False)

    async def _compose(
        self,
        inp: PromptBuildInput,
        *,
        persist_replay: bool,
        use_cache: bool,
    ) -> PromptRequest:
        started = time.perf_counter()
        name = inp.prompt_name or inp.capability
        if inp.prompt_version:
            definition = await self._registry.get_version(name, inp.prompt_version)
        else:
            definition = await self._registry.get_latest(name)
        if definition is None:
            definition = await self._registry.get_latest(inp.capability)
        if definition is None:
            return PromptRequest(
                prompt="",
                capability=inp.capability,
                prompt_version=inp.prompt_version or "",
                correlation_id=inp.correlation_id,
                organization_id=inp.organization_id,
                valid=False,
                errors=(f"prompt not found: {name}",),
            )

        lint_warnings: tuple[str, ...] = ()
        if self._linter is not None:
            lint = self._linter.lint(definition, partials_dir=self._partials_dir)
            lint_warnings = lint.warnings
            if not lint.ok:
                return PromptRequest(
                    prompt="",
                    capability=definition.capability,
                    prompt_version=definition.version,
                    prompt_id=definition.id,
                    correlation_id=inp.correlation_id,
                    organization_id=inp.organization_id,
                    valid=False,
                    errors=lint.errors,
                    metrics={"lint_warnings": list(lint.warnings)},
                    explanation=PromptExplanation(
                        lint_warnings=lint.warnings,
                        policy_id=self._policy_id,
                    ),
                )

        cache_key = None
        if use_cache and self._cache is not None:
            cache_key = _cache_key(definition.id, definition.version, inp)
            cached = await self._cache.get(f"compiled:{cache_key}")
            if cached and cached.get("valid"):
                return _request_from_cache(cached, inp, definition.capability)

        variables = _flatten_variables(inp, definition.schema_id)
        if self._schemas is not None:
            schema_id = inp.schema_id or definition.schema_id
            schema = self._schemas.get(schema_id)
            if schema and schema.instructions and not variables.get("output_format"):
                variables["output_format"] = schema.instructions

        compiled = self._compiler.compile(definition, variables)
        optimized = self._optimizer.optimize(compiled, token_budget=inp.token_budget)
        validation = self._validator.validate(definition, optimized, variables)

        errors: list[str] = list(validation.errors)
        policy_metrics: dict[str, Any] = {}
        policy_id = self._policy_id

        if self._security is not None:
            scan = self._security.scan(
                definition,
                optimized,
                variables,
                partials_dir=self._partials_dir,
            )
            if not scan.safe:
                errors.extend(scan.errors)

        if self._policy is not None:
            policy_result = self._policy.apply(
                definition,
                optimized,
                variables,
                organization_id=inp.organization_id,
                capability=definition.capability,
            )
            policy_id = policy_result.policy_id
            policy_metrics = dict(policy_result.metrics)
            if not policy_result.allowed:
                errors.extend(policy_result.errors)

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        metrics = {
            "compile_ms": elapsed_ms,
            "prompt_size": optimized.token_estimate,
            "version": definition.version,
            "schema_id": optimized.schema_id,
            "prompt_id": definition.id,
            "policy_id": policy_id,
            "lint_warnings": list(lint_warnings),
            **policy_metrics,
        }
        explanation = _build_explanation(
            inp, optimized.variables_used, optimized.sections, policy_id, lint_warnings
        )
        request = PromptRequest(
            prompt=optimized.text,
            capability=definition.capability,
            prompt_version=definition.version,
            prompt_id=definition.id,
            system_message=optimized.system_message,
            response_format=inp.response_format or "json",
            schema_id=inp.schema_id or optimized.schema_id,
            sections=dict(optimized.sections),
            token_estimate=optimized.token_estimate,
            correlation_id=inp.correlation_id,
            organization_id=inp.organization_id,
            metrics=metrics,
            valid=len(errors) == 0,
            errors=tuple(errors),
            explanation=explanation,
        )

        if self._analytics is not None:
            self._analytics.record_build(request)

        if persist_replay and self._replay is not None and request.valid:
            digest = hashlib.sha256(request.prompt.encode()).hexdigest()[:32]
            await self._replay.save(
                PromptReplayRecord(
                    replay_id=str(uuid.uuid4()),
                    prompt_id=request.prompt_id,
                    prompt_version=request.prompt_version,
                    capability=request.capability,
                    compiled_hash=digest,
                    compiled_text=request.prompt,
                    correlation_id=request.correlation_id,
                    organization_id=str(request.organization_id or ""),
                    metadata={"system_message": request.system_message},
                )
            )

        if use_cache and self._cache is not None and cache_key and request.valid:
            await self._cache.set(f"compiled:{cache_key}", request.to_dict())

        return request


def _presence(text: str) -> PromptSectionPresence:
    t = (text or "").strip()
    if not t:
        return PromptSectionPresence(present=False)
    digest = hashlib.sha256(t.encode()).hexdigest()[:12]
    return PromptSectionPresence(present=True, length=len(t), digest=digest)


def _build_explanation(
    inp: PromptBuildInput,
    variables_used: tuple[str, ...],
    sections: dict[str, str],
    policy_id: str,
    lint_warnings: tuple[str, ...],
) -> PromptExplanation:
    knowledge_sources: list[str] = []
    if inp.knowledge_text:
        knowledge_sources.append("optimized_context")
    sources = inp.planner_json.get("knowledge_sources") if inp.planner_json else None
    if isinstance(sources, (list, tuple)):
        knowledge_sources.extend(str(s) for s in sources)
    elif inp.planner_json.get("knowledge_source"):
        knowledge_sources.append(str(inp.planner_json["knowledge_source"]))

    planner_inputs: list[str] = []
    if inp.planner_json:
        planner_inputs.extend(sorted(str(k) for k in inp.planner_json.keys()))
        pv = inp.planner_json.get("prompt_variables")
        if isinstance(pv, dict):
            planner_inputs.extend(f"prompt_variables.{k}" for k in sorted(pv.keys()))

    return PromptExplanation(
        knowledge_sources=tuple(dict.fromkeys(knowledge_sources)),
        planner_inputs=tuple(dict.fromkeys(planner_inputs)),
        rules=_presence(inp.rules_text or sections.get("rules", "")),
        claims=_presence(inp.claims_text or sections.get("claims", "")),
        brand=_presence(inp.brand_text or sections.get("brand", "")),
        examples=_presence(inp.examples_text or sections.get("examples", "")),
        variables_used=tuple(variables_used),
        sections_present=tuple(sorted(sections.keys())),
        policy_id=policy_id,
        lint_warnings=lint_warnings,
    )


def _request_from_cache(
    cached: dict[str, Any], inp: PromptBuildInput, capability: str
) -> PromptRequest:
    from app.modules.prompts.domain.models import PromptExplanation

    expl_raw = cached.get("explanation") or {}
    explanation = PromptExplanation(
        knowledge_sources=tuple(expl_raw.get("knowledge_sources") or ()),
        planner_inputs=tuple(expl_raw.get("planner_inputs") or ()),
        variables_used=tuple(expl_raw.get("variables_used") or ()),
        sections_present=tuple(expl_raw.get("sections_present") or ()),
        policy_id=str(expl_raw.get("policy_id") or "default"),
        lint_warnings=tuple(expl_raw.get("lint_warnings") or ()),
    )
    return PromptRequest(
        prompt=str(cached.get("prompt") or ""),
        capability=str(cached.get("capability") or capability),
        prompt_version=str(cached.get("prompt_version") or ""),
        prompt_id=str(cached.get("prompt_id") or ""),
        system_message=str(cached.get("system_message") or ""),
        response_format=str(cached.get("response_format") or "json"),
        schema_id=str(cached.get("schema_id") or "json"),
        sections=dict(cached.get("sections") or {}),
        token_estimate=int(cached.get("token_estimate") or 0),
        correlation_id=inp.correlation_id,
        organization_id=inp.organization_id,
        metrics=dict(cached.get("metrics") or {}),
        valid=True,
        explanation=explanation,
    )


def _flatten_variables(inp: PromptBuildInput, default_schema: str) -> dict[str, str]:
    vars_out: dict[str, str] = {}
    for key, val in (inp.variables or {}).items():
        if isinstance(val, (dict, list)):
            vars_out[str(key)] = json.dumps(val, default=str)
        else:
            vars_out[str(key)] = "" if val is None else str(val)

    if inp.knowledge_text:
        vars_out.setdefault("knowledge", inp.knowledge_text)
    if inp.brand_text:
        vars_out.setdefault("brand", inp.brand_text)
    if inp.rules_text:
        vars_out.setdefault("rules", inp.rules_text)
    if inp.examples_text:
        vars_out.setdefault("examples", inp.examples_text)
    if inp.claims_text:
        vars_out.setdefault("claims", inp.claims_text)
    if inp.preferences_text:
        vars_out.setdefault("preferences", inp.preferences_text)
    if inp.planner_json:
        vars_out.setdefault("planner", json.dumps(inp.planner_json, default=str))
        pv = inp.planner_json.get("prompt_variables")
        if isinstance(pv, dict):
            for k, v in pv.items():
                if isinstance(v, (dict, list)):
                    vars_out.setdefault(str(k), json.dumps(v, default=str))
                else:
                    vars_out.setdefault(str(k), "" if v is None else str(v))

    vars_out.setdefault("schema_id", inp.schema_id or default_schema)
    return vars_out


def _cache_key(prompt_id: str, version: str, inp: PromptBuildInput) -> str:
    blob = json.dumps(
        {
            "id": prompt_id,
            "version": version,
            "vars": inp.variables,
            "knowledge": inp.knowledge_text,
            "brand": inp.brand_text,
            "rules": inp.rules_text,
            "examples": inp.examples_text,
            "claims": inp.claims_text,
            "preferences": inp.preferences_text,
            "planner": inp.planner_json,
            "budget": inp.token_budget,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:32]
