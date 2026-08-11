"""Prompt evaluation — golden cases, heuristic scoring (no live LLM)."""

from __future__ import annotations

from pathlib import Path

import yaml

from app.modules.prompts.domain.models import EvalCase, EvalRunResult, PromptBuildInput, PromptRequest
from app.modules.prompts.domain.ports import PromptBuilder


class DefaultPromptEvaluator:
    async def run_case(
        self, case: EvalCase, request: PromptRequest
    ) -> EvalRunResult:
        if not request.valid:
            return EvalRunResult(
                case_id=case.case_id,
                passed=False,
                score=0.0,
                details="; ".join(request.errors) or "invalid prompt",
                prompt_version=request.prompt_version,
            )

        hits = 0
        total = max(1, len(case.expected_contains) + len(case.expected_json_keys))
        details: list[str] = []
        text = f"{request.system_message}\n{request.prompt}".lower()

        for needle in case.expected_contains:
            if needle.lower() in text:
                hits += 1
            else:
                details.append(f"missing contains: {needle}")

        section_blob = " ".join(request.sections.keys()).lower()
        for key in case.expected_json_keys:
            # Keys expected in output schema instructions / sections
            if key.lower() in text or key.lower() in section_blob:
                hits += 1
            else:
                details.append(f"missing key hint: {key}")

        score = hits / total
        passed = score >= 0.99 if total > 0 else request.valid
        if case.expected_contains or case.expected_json_keys:
            passed = hits == total
        return EvalRunResult(
            case_id=case.case_id,
            passed=passed,
            score=score,
            details="; ".join(details),
            prompt_version=request.prompt_version,
        )

    async def run_suite(
        self, cases: list[EvalCase], builder: PromptBuilder
    ) -> list[EvalRunResult]:
        results: list[EvalRunResult] = []
        for case in cases:
            request = await builder.build(
                PromptBuildInput(
                    capability=case.prompt_name,
                    prompt_name=case.prompt_name,
                    prompt_version=case.prompt_version or None,
                    variables={k: str(v) for k, v in case.variables.items()},
                    knowledge_text=str(case.variables.get("knowledge") or ""),
                    brand_text=str(case.variables.get("brand") or ""),
                    rules_text=str(case.variables.get("rules") or ""),
                    examples_text=str(case.variables.get("examples") or ""),
                    planner_json=dict(case.variables.get("planner_json") or {})
                    if isinstance(case.variables.get("planner_json"), dict)
                    else {},
                )
            )
            results.append(await self.run_case(case, request))
        return results


def load_eval_cases(path: Path) -> list[EvalCase]:
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cases_raw = raw.get("cases") if isinstance(raw, dict) else raw
    if not isinstance(cases_raw, list):
        return []
    out: list[EvalCase] = []
    for item in cases_raw:
        if not isinstance(item, dict):
            continue
        out.append(
            EvalCase(
                case_id=str(item.get("case_id") or item.get("id") or ""),
                prompt_name=str(item.get("prompt_name") or ""),
                prompt_version=str(item.get("prompt_version") or ""),
                variables=dict(item.get("variables") or {}),
                expected_contains=tuple(
                    str(x) for x in (item.get("expected_contains") or [])
                ),
                expected_json_keys=tuple(
                    str(x) for x in (item.get("expected_json_keys") or [])
                ),
                description=str(item.get("description") or ""),
            )
        )
    return out
