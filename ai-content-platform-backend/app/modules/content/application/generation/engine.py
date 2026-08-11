"""Content Generation Engine — PromptRequest → Orchestrator → validated StructuredDraft."""

from __future__ import annotations

import time
import uuid
from dataclasses import replace
from typing import Any

from app.modules.ai.domain.models import OrchestratorRequest, OrchestratorResult
from app.modules.ai.domain.ports import AIOrchestrator
from app.modules.consensus.domain.ports import ConsensusEngine
from app.modules.content.application.generation.brand_validator import DefaultBrandValidator
from app.modules.content.application.generation.content_validator import (
    DefaultContentDraftValidator,
)
from app.modules.content.application.generation.diff import DefaultDraftDiffService
from app.modules.content.application.generation.fact_validator import DefaultFactValidator
from app.modules.content.application.generation.formatter import DefaultContentFormatter
from app.modules.content.application.generation.grammar_validator import DefaultGrammarValidator
from app.modules.content.application.generation.lifecycle import InMemoryDraftLifecycleStore
from app.modules.content.application.generation.metadata import build_draft_metadata
from app.modules.content.application.generation.metrics import GenerationMetricsRecorder
from app.modules.content.application.generation.parser import DefaultOutputParser
from app.modules.content.application.generation.policy_loader import load_generation_policy
from app.modules.content.application.generation.quality import DefaultQualityBreakdownBuilder
from app.modules.content.application.generation.replay import InMemoryGenerationReplayStore
from app.modules.content.application.generation.safety import DefaultContentSafetyValidator
from app.modules.content.application.generation.tone_validator import DefaultToneValidator
from app.modules.content.application.generation.visual_brief import DefaultVisualBriefGenerator
from app.modules.content.domain.models import (
    ContentFormat,
    ContentSafetyResult,
    DraftLifecycleStatus,
    DraftSlide,
    DraftValidationResult,
    DraftVersionSnapshot,
    GenerationPolicy,
    GenerationReplayRecord,
    GenerationRequest,
    GenerationResult,
    QualityBreakdown,
    RawAIOutput,
    StructuredDraft,
    VisualBrief,
)
from app.modules.prompts.domain.models import PromptRequest
from app.shared.ai_types import CompletionResult


class FakeOrchestrator:
    """CI / unit-test orchestrator returning fixture JSON."""

    def __init__(self, response_text: str | None = None) -> None:
        self._text = response_text or (
            '{"hook":"Protect your organisation with clear DSPT guidance.",'
            '"body":"Healthcare teams need practical compliance steps that reduce risk '
            "and build trust with patients and regulators. Start with inventory, "
            'access controls, and staff training.",'
            '"cta":"Comment with your biggest DSPT challenge.",'
            '"hashtags":["DSPT","CyberSecurity","Healthcare"]}'
        )
        self.calls: list[OrchestratorRequest] = []

    async def execute(self, request: OrchestratorRequest) -> OrchestratorResult:
        self.calls.append(request)
        return OrchestratorResult(
            success=True,
            result=CompletionResult(text=self._text, provider="fake", model="fixture"),
            capability=request.capability,
            provider="fake",
            model="fixture",
        )

    async def complete(self, capability: str, prompt: str, **overrides: Any) -> CompletionResult:
        req = OrchestratorRequest(capability=capability, prompt=prompt)
        out = await self.execute(req)
        assert out.result is not None
        return out.result

    async def execute_stream(self, request: OrchestratorRequest):
        yield  # pragma: no cover

    async def execute_many(self, requests: list[OrchestratorRequest]) -> list[OrchestratorResult]:
        return [await self.execute(r) for r in requests]


