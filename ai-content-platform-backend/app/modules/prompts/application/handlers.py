"""Workflow handlers for Prompt Builder (M7)."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from app.modules.prompts.application.evaluator import DefaultPromptEvaluator, load_eval_cases
from app.modules.prompts.application.factory import PromptBuilderFactory
from app.modules.prompts.domain.models import PromptBuildInput
from app.modules.workflow.domain.models import NodeOutcome, WorkflowContext, WorkflowNode

_EVAL_DIR = Path(__file__).resolve().parents[4] / "configs" / "prompts" / "eval"


def _org_id(context: WorkflowContext) -> uuid.UUID | None:
    raw = context.organization_id or context.get("organization_id")
    if isinstance(raw, uuid.UUID):
        return raw
    if isinstance(raw, str) and raw:
        try:
            return uuid.UUID(raw)
        except ValueError:
            return None
    return None


def _build_input(context: WorkflowContext, node: WorkflowNode) -> PromptBuildInput:
    cfg = node.config or {}
    plan = context.get("content.plan")
    planner_json = plan if isinstance(plan, dict) else {}
    knowledge = (
        context.get("knowledge.optimized_context")
        or context.get("optimized_context")
        or {}
    )
    knowledge_text = ""
    if isinstance(knowledge, dict):
        knowledge_text = str(knowledge.get("text") or "")
        sections = knowledge.get("sections") or {}
        if isinstance(sections, dict) and sections.get("knowledge"):
            knowledge_text = str(sections.get("knowledge") or knowledge_text)
    elif isinstance(knowledge, str):
        knowledge_text = knowledge

    prompt_vars = {}
    if isinstance(planner_json.get("prompt_variables"), dict):
        prompt_vars = dict(planner_json["prompt_variables"])

    capability = str(
        cfg.get("capability")
        or context.get("prompt.capability")
        or "writing_from_plan"
    )
    return PromptBuildInput(
        capability=capability,
        prompt_name=str(cfg.get("prompt_name") or capability),
        prompt_version=cfg.get("prompt_version") or context.get("prompt.version"),
        organization_id=_org_id(context),
        correlation_id=context.correlation_id,
        variables={**prompt_vars, **dict(cfg.get("variables") or {})},
        knowledge_text=knowledge_text or str(context.get("knowledge_text") or ""),
        brand_text=str(context.get("brand_text") or cfg.get("brand_text") or ""),
        rules_text=str(context.get("rules_text") or cfg.get("rules_text") or ""),
        examples_text=str(
            context.get("examples_text") or cfg.get("examples_text") or ""
        ),
        claims_text=str(context.get("claims_text") or ""),
        preferences_text=str(context.get("preferences_text") or ""),
        planner_json=planner_json,
        token_budget=int(cfg.get("token_budget") or context.get("token_budget") or 6000),
        response_format=str(cfg.get("response_format") or "json"),
        schema_id=str(cfg.get("schema_id") or ""),
    )


class PromptPrepareHandler:
    def __init__(self, builder=None) -> None:
        self._builder = builder or PromptBuilderFactory.create_memory()

    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        inp = _build_input(context, node)
        request = await self._builder.build(inp)
        payload = {
            "prompt.request": request.to_dict(),
            "prompt.valid": request.valid,
            "prompt.version": request.prompt_version,
            "prompt.id": request.prompt_id,
            "prompt.text": request.prompt,
            "prompt.system_message": request.system_message,
            "prompt.errors": list(request.errors),
        }
        context.update(payload)
        return NodeOutcome(
            success=request.valid,
            outputs=payload,
            error_message=None if request.valid else "; ".join(request.errors),
        )


class PromptCompileHandler:
    """Compile-only path — same as prepare for M7 (full pipeline)."""

    def __init__(self, builder=None) -> None:
        self._builder = builder or PromptBuilderFactory.create_memory()

    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        # Prefer re-using prepare if already present
        existing = context.get("prompt.request")
        if isinstance(existing, dict) and existing.get("prompt"):
            payload = {
                "prompt.compiled": existing.get("prompt"),
                "prompt.token_estimate": existing.get("token_estimate"),
            }
            context.update(payload)
            return NodeOutcome(success=True, outputs=payload)

        handler = PromptPrepareHandler(self._builder)
        outcome = await handler.execute(node, context)
        if outcome.success:
            req = context.get("prompt.request") or {}
            extra = {
                "prompt.compiled": req.get("prompt") if isinstance(req, dict) else "",
                "prompt.token_estimate": req.get("token_estimate")
                if isinstance(req, dict)
                else 0,
            }
            context.update(extra)
            outcome.outputs.update(extra)
        return outcome


class PromptValidateHandler:
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        req = context.get("prompt.request")
        if not isinstance(req, dict):
            payload = {
                "prompt.valid": False,
                "prompt.errors": ["missing prompt.request"],
            }
            context.update(payload)
            return NodeOutcome(
                success=False, outputs=payload, error_message="missing prompt.request"
            )
        valid = bool(req.get("valid", False))
        errors = list(req.get("errors") or [])
        payload = {"prompt.valid": valid, "prompt.errors": errors}
        context.update(payload)
        return NodeOutcome(
            success=valid,
            outputs=payload,
            error_message=None if valid else "; ".join(str(e) for e in errors),
        )


class PromptEvaluateHandler:
    def __init__(self, builder=None, evaluator: DefaultPromptEvaluator | None = None) -> None:
        self._builder = builder or PromptBuilderFactory.create_memory()
        self._evaluator = evaluator or DefaultPromptEvaluator()

    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        cfg = node.config or {}
        suite = str(cfg.get("suite") or "writing_from_plan_golden.yaml")
        cases = load_eval_cases(_EVAL_DIR / suite)
        if not cases:
            # Evaluate current request heuristically
            req_raw = context.get("prompt.request")
            if isinstance(req_raw, dict) and req_raw.get("prompt"):
                from app.modules.prompts.domain.models import EvalCase, PromptRequest

                request = PromptRequest(
                    prompt=str(req_raw.get("prompt") or ""),
                    capability=str(req_raw.get("capability") or ""),
                    prompt_version=str(req_raw.get("prompt_version") or ""),
                    prompt_id=str(req_raw.get("prompt_id") or ""),
                    system_message=str(req_raw.get("system_message") or ""),
                    sections=dict(req_raw.get("sections") or {}),
                    valid=bool(req_raw.get("valid", True)),
                    errors=tuple(req_raw.get("errors") or ()),
                )
                case = EvalCase(
                    case_id="inline",
                    prompt_name=request.capability,
                    prompt_version=request.prompt_version,
                    variables={},
                    expected_contains=tuple(
                        str(x) for x in (cfg.get("expected_contains") or ["TASK"])
                    ),
                )
                result = await self._evaluator.run_case(case, request)
                payload = {
                    "prompt.eval_results": [
                        {
                            "case_id": result.case_id,
                            "passed": result.passed,
                            "score": result.score,
                            "details": result.details,
                        }
                    ],
                    "prompt.eval_pass_rate": 1.0 if result.passed else 0.0,
                }
                context.update(payload)
                return NodeOutcome(success=result.passed, outputs=payload)

            payload = {"prompt.eval_results": [], "prompt.eval_pass_rate": 0.0}
            context.update(payload)
            return NodeOutcome(
                success=False, outputs=payload, error_message="no eval cases"
            )

        results = await self._evaluator.run_suite(cases, self._builder)
        passed = sum(1 for r in results if r.passed)
        rate = passed / len(results) if results else 0.0
        payload = {
            "prompt.eval_results": [
                {
                    "case_id": r.case_id,
                    "passed": r.passed,
                    "score": r.score,
                    "details": r.details,
                    "prompt_version": r.prompt_version,
                }
                for r in results
            ],
            "prompt.eval_pass_rate": rate,
        }
        context.update(payload)
        return NodeOutcome(success=rate >= 1.0, outputs=payload)


def register_prompt_handlers(node_registry, builder=None) -> None:
    b = builder or PromptBuilderFactory.create_memory()
    node_registry.register("prompt.prepare", PromptPrepareHandler(b))
    node_registry.register("prompt.compile", PromptCompileHandler(b))
    node_registry.register("prompt.validate", PromptValidateHandler())
    node_registry.register("prompt.evaluate", PromptEvaluateHandler(b))
