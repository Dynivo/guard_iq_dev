"""AI critique engine — critique only, never rewrites."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from app.core.logging import get_logger
from app.modules.ai.domain.models import OrchestratorRequest
from app.modules.ai.domain.ports import AIOrchestrator
from app.modules.consensus.domain.models import CritiqueReport, MergeDecision

logger = get_logger(__name__)

_PROMPT_PATH = (
    Path(__file__).resolve().parents[4] / "configs" / "prompts" / "consensus_critique.yaml"
)
_VALID_SECTIONS = frozenset(
    {"hook", "body", "cta", "hashtags", "statistics", "visual_prompt"}
)


class DefaultCritiqueEngine:
    """Call consensus_critique capability and parse CritiqueReport."""

    def __init__(
        self,
        orchestrator: AIOrchestrator,
        *,
        prompt_path: Path | None = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._prompt_path = prompt_path or _PROMPT_PATH

    async def critique(
        self,
        merged: MergeDecision,
        *,
        correlation_id: str = "",
        organization_id: Any = None,
    ) -> CritiqueReport:
        system_msg, user_prompt = self._render_prompt(merged.merged_text)
        try:
            outcome = await self._orchestrator.execute(
                OrchestratorRequest(
                    capability="consensus_critique",
                    prompt=user_prompt,
                    system_message=system_msg,
                    organization_id=organization_id,
                    correlation_id=correlation_id,
                    response_format="json",
                    bypass_cache=True,
                    metadata={"consensus_stage": "critique"},
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "consensus.critique_failed",
                extra={
                    "app_module": "consensus",
                    "operation": "critique",
                    "correlation_id": correlation_id,
                    "error": str(exc),
                    "outcome": "failure",
                },
            )
            return CritiqueReport(
                issues=[],
                affected_sections=[],
                severity="low",
                raw={"error": str(exc)},
            )

        if not outcome.success or outcome.result is None:
            return CritiqueReport(
                issues=[],
                affected_sections=[],
                severity="low",
                raw={"error": outcome.error_message or "critique_failed"},
                provider=outcome.provider,
                model=outcome.model,
            )

        parsed = _parse_json(outcome.result.text)
        if parsed is None:
            return CritiqueReport(
                issues=[],
                affected_sections=[],
                severity="low",
                raw={"parse_error": True, "text": (outcome.result.text or "")[:2000]},
                provider=outcome.result.provider,
                model=outcome.result.model,
            )

        issues_raw = parsed.get("issues") or []
        issues = [i for i in issues_raw if isinstance(i, dict)]
        affected = [
            str(s)
            for s in (parsed.get("affected_sections") or [])
            if str(s) in _VALID_SECTIONS
        ]
        if not affected:
            for issue in issues:
                section = str(issue.get("section") or "")
                if section in _VALID_SECTIONS and section not in affected:
                    affected.append(section)

        severity = str(parsed.get("severity") or "low").lower()
        if severity not in {"low", "medium", "high", "critical"}:
            severity = _infer_severity(issues)

        return CritiqueReport(
            issues=issues,
            affected_sections=affected,
            severity=severity,
            raw=parsed,
            provider=outcome.result.provider,
            model=outcome.result.model,
        )

    def _render_prompt(self, merged_json: str) -> tuple[str, str]:
        raw = self._load_prompt_yaml()
        system = str(raw.get("system") or "").strip()
        template = str(raw.get("user_template") or raw.get("template") or "").strip()
        user = template.replace("{{merged_json}}", merged_json)
        return system, user

    def _load_prompt_yaml(self) -> dict[str, Any]:
        if not self._prompt_path.exists():
            return {
                "system": "Critique only. Never rewrite. Return JSON.",
                "user_template": (
                    "Critique this draft JSON:\n{{merged_json}}\n"
                    'Return JSON: {"issues": [], "affected_sections": [], "severity": "low"}'
                ),
            }
        return yaml.safe_load(self._prompt_path.read_text(encoding="utf-8")) or {}


def _infer_severity(issues: list[dict[str, Any]]) -> str:
    order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    best = 0
    for issue in issues:
        sev = str(issue.get("severity") or "low").lower()
        best = max(best, order.get(sev, 0))
    for name, rank in order.items():
        if rank == best:
            return name
    return "low"


def _parse_json(text: str) -> dict[str, Any] | None:
    blob = (text or "").strip()
    if not blob:
        return None
    if "```" in blob:
        match = re.search(
            r"```(?:json)?\s*(\{.*?\})\s*```", blob, re.DOTALL | re.IGNORECASE
        )
        if match:
            blob = match.group(1)
    start = blob.find("{")
    end = blob.rfind("}")
    if start >= 0 and end > start:
        blob = blob[start : end + 1]
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None
