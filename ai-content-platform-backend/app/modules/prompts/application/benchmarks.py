"""Prompt Benchmark runner — suite YAML scaffold (no live LLM calls)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.modules.prompts.domain.models import (
    BenchmarkCase,
    BenchmarkResult,
    BenchmarkSuite,
)
from app.modules.prompts.domain.ports import PromptRegistry

_DEFAULT_DIR = Path(__file__).resolve().parents[4] / "configs" / "prompts" / "benchmarks"

_KNOWN_PROVIDERS = ("gemini", "openai", "anthropic", "perplexity")


class DefaultPromptBenchmarkRunner:
    """Loads benchmark suites and prepares pending results per provider.

    Execution against vendors is deferred to Writer/Orchestrator (M9+).
    """

    def __init__(self, benchmarks_dir: Path | None = None) -> None:
        self._dir = benchmarks_dir or _DEFAULT_DIR

    def load_suite(self, suite_id: str) -> BenchmarkSuite:
        path = self._dir / f"{suite_id}.yaml"
        if not path.exists():
            path = self._dir / f"{suite_id}_suite.yaml"
        raw: dict[str, Any] = {}
        if path.exists():
            loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(loaded, dict):
                raw = loaded
        providers = tuple(
            str(x) for x in (raw.get("providers") or list(_KNOWN_PROVIDERS))
        )
        cases_raw = raw.get("cases") or []
        cases: list[BenchmarkCase] = []
        for item in cases_raw:
            if not isinstance(item, dict):
                continue
            cases.append(
                BenchmarkCase(
                    case_id=str(item.get("case_id") or item.get("id") or ""),
                    prompt_name=str(item.get("prompt_name") or ""),
                    prompt_version=str(item.get("prompt_version") or ""),
                    variables=dict(item.get("variables") or {}),
                    description=str(item.get("description") or ""),
                )
            )
        return BenchmarkSuite(
            suite_id=str(raw.get("suite_id") or suite_id),
            providers=providers,
            cases=tuple(cases),
            compare_versions=tuple(str(x) for x in (raw.get("compare_versions") or [])),
        )

    async def prepare(
        self, suite: BenchmarkSuite, registry: PromptRegistry
    ) -> list[BenchmarkResult]:
        results: list[BenchmarkResult] = []
        for case in suite.cases:
            defn = None
            if case.prompt_version:
                defn = await registry.get_version(case.prompt_name, case.prompt_version)
            if defn is None:
                defn = await registry.get_latest(case.prompt_name)
            version = case.prompt_version or (defn.version if defn else "")
            status = "pending" if defn is not None else "skipped"
            details = "" if defn is not None else f"prompt not found: {case.prompt_name}"
            for provider in suite.providers:
                results.append(
                    BenchmarkResult(
                        suite_id=suite.suite_id,
                        provider=provider,
                        prompt_version=version,
                        case_id=case.case_id,
                        score=None,
                        status=status,
                        details=details,
                    )
                )
            for ver in suite.compare_versions:
                alt = await registry.get_version(case.prompt_name, ver)
                for provider in suite.providers:
                    results.append(
                        BenchmarkResult(
                            suite_id=suite.suite_id,
                            provider=provider,
                            prompt_version=ver,
                            case_id=case.case_id,
                            score=None,
                            status="pending" if alt is not None else "skipped",
                            details="" if alt is not None else f"version missing: {ver}",
                        )
                    )
        return results