class DefaultContentGenerationEngine:
    """Transforms PromptRequest into StructuredDraft. Never builds prompts or chooses providers."""

    def __init__(
        self,
        orchestrator: AIOrchestrator,
        *,
        policy: GenerationPolicy | None = None,
        parser: DefaultOutputParser | None = None,
        content_validator: DefaultContentDraftValidator | None = None,
        fact_validator: DefaultFactValidator | None = None,
        brand_validator: DefaultBrandValidator | None = None,
        tone_validator: DefaultToneValidator | None = None,
        grammar_validator: DefaultGrammarValidator | None = None,
        formatter: DefaultContentFormatter | None = None,
        lifecycle: InMemoryDraftLifecycleStore | None = None,
        replay: InMemoryGenerationReplayStore | None = None,
        metrics: GenerationMetricsRecorder | None = None,
        diff: DefaultDraftDiffService | None = None,
        safety: DefaultContentSafetyValidator | None = None,
        quality_builder: DefaultQualityBreakdownBuilder | None = None,
        visual_brief: DefaultVisualBriefGenerator | None = None,
        consensus_engine: ConsensusEngine | None = None,
    ) -> None:
        self._orch = orchestrator
        self._policy = policy or load_generation_policy()
        self._parser = parser or DefaultOutputParser()
        self._content_v = content_validator or DefaultContentDraftValidator()
        self._fact_v = fact_validator or DefaultFactValidator()
        self._brand_v = brand_validator or DefaultBrandValidator()
        self._tone_v = tone_validator or DefaultToneValidator()
        self._grammar_v = grammar_validator or DefaultGrammarValidator()
        self._formatter = formatter or DefaultContentFormatter()
        self._lifecycle = lifecycle or InMemoryDraftLifecycleStore()
        self._replay = replay or InMemoryGenerationReplayStore()
        self._metrics = metrics or GenerationMetricsRecorder()
        self._diff = diff or DefaultDraftDiffService()
        self._safety = safety or DefaultContentSafetyValidator()
        self._quality = quality_builder or DefaultQualityBreakdownBuilder()
        self._visual = visual_brief or DefaultVisualBriefGenerator()
        self._consensus = consensus_engine

    @property
    def lifecycle(self) -> InMemoryDraftLifecycleStore:
        return self._lifecycle

    @property
    def replay_store(self) -> InMemoryGenerationReplayStore:
        return self._replay

    @property
    def metrics(self) -> GenerationMetricsRecorder:
        return self._metrics

    @property
    def diff_service(self) -> DefaultDraftDiffService:
        return self._diff

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        pr = request.prompt_request
        if pr is None:
            return GenerationResult(success=False, errors=("missing PromptRequest",))
        if not isinstance(pr, PromptRequest):
            return GenerationResult(success=False, errors=("invalid PromptRequest type",))
        if not getattr(pr, "valid", True):
            return GenerationResult(
                success=False,
                errors=tuple(getattr(pr, "errors", ()) or ("PromptRequest invalid",)),
            )
        if not (pr.prompt or "").strip():
            return GenerationResult(success=False, errors=("PromptRequest.prompt empty",))

        started = time.perf_counter()
        orch_req = OrchestratorRequest(
            capability=pr.capability or "writing",
            prompt=pr.prompt,
            organization_id=request.organization_id or pr.organization_id,
            correlation_id=request.correlation_id or pr.correlation_id,
            system_message=pr.system_message,
            response_format=pr.response_format or "json",
            prompt_version=pr.prompt_version,
            metadata={
                "prompt_id": pr.prompt_id,
                "schema_id": pr.schema_id,
                "content_plan_id": request.content_plan_id,
            },
        )

        from app.core.config import get_settings

        settings = get_settings()
        use_consensus = bool(self._consensus) and bool(settings.CONSENSUS_ENABLED)
        opt_in = True
        if use_consensus:
            try:
                from app.modules.consensus.application.config_loader import load_consensus_config
                from app.modules.providers.domain.models import normalize_capability

                caps = (load_consensus_config().get("providers") or {}).get(
                    "opt_in_capabilities"
                ) or []
                raw_cap = (pr.capability or "writing").strip()
                canon = normalize_capability(raw_cap)
                # Match either raw (writing_from_plan) or normalized (writing)
                if caps and raw_cap not in caps and canon not in caps:
                    opt_in = False
            except Exception:  # noqa: BLE001
                opt_in = True

        if use_consensus and opt_in:
            from app.modules.consensus.domain.models import ConsensusRequest

            consensus_out = await self._consensus.run(  # type: ignore[union-attr]
                ConsensusRequest.from_prompt_fields(
                    prompt=pr.prompt,
                    capability=pr.capability or "writing",
                    system_message=pr.system_message,
                    organization_id=request.organization_id or pr.organization_id,
                    correlation_id=request.correlation_id or pr.correlation_id,
                    response_format=pr.response_format or "json",
                    prompt_version=pr.prompt_version,
                    policy_id=settings.CONSENSUS_POLICY,
                    metadata=dict(orch_req.metadata),
                )
            )
            gen_ms = (time.perf_counter() - started) * 1000
            self._metrics.record_generation(gen_ms)
            if not consensus_out.success:
                return GenerationResult(
                    success=False,
                    errors=(consensus_out.error or "consensus failed",),
                    metrics={"generation_time_ms": gen_ms, "consensus": True},
                )
            orch_result = OrchestratorResult(
                success=True,
                result=CompletionResult(
                    text=consensus_out.final_text,
                    provider=consensus_out.provider,
                    model=consensus_out.model,
                    latency_ms=int(gen_ms),
                ),
                capability=pr.capability or "writing",
                provider=consensus_out.provider,
                model=consensus_out.model,
                metrics={
                    "consensus_run_id": consensus_out.run.run_id,
                    "consensus_report": consensus_out.run.to_report(),
                },
            )
        else:
            orch_result = await self._orch.execute(orch_req)
            gen_ms = (time.perf_counter() - started) * 1000
            self._metrics.record_generation(gen_ms)

        if not orch_result.success or orch_result.result is None:
            return GenerationResult(
                success=False,
                errors=(orch_result.error_message or "orchestrator failed",),
                metrics={"generation_time_ms": gen_ms},
            )

        raw = RawAIOutput(
            text=orch_result.result.text or "",
            response_format=pr.response_format or "json",
            provider=orch_result.provider or getattr(orch_result.result, "provider", ""),
            model=orch_result.model or getattr(orch_result.result, "model", ""),
            latency_ms=gen_ms,
            metadata=dict(orch_result.metrics or {}),
        )

        candidate = self._parser.parse(
            raw, content_type=request.content_type, format=request.format
        )
        candidate = _ensure_carousel_slides(candidate, request)
        candidate = _repair_draft_fields(candidate, request)
        candidate = replace(
            candidate,
            content_plan_id=request.content_plan_id,
            prompt_version=pr.prompt_version,
            provider_metadata={
                "provider": raw.provider,
                "model": raw.model,
                "capability": pr.capability,
            },
            lifecycle_status=DraftLifecycleStatus.GENERATED.value,
        )

        v_started = time.perf_counter()
        validation = self._run_validators(candidate, request)
        safety = self._safety.validate(candidate, source_text=request.source_text)
        quality = self._quality.build(
            candidate, validation, source_text=request.source_text
        )
        val_ms = (time.perf_counter() - v_started) * 1000
        self._metrics.record_validation(val_ms)

        scores = quality.to_dict()
        composite = quality.composite()
        confidence = min(1.0, composite)

        reject_errors = list(validation.errors)
        if not safety.safe:
            reject_errors.extend(safety.reasons or ("content safety failed",))

        if (
            not validation.valid
            or not safety.safe
            or composite < self._policy.min_quality_score
        ):
            rejected = replace(
                candidate,
                lifecycle_status=DraftLifecycleStatus.REJECTED.value,
                quality_score=composite,
                confidence_score=round(confidence, 4),
                grammar_score=quality.grammar,
                brand_score=quality.brand,
                fact_score=quality.fact,
                tone_score=quality.tone,
                readability_score=quality.readability,
                quality=quality,
                safety=safety,
            )
            self._metrics.record_outcome(accepted=False, scores=scores)
            return GenerationResult(
                success=False,
                draft=rejected,
                validation=validation,
                raw=raw,
                errors=tuple(reject_errors) or ("validation failed",),
                metrics={
                    "generation_time_ms": gen_ms,
                    "validation_time_ms": val_ms,
                    **self._metrics.snapshot(),
                },
                quality=quality,
                safety=safety,
            )

        validated = self._lifecycle.transition(
            replace(
                candidate,
                quality_score=composite,
                confidence_score=round(confidence, 4),
                grammar_score=quality.grammar,
                brand_score=quality.brand,
                fact_score=quality.fact,
                tone_score=quality.tone,
                readability_score=quality.readability,
                quality=quality,
                safety=safety,
            ),
            DraftLifecycleStatus.VALIDATED.value,
        )
        formatted = self._formatter.format(validated, platform="linkedin")
        brief = self._visual.generate(formatted, content_plan=request.content_plan)
        md = {
            **formatted.metadata,
            "visual_brief": brief.to_dict(),
            "image_brief": brief.to_dict(),  # forward-compat alias for M10
            "quality": quality.to_dict(),
            "safety": safety.to_dict(),
        }
        with_brief = replace(
            formatted,
            visual_brief=brief,
            metadata=md,
        )

        draft_id = str(uuid.uuid4())
        replay_id = str(uuid.uuid4())
        draft_meta = build_draft_metadata(
            with_brief,
            request,
            replay_id=replay_id,
            generation_ms=gen_ms,
        )
        finalized = self._lifecycle.transition(
            replace(
                with_brief,
                draft_metadata=draft_meta,
                metadata={
                    **with_brief.metadata,
                    "draft_id": draft_id,
                    "draft_metadata": draft_meta.to_dict(),
                },
            ),
            DraftLifecycleStatus.FINALIZED.value,
        )
        self._lifecycle.save_version(
            DraftVersionSnapshot(
                draft_id=draft_id,
                version=1,
                text=finalized.markdown or finalized.body,
                draft_json=finalized.to_dict(),
                change_summary="initial generation",
            )
        )

        pr_json = pr.to_dict() if hasattr(pr, "to_dict") else {"prompt": pr.prompt}
        self._replay.save(
            GenerationReplayRecord(
                replay_id=replay_id,
                prompt_request_json=pr_json,
                raw_output=raw.text,
                draft_json=finalized.to_dict(),
                metrics={"generation_time_ms": gen_ms, "validation_time_ms": val_ms},
                draft_id=draft_id,
                correlation_id=request.correlation_id or pr.correlation_id,
            )
        )
        self._metrics.record_outcome(accepted=True, scores=scores)
        return GenerationResult(
            success=True,
            draft=finalized,
            validation=validation,
            raw=raw,
            replay_id=replay_id,
            metrics={
                "generation_time_ms": gen_ms,
                "validation_time_ms": val_ms,
                **self._metrics.snapshot(),
            },
            quality=quality,
            safety=safety,
        )

    def enrich_draft(
        self, draft: StructuredDraft, request: GenerationRequest
    ) -> StructuredDraft:
        """Re-run safety/quality/visual/metadata on an existing draft (regen path)."""
        validation = self._run_validators(draft, request)
        safety = self._safety.validate(draft, source_text=request.source_text)
        quality = self._quality.build(draft, validation, source_text=request.source_text)
        formatted = self._formatter.format(draft, platform="linkedin")
        brief = self._visual.generate(formatted, content_plan=request.content_plan)
        draft_meta = build_draft_metadata(formatted, request)
        return replace(
            formatted,
            quality_score=quality.composite(),
            grammar_score=quality.grammar,
            brand_score=quality.brand,
            fact_score=quality.fact,
            tone_score=quality.tone,
            readability_score=quality.readability,
            quality=quality,
            safety=safety,
            visual_brief=brief,
            draft_metadata=draft_meta,
            metadata={
                **formatted.metadata,
                "visual_brief": brief.to_dict(),
                "image_brief": brief.to_dict(),
                "quality": quality.to_dict(),
                "safety": safety.to_dict(),
                "draft_metadata": draft_meta.to_dict(),
            },
        )

    def _run_validators(
        self, draft: StructuredDraft, request: GenerationRequest
    ) -> DraftValidationResult:
        c = self._content_v.validate(draft, self._policy)
        f = self._fact_v.validate(draft, source_text=request.source_text)
        b = self._brand_v.validate(
            draft, policy=self._policy, preferences=request.brand_preferences
        )
        t = self._tone_v.validate(
            draft,
            expected_tone=request.expected_tone,
            profiles=self._policy.tone_profiles,
        )
        g = self._grammar_v.validate(draft, self._policy)
        errors = c.errors + f.errors + b.errors + t.errors + g.errors
        return DraftValidationResult(
            valid=c.valid and f.valid and b.valid and t.valid and g.valid,
            errors=errors,
            content_score=c.content_score,
            fact_score=f.fact_score,
            brand_score=b.brand_score,
            tone_score=t.tone_score,
            grammar_score=g.grammar_score,
            readability_score=g.readability_score,
        )


