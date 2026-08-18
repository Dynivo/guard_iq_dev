"""Revision engine — regenerate only affected sections, then re-merge."""

from __future__ import annotations

import json
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.ai.domain.models import OrchestratorRequest
from app.modules.ai.domain.ports import AIOrchestrator
from app.modules.consensus.application import sections as section_parser
from app.modules.consensus.domain.models import (
    ConsensusRequest,
    CritiqueReport,
    MergeDecision,
)

logger = get_logger(__name__)


class DefaultRevisionEngine:
    """Regenerate critique-affected sections via orchestrator and splice into merge."""

    def __init__(self, orchestrator: AIOrchestrator) -> None:
        self._orchestrator = orchestrator

    async def revise(
        self,
        request: ConsensusRequest,
        merged: MergeDecision,
        critique: CritiqueReport,
        *,
        correlation_id: str = "",
    ) -> MergeDecision:
        affected = [
            s
            for s in (critique.affected_sections or [])
            if s in section_parser.SECTION_KEYS
        ]
        if not affected:
            return merged

        provider_override = self._select_revision_provider(request)
        prompt = self._build_revision_prompt(
            original_prompt=request.prompt,
            merged_sections=merged.merged_sections,
            affected=affected,
            issues=critique.issues,
        )

        try:
            outcome = await self._orchestrator.execute(
                OrchestratorRequest(
                    capability=request.capability or "writing",
                    prompt=prompt,
                    system_message=(
                        request.system_message
                        or "You revise only the requested LinkedIn post sections. "
                        "Return JSON with only those section keys."
                    ),
                    organization_id=request.organization_id,
                    correlation_id=correlation_id or request.correlation_id,
                    response_format="json",
                    prompt_version=request.prompt_version,
                    bypass_cache=True,
                    provider_override=provider_override,
                    skip_fallbacks=True,
                    metadata={
                        **dict(request.metadata),
                        "consensus_stage": "revise",
                        "affected_sections": affected,
                    },
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "consensus.revise_failed",
                extra={
                    "app_module": "consensus",
                    "operation": "revise",
                    "correlation_id": correlation_id or request.correlation_id,
                    "error": str(exc),
                    "outcome": "failure",
                },
            )
            return merged

        if not outcome.success or outcome.result is None:
            logger.warning(
                "consensus.revise_empty",
                extra={
                    "app_module": "consensus",
                    "operation": "revise",
                    "correlation_id": correlation_id or request.correlation_id,
                    "error": outcome.error_message,
                    "outcome": "failure",
                },
            )
            return merged

        revised_sections = section_parser.parse_sections(outcome.result.text)
        new_merged = dict(merged.merged_sections or {})
        new_sources = dict(merged.section_sources or {})
        revision_id = f"revision:{provider_override or outcome.provider or 'orchestrator'}"

        for key in affected:
            value = revised_sections.get(key)
            if key == "hashtags":
                if isinstance(value, list) and value:
                    new_merged[key] = list(value)
                    new_sources[key] = revision_id
                continue
            if str(value or "").strip():
                new_merged[key] = value
                new_sources[key] = revision_id

        # Ensure canonical keys
        for key in section_parser.SECTION_KEYS:
            if key not in new_merged:
                new_merged[key] = [] if key == "hashtags" else ""

        merged_text = section_parser.sections_to_json_text(new_merged)
        meta = dict(merged.metadata or {})
        meta["revised_sections"] = list(affected)
        meta["revision_provider"] = provider_override or outcome.provider

        logger.info(
            "consensus.revise_complete",
            extra={
                "app_module": "consensus",
                "operation": "revise",
                "correlation_id": correlation_id or request.correlation_id,
                "affected_sections": affected,
                "provider": provider_override or outcome.provider,
                "outcome": "success",
            },
        )
        return MergeDecision(
            merged_text=merged_text,
            merged_sections=new_merged,
            section_sources=new_sources,
            strategy=merged.strategy,
            metadata=meta,
        )

    def _select_revision_provider(self, request: ConsensusRequest) -> str | None:
        """Use an explicit override or the configured real default provider."""
        meta = request.metadata or {}
        if meta.get("revision_provider"):
            return str(meta["revision_provider"]).lower()
        settings = get_settings()
        return str(settings.DEFAULT_LLM_PROVIDER or "gemini").strip().lower()

    def _build_revision_prompt(
        self,
        *,
        original_prompt: str,
        merged_sections: dict[str, Any],
        affected: list[str],
        issues: list[dict[str, Any]],
    ) -> str:
        relevant_issues = [
            i
            for i in issues
            if isinstance(i, dict)
            and (not i.get("section") or str(i.get("section")) in affected)
        ]
        current = {k: merged_sections.get(k) for k in affected}
        return (
            "Revise ONLY these LinkedIn post sections. Do not rewrite other sections.\n"
            f"Sections to revise: {json.dumps(affected)}\n"
            f"Current section values:\n{json.dumps(current, ensure_ascii=False, indent=2)}\n"
            f"Critique issues:\n{json.dumps(relevant_issues, ensure_ascii=False, indent=2)}\n"
            f"Original generation brief:\n{original_prompt}\n"
            "Return JSON containing only the revised section keys "
            "(hook, body, cta, hashtags, statistics, visual_prompt as applicable)."
        )
