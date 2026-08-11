"""Workflow handlers — plan assembles only; validate uses ContentValidator."""

from __future__ import annotations

import uuid
from typing import Any

from app.modules.content.application.factory import ContentPlannerFactory
from app.modules.content.application.generation.factory import ContentGenerationFactory
from app.modules.content.application.validator import DefaultContentValidator
from app.modules.content.domain.models import (
    ContentPlan,
    GenerationRequest,
    PlannerInput,
    PlannerPolicy,
    StructuredDraft,
)
from app.modules.content.infrastructure.policy_loader import YamlPlannerPolicyLoader
from app.modules.knowledge.domain.models import CitationMap, OptimizedContext
from app.modules.prompts.domain.models import PromptRequest
from app.modules.workflow.domain.models import NodeOutcome, WorkflowContext, WorkflowNode


def _empty_context() -> OptimizedContext:
    return OptimizedContext(
        text="Industry update for professional audience.",
        citations=(),
        citation_map=CitationMap(),
        knowledge_sources=("workflow",),
        items=(),
        token_estimate=20,
        token_budget=4000,
        sections={"knowledge": "Industry update for professional audience."},
        metrics={},
    )


def _context_from_payload(raw: Any) -> OptimizedContext:
    if isinstance(raw, OptimizedContext):
        return raw
    if isinstance(raw, dict):
        return OptimizedContext(
            text=str(raw.get("text") or ""),
            citations=tuple(raw.get("citations") or ()),
            citation_map=CitationMap(),
            knowledge_sources=tuple(raw.get("knowledge_sources") or ()),
            items=(),
            token_estimate=int(raw.get("token_estimate") or 0),
            token_budget=int(raw.get("token_budget") or 4000),
            sections=dict(raw.get("sections") or {}),
            metrics=dict(raw.get("metrics") or {}),
        )
    text = str(raw) if raw else ""
    if text:
        return OptimizedContext(
            text=text,
            sections={"knowledge": text},
            token_estimate=max(1, len(text) // 4),
            token_budget=4000,
        )
    return _empty_context()


def _parse_input(context: WorkflowContext, node: WorkflowNode) -> PlannerInput:
    cfg = node.config or {}
    org_raw = context.organization_id or context.get("organization_id")
    if isinstance(org_raw, str):
        org_id = uuid.UUID(org_raw)
    elif isinstance(org_raw, uuid.UUID):
        org_id = org_raw
    else:
        org_id = uuid.UUID(int=0)

    article_raw = cfg.get("article_id") or context.get("article_id")
    article_id = uuid.UUID(str(article_raw)) if article_raw else None

    optimized = context.get("knowledge.optimized_context_obj")
    if optimized is None:
        optimized = _context_from_payload(
            context.get("knowledge.optimized_context")
            or context.get("optimized_context")
            or context.get("article_summary")
        )

    prev = context.get("previous_post_topics") or cfg.get("previous_post_topics") or []
    relevance = context.get("relevance_score")
    if relevance is None:
        relevance = cfg.get("relevance_score")

    return PlannerInput(
        organization_id=org_id,
        context=optimized
        if isinstance(optimized, OptimizedContext)
        else _context_from_payload(optimized),
        article_id=article_id,
        topic=str(cfg.get("topic") or context.get("topic") or context.get("query_text") or ""),
        industry=str(cfg.get("industry") or context.get("industry") or ""),
        target_audience_hint=str(
            cfg.get("target_audience") or context.get("target_audience") or ""
        ),
        previous_post_topics=tuple(str(x) for x in prev),
        previous_content_types=tuple(
            str(x) for x in (context.get("previous_content_types") or [])
        ),
        previous_ctas=tuple(str(x) for x in (context.get("previous_ctas") or [])),
        previous_audiences=tuple(
            str(x) for x in (context.get("previous_audiences") or [])
        ),
        article_metadata=dict(context.get("article_metadata") or {}),
        correlation_id=context.correlation_id,
        relevance_score=float(relevance) if relevance is not None else None,
        policy_id=str(cfg.get("policy_id") or context.get("policy_id") or "default"),
    )


class ContentStrategyHandler:
    def __init__(self, planner=None) -> None:
        self._planner = planner or ContentPlannerFactory.create_memory()

    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        inp = _parse_input(context, node)
        decision = await self._planner.strategy(inp)
        payload = {
            "content.strategy_decision": {
                "action": decision.action.value,
                "recommended_type": decision.recommended_type.value,
                "format": decision.format.value,
                "confidence": decision.confidence,
                "duplicate_score": decision.duplicate_score,
                "reasons": list(decision.reasons),
                "alternatives": list(decision.alternatives),
                "should_merge_articles": decision.should_merge_articles,
                "metrics": decision.metrics,
            }
        }
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class ContentPlanHandler:
    def __init__(self, planner=None) -> None:
        self._planner = planner or ContentPlannerFactory.create_memory()

    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        inp = _parse_input(context, node)
        plan = await self._planner.plan(inp)  # candidate only — no validation
        payload = {
            "content.plan": plan.to_dict(),
            "content.plan_id": str(plan.id),
            "content.plan_status": plan.status.value,
            "content.explanation": plan.explanation.to_dict(),
        }
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class ContentValidateHandler:
    def __init__(
        self,
        validator: DefaultContentValidator | None = None,
        policy: PlannerPolicy | None = None,
    ) -> None:
        self._validator = validator or DefaultContentValidator()
        self._policy = policy or YamlPlannerPolicyLoader().load("default")

    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        raw = context.get("content.plan")
        if not isinstance(raw, dict):
            payload = {
                "content.plan_valid": False,
                "content.plan_errors": ["missing content.plan"],
            }
            context.update(payload)
            return NodeOutcome(
                success=False, outputs=payload, error_message="missing content.plan"
            )

        plan = ContentPlan.from_dict(raw)
        result = self._validator.validate(plan, self._policy)
        payload = {
            "content.plan_valid": result.valid,
            "content.plan_errors": list(result.errors),
        }
        context.update(payload)
        return NodeOutcome(
            success=result.valid,
            outputs=payload,
            error_message=None if result.valid else "; ".join(result.errors),
        )


def _prompt_from_context(context: WorkflowContext) -> PromptRequest | None:
    raw = context.get("prompt.request") or context.get("prompt_request")
    if isinstance(raw, PromptRequest):
        return raw
    if isinstance(raw, dict) and raw.get("prompt"):
        return PromptRequest(
            prompt=str(raw.get("prompt") or ""),
            capability=str(raw.get("capability") or "writing"),
            prompt_version=str(raw.get("prompt_version") or "1.0"),
            prompt_id=str(raw.get("prompt_id") or ""),
            system_message=str(raw.get("system_message") or ""),
            response_format=str(raw.get("response_format") or "json"),
            schema_id=str(raw.get("schema_id") or "json"),
            correlation_id=str(raw.get("correlation_id") or context.correlation_id or ""),
            valid=bool(raw.get("valid", True)),
            errors=tuple(raw.get("errors") or ()),
        )
    # Synthesize from plan + knowledge when Prompt Builder already ran upstream
    plan = context.get("content.plan") or {}
    knowledge = context.get("knowledge.optimized_context") or context.get("article_summary") or ""
    if isinstance(knowledge, dict):
        knowledge = knowledge.get("text") or ""
    topic = plan.get("topic") if isinstance(plan, dict) else ""
    prompt = (
        f"Write a LinkedIn post.\nTopic: {topic}\nContext:\n{knowledge}\n"
        'Respond as JSON with hook, body, cta, hashtags.'
    )
    if topic or knowledge:
        return PromptRequest(
            prompt=prompt,
            capability="writing",
            prompt_version="workflow-1.0",
            response_format="json",
            schema_id="json",
            correlation_id=context.correlation_id or "",
            valid=True,
        )
    return None


class ContentGenerateHandler:
    def __init__(self, engine=None) -> None:
        self._engine = engine or ContentGenerationFactory.create_memory()

    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        pr = _prompt_from_context(context)
        if pr is None:
            payload = {"content.generation_ok": False, "content.errors": ["missing PromptRequest"]}
            context.update(payload)
            return NodeOutcome(success=False, outputs=payload, error_message="missing PromptRequest")

        plan = context.get("content.plan") or {}
        plan_id = ""
        content_type = "single_post"
        fmt = "single"
        tone = "professional"
        if isinstance(plan, dict):
            plan_id = str(plan.get("id") or "")
            content_type = str(plan.get("content_type") or content_type)
            fmt = str(plan.get("format") or fmt)
            tone = str(plan.get("tone") or tone)

        source = context.get("article_summary") or ""
        if isinstance(source, dict):
            source = str(source.get("text") or "")
        kc = context.get("knowledge.optimized_context")
        if isinstance(kc, dict) and not source:
            source = str(kc.get("text") or "")

        result = await self._engine.generate(
            GenerationRequest(
                prompt_request=pr,
                content_plan_id=plan_id,
                content_plan=plan if isinstance(plan, dict) else {},
                source_text=str(source),
                correlation_id=context.correlation_id or "",
                expected_tone=tone,
                content_type=content_type,
                format=fmt,
            )
        )
        payload = {
            "content.generation_ok": result.success,
            "content.generation_result": result.to_dict(),
            "content.draft": result.draft.to_dict() if result.draft else None,
            "content.raw_hidden": True,
            "content.errors": list(result.errors),
            "content.replay_id": result.replay_id,
            "content.metrics": result.metrics,
        }
        context.update(payload)
        return NodeOutcome(
            success=result.success,
            outputs=payload,
            error_message=None if result.success else "; ".join(result.errors),
        )


class ContentValidateDraftHandler:
    def __init__(self, engine=None) -> None:
        self._engine = engine or ContentGenerationFactory.create_memory()

    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        raw = context.get("content.draft")
        gen = context.get("content.generation_result") or {}
        validation = gen.get("validation") if isinstance(gen, dict) else None
        if validation is None and isinstance(raw, dict):
            # Re-validate from stored draft
            draft = StructuredDraft.from_dict(raw)
            from app.modules.content.application.generation.policy_loader import (
                load_generation_policy,
            )

            policy = load_generation_policy()
            v = self._engine._content_v.validate(draft, policy)  # noqa: SLF001
            validation = v.to_dict()
            ok = v.valid
        else:
            ok = bool(validation.get("valid")) if isinstance(validation, dict) else bool(
                context.get("content.generation_ok")
            )
        payload = {
            "content.draft_valid": ok,
            "content.draft_validation": validation or {},
        }
        context.update(payload)
        return NodeOutcome(
            success=ok,
            outputs=payload,
            error_message=None if ok else "draft validation failed",
        )


class ContentFormatHandler:
    def __init__(self, engine=None) -> None:
        self._engine = engine or ContentGenerationFactory.create_memory()

    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        raw = context.get("content.draft")
        if not isinstance(raw, dict):
            payload = {"content.format_ok": False}
            context.update(payload)
            return NodeOutcome(success=False, outputs=payload, error_message="missing draft")
        draft = StructuredDraft.from_dict(raw)
        formatted = self._engine._formatter.format(draft, platform="linkedin")  # noqa: SLF001
        payload = {
            "content.format_ok": True,
            "content.draft": formatted.to_dict(),
            "content.markdown": formatted.markdown,
        }
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class ContentFinalizeHandler:
    def __init__(self, engine=None) -> None:
        self._engine = engine or ContentGenerationFactory.create_memory()

    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        raw = context.get("content.draft")
        if not isinstance(raw, dict):
            payload = {"content.finalized": False}
            context.update(payload)
            return NodeOutcome(success=False, outputs=payload, error_message="missing draft")
        if context.get("content.draft_valid") is False:
            payload = {"content.finalized": False, "content.errors": ["draft not valid"]}
            context.update(payload)
            return NodeOutcome(success=False, outputs=payload, error_message="draft not valid")
        draft = StructuredDraft.from_dict(raw)
        from app.modules.content.domain.models import DraftLifecycleStatus

        finalized = self._engine.lifecycle.transition(draft, DraftLifecycleStatus.FINALIZED.value)
        payload = {
            "content.finalized": True,
            "content.draft": finalized.to_dict(),
            "content.ready_for_review": True,
        }
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


def register_content_handlers(node_registry, planner=None, generation_engine=None) -> None:
    pl = planner or ContentPlannerFactory.create_memory()
    node_registry.register("content.strategy", ContentStrategyHandler(pl))
    node_registry.register("content.plan", ContentPlanHandler(pl))
    node_registry.register("content.validate", ContentValidateHandler())
    eng = generation_engine
    node_registry.register("content.generate", ContentGenerateHandler(eng))
    node_registry.register("content.validate_draft", ContentValidateDraftHandler(eng))
    node_registry.register("content.format", ContentFormatHandler(eng))
    node_registry.register("content.finalize", ContentFinalizeHandler(eng))