def _repair_draft_fields(
    draft: StructuredDraft, request: GenerationRequest
) -> StructuredDraft:
    """Fill missing CTA / hashtags so a good LLM body is not rejected on soft fields.

    Models sometimes omit ``cta`` even when the prompt asks for JSON with all keys.
    Prefer extracting a trailing question from the body, then fall back to plan CTA.
    """
    cta = (draft.cta or "").strip()
    hashtags = list(draft.hashtags or ())
    meta = dict(draft.metadata or {})
    repaired: list[str] = []

    if not cta:
        # Last non-empty body paragraph that looks like an engagement ask
        for para in reversed([p.strip() for p in (draft.body or "").split("\n\n") if p.strip()]):
            if "?" in para and len(para) <= 280:
                cta = para
                repaired.append("cta_from_body")
                break
    if not cta and isinstance(request.content_plan, dict):
        plan_cta = str(
            request.content_plan.get("cta_strategy")
            or request.content_plan.get("cta")
            or ""
        ).strip()
        if plan_cta and plan_cta.lower() not in {"n/a", "none", "comment"}:
            # Prefer human-readable strategy text over enum slug
            if len(plan_cta) > 12 and " " in plan_cta:
                cta = plan_cta
            else:
                cta = "What do you think — worth a closer look for your team?"
            repaired.append("cta_from_plan")
    if not cta:
        cta = "What’s your take — have you seen this play out in your org?"
        repaired.append("cta_default")

    if not hashtags:
        hashtags = ["#cybersecurity", "#LinkedIn", "#infosec"]
        repaired.append("hashtags_default")

    if not repaired:
        return draft
    meta["repaired_fields"] = repaired
    return replace(draft, cta=cta, hashtags=tuple(hashtags), metadata=meta)


