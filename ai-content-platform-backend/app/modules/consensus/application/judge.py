"""Anonymous AI judge for consensus ranking."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from app.core.logging import get_logger
from app.modules.ai.domain.models import OrchestratorRequest
from app.modules.ai.domain.ports import AIOrchestrator
from app.modules.consensus.application.config_loader import load_consensus_config
from app.modules.consensus.domain.models import (
    CandidateResponse,
    EvaluationScore,
    JudgeDecision,
)

logger = get_logger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parents[4] / "configs" / "prompts" / "consensus_judge.yaml"


class DefaultAIJudge:
    """Anonymize candidates, call consensus_judge capability, parse JudgeDecision."""

    def __init__(
        self,
        orchestrator: AIOrchestrator,
        *,
        config: dict[str, Any] | None = None,
        prompt_path: Path | None = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._config = config if config is not None else load_consensus_config()
        self._judge_cfg = dict(self._config.get("judge") or {})
        self._prompt_path = prompt_path or _PROMPT_PATH

    async def judge(
        self,
        candidates: list[CandidateResponse],
        evaluations: list[EvaluationScore],
        *,
        correlation_id: str = "",
        organization_id: Any = None,
    ) -> JudgeDecision:
        successful = [c for c in candidates if c.success]
        min_candidates = int(self._judge_cfg.get("min_candidates", 1))
        if len(successful) < min_candidates:
            return JudgeDecision(rankings=[], confidence=0.0, anonymized=True)

        eval_by_id = {e.candidate_id: e for e in evaluations}
        anon_payload = []
        det_scores = []
        for c in successful:
            anon_id = c.anonymous_id or c.candidate_id
            ev = eval_by_id.get(c.candidate_id)
            anon_payload.append(
                {
                    "candidate_id": anon_id,
                    "text": c.text,
                    "sections": {
                        k: v
                        for k, v in (c.sections or {}).items()
                        if k != "provider"
                    },
                }
            )
            det_scores.append(
                {
                    "candidate_id": anon_id,
                    "composite": ev.composite if ev else 0.0,
                    "passed": ev.passed if ev else False,
                    "scores": dict(ev.scores) if ev else {},
                }
            )

        system_msg, user_prompt = self._render_prompt(
            deterministic_scores=json.dumps(det_scores, ensure_ascii=False),
            candidates_json=json.dumps(anon_payload, ensure_ascii=False),
        )
        capability = str(self._judge_cfg.get("capability") or "consensus_judge")
        response_format = str(self._judge_cfg.get("response_format") or "json")
        temperature = self._judge_cfg.get("temperature")
        max_tokens = self._judge_cfg.get("max_tokens")

        try:
            outcome = await self._orchestrator.execute(
                OrchestratorRequest(
                    capability=capability,
                    prompt=user_prompt,
                    system_message=system_msg,
                    organization_id=organization_id,
                    correlation_id=correlation_id,
                    response_format=response_format,
                    temperature=float(temperature) if temperature is not None else None,
                    max_tokens=int(max_tokens) if max_tokens is not None else None,
                    bypass_cache=True,
                    skip_fallbacks=False,
                    metadata={"consensus_stage": "judge", "anonymized": True},
                )
            )
        except Exception as exc:  # noqa: BLE001 — judge must degrade gracefully
            logger.error(
                "consensus.judge_failed",
                extra={
                    "app_module": "consensus",
                    "operation": "judge",
                    "correlation_id": correlation_id,
                    "error": str(exc),
                    "outcome": "failure",
                },
            )
            return JudgeDecision(rankings=[], confidence=0.0, anonymized=True)

        if not outcome.success or outcome.result is None:
            logger.warning(
                "consensus.judge_empty",
                extra={
                    "app_module": "consensus",
                    "operation": "judge",
                    "correlation_id": correlation_id,
                    "error": outcome.error_message,
                    "outcome": "failure",
                },
            )
            return JudgeDecision(
                rankings=[],
                confidence=0.0,
                provider=outcome.provider,
                model=outcome.model,
                latency_ms=int((outcome.metrics or {}).get("latency_ms", 0)),
                anonymized=True,
            )

        parsed = _parse_judge_json(outcome.result.text)
        if parsed is None:
            return JudgeDecision(
                rankings=[],
                confidence=0.0,
                raw={"parse_error": True, "text": outcome.result.text[:2000]},
                provider=outcome.result.provider,
                model=outcome.result.model,
                latency_ms=int(outcome.result.latency_ms),
                anonymized=True,
            )

        rankings = parsed.get("rankings") or []
        if not isinstance(rankings, list):
            rankings = []
        try:
            confidence = float(parsed.get("confidence", 0.0) or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))

        return JudgeDecision(
            rankings=[r for r in rankings if isinstance(r, dict)],
            confidence=confidence,
            raw=parsed,
            provider=outcome.result.provider,
            model=outcome.result.model,
            latency_ms=int(outcome.result.latency_ms),
            anonymized=True,
        )

    def _render_prompt(
        self, *, deterministic_scores: str, candidates_json: str
    ) -> tuple[str, str]:
        raw = self._load_prompt_yaml()
        system = str(raw.get("system") or "").strip()
        template = str(raw.get("user_template") or raw.get("template") or "").strip()
        user = template.replace("{{deterministic_scores}}", deterministic_scores)
        user = user.replace("{{candidates_json}}", candidates_json)
        return system, user

    def _load_prompt_yaml(self) -> dict[str, Any]:
        if not self._prompt_path.exists():
            return {
                "system": "You are an anonymous enterprise content judge. Return JSON only.",
                "user_template": (
                    "Deterministic scores: {{deterministic_scores}}\n"
                    "Candidates:\n{{candidates_json}}\n"
                    'Return JSON: {"rankings": [], "confidence": 0.0}'
                ),
            }
        return yaml.safe_load(self._prompt_path.read_text(encoding="utf-8")) or {}


def _parse_judge_json(text: str) -> dict[str, Any] | None:
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
