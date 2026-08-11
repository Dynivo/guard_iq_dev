"""Assemble DraftMetadata from GenerationRequest context (no KE/News calls)."""

from __future__ import annotations

from typing import Any

from app.modules.content.domain.models import DraftMetadata, GenerationRequest, StructuredDraft


def build_draft_metadata(
    draft: StructuredDraft,
    request: GenerationRequest,
    *,
    replay_id: str = "",
    generation_ms: float = 0.0,
) -> DraftMetadata:
    ctx = dict(request.context_metadata or {})
    plan = request.content_plan or {}
    entities = tuple(ctx.get("entities") or ())
    topics = tuple(ctx.get("topics") or ())
    if not topics and plan.get("topic"):
        topics = (str(plan["topic"]),)
    opportunities = tuple(ctx.get("opportunity_types") or ctx.get("opportunities") or ())
    audience = str(ctx.get("audience") or plan.get("audience") or "")
    planner = dict(ctx.get("planner_decisions") or {})
    if not planner and plan:
        planner = {
            "content_type": plan.get("content_type"),
            "format": plan.get("format"),
            "tone": plan.get("tone"),
            "cta": plan.get("cta"),
            "strategy": plan.get("strategy"),
            "confidence": plan.get("confidence"),
        }
    gen_meta: dict[str, Any] = {
        **dict(draft.provider_metadata or {}),
        "latency_ms": generation_ms,
        "replay_id": replay_id,
        "content_plan_id": request.content_plan_id or draft.content_plan_id,
    }
    gen_meta.update(dict(ctx.get("generation_metadata") or {}))
    return DraftMetadata(
        entities=entities,
        topics=topics,
        trend_score=float(ctx.get("trend_score") or 0.0),
        opportunity_types=opportunities,
        audience=audience,
        planner_decisions=planner,
        prompt_version=draft.prompt_version or str(ctx.get("prompt_version") or ""),
        generation_metadata=gen_meta,
    )
