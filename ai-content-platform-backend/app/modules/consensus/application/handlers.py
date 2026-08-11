"""Consensus workflow node handlers — thin wrappers over ConsensusEngine."""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.modules.consensus.application.factory import ConsensusEngineFactory
from app.modules.consensus.domain.models import ConsensusRequest
from app.modules.workflow.domain.models import NodeOutcome

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = ConsensusEngineFactory.create()
    return _engine


class ConsensusGenerateHandler:
    async def execute(self, node: Any, context: dict[str, Any]) -> NodeOutcome:
        prompt = str(context.get("prompt") or context.get("prompt_text") or "")
        if not prompt.strip():
            return NodeOutcome(success=False, error_message="missing prompt for consensus.generate")
        settings = get_settings()
        req = ConsensusRequest.from_prompt_fields(
            prompt=prompt,
            capability=str(context.get("capability") or "writing"),
            system_message=str(context.get("system_message") or ""),
            correlation_id=str(context.get("correlation_id") or ""),
            response_format=str(context.get("response_format") or "json"),
            policy_id=str(context.get("policy_id") or settings.CONSENSUS_POLICY),
        )
        result = await _get_engine().run(req)
        context["consensus_run_id"] = result.run.run_id
        context["consensus_result"] = result
        context["consensus_report"] = result.run.to_report()
        context["draft_text"] = result.final_text
        return NodeOutcome(success=result.success, error_message=result.error or None)


class ConsensusEvaluateHandler:
    async def execute(self, node: Any, context: dict[str, Any]) -> NodeOutcome:
        result = context.get("consensus_result")
        if result is None:
            return NodeOutcome(success=False, error_message="consensus_result missing")
        context["consensus_evaluations"] = [
            {"candidate_id": e.candidate_id, "composite": e.composite}
            for e in result.run.evaluations
        ]
        return NodeOutcome(success=True)


class ConsensusRankHandler:
    async def execute(self, node: Any, context: dict[str, Any]) -> NodeOutcome:
        result = context.get("consensus_result")
        if result is None or result.run.judge is None:
            return NodeOutcome(success=False, error_message="judge missing")
        context["consensus_rankings"] = list(result.run.judge.rankings)
        return NodeOutcome(success=True)


class ConsensusMergeHandler:
    async def execute(self, node: Any, context: dict[str, Any]) -> NodeOutcome:
        result = context.get("consensus_result")
        if result is None or result.run.merge is None:
            return NodeOutcome(success=False, error_message="merge missing")
        context["merged_text"] = result.run.merge.merged_text
        context["section_sources"] = dict(result.run.merge.section_sources)
        return NodeOutcome(success=True)


class ConsensusCritiqueHandler:
    async def execute(self, node: Any, context: dict[str, Any]) -> NodeOutcome:
        result = context.get("consensus_result")
        if result is None:
            return NodeOutcome(success=False, error_message="consensus_result missing")
        critique = result.run.critique
        context["critique"] = {
            "severity": critique.severity if critique else "",
            "affected_sections": list(critique.affected_sections) if critique else [],
        }
        return NodeOutcome(success=True)


class ConsensusReviseHandler:
    async def execute(self, node: Any, context: dict[str, Any]) -> NodeOutcome:
        result = context.get("consensus_result")
        if result is None:
            return NodeOutcome(success=False, error_message="consensus_result missing")
        context["draft_text"] = result.final_text
        return NodeOutcome(success=True)


class ConsensusFinalizeHandler:
    async def execute(self, node: Any, context: dict[str, Any]) -> NodeOutcome:
        result = context.get("consensus_result")
        if result is None:
            return NodeOutcome(success=False, error_message="consensus_result missing")
        context["stage"] = "consensus_done"
        context["final_text"] = result.final_text
        context["consensus_report"] = result.run.to_report()
        return NodeOutcome(success=result.success, error_message=result.error or None)


def register_consensus_workflow_handlers(node_registry) -> None:
    node_registry.register("consensus.generate", ConsensusGenerateHandler())
    node_registry.register("consensus.evaluate", ConsensusEvaluateHandler())
    node_registry.register("consensus.rank", ConsensusRankHandler())
    node_registry.register("consensus.merge", ConsensusMergeHandler())
    node_registry.register("consensus.critique", ConsensusCritiqueHandler())
    node_registry.register("consensus.revise", ConsensusReviseHandler())
    node_registry.register("consensus.finalize", ConsensusFinalizeHandler())