def _ensure_carousel_slides(
    draft: StructuredDraft, request: GenerationRequest
) -> StructuredDraft:
    """When plan expects carousel but model omitted slides, lift from plan outline."""
    fmt = request.format or draft.format
    if fmt != ContentFormat.CAROUSEL.value:
        return draft if draft.format != ContentFormat.CAROUSEL.value else draft
    if draft.slides:
        return replace(draft, format=ContentFormat.CAROUSEL.value)
    outline = []
    if isinstance(request.content_plan, dict):
        outline = list(request.content_plan.get("slide_outline") or [])
        car = request.content_plan.get("carousel") or {}
        if not outline and isinstance(car, dict):
            outline = list(car.get("slides") or [])
    slides: list[DraftSlide] = []
    for i, s in enumerate(outline):
        if not isinstance(s, dict):
            continue
        title = str(s.get("title") or f"Slide {i + 1}")
        body = str(s.get("purpose") or "")
        points = s.get("key_points") or []
        if points:
            body = (body + "\n" if body else "") + "\n".join(f"- {p}" for p in points)
        slides.append(DraftSlide(index=int(s.get("index", i + 1)), title=title, body=body))
    if not slides and draft.body:
        # Split body into chunks as a last resort
        parts = [p.strip() for p in draft.body.split("\n\n") if p.strip()]
        for i, part in enumerate(parts[:8] or [draft.body]):
            slides.append(DraftSlide(index=i + 1, title=draft.hook or f"Slide {i + 1}", body=part))
    if not slides:
        return replace(draft, format=ContentFormat.CAROUSEL.value)
    return replace(
        draft,
        format=ContentFormat.CAROUSEL.value,
        slides=tuple(slides),
        metadata={**draft.metadata, "slides_from_plan": True},
    )
