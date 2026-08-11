"""Prompt Builder ports."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Protocol

from app.modules.prompts.domain.models import (
    BenchmarkResult,
    BenchmarkSuite,
    CompiledPrompt,
    EvalCase,
    EvalRunResult,
    LintResult,
    OutputSchema,
    PolicyResult,
    PromptBuildInput,
    PromptDefinition,
    PromptDiff,
    PromptPolicy,
    PromptReplayRecord,
    PromptRequest,
    SecurityScanResult,
    ValidationResult,
)


class PromptRegistry(Protocol):
    async def get_latest(self, name: str) -> PromptDefinition | None: ...

    async def get_version(self, name: str, version: str) -> PromptDefinition | None: ...

    async def register(self, definition: PromptDefinition) -> str: ...

    async def list_names(self) -> list[str]: ...


class PromptCompiler(Protocol):
    def compile(
        self, definition: PromptDefinition, variables: dict[str, str]
    ) -> CompiledPrompt: ...


class PromptOptimizer(Protocol):
    def optimize(
        self, compiled: CompiledPrompt, *, token_budget: int
    ) -> CompiledPrompt: ...


class PromptValidator(Protocol):
    def validate(
        self,
        definition: PromptDefinition,
        compiled: CompiledPrompt,
        variables: dict[str, str],
    ) -> ValidationResult: ...


class PromptPolicyEngine(Protocol):
    def apply(
        self,
        definition: PromptDefinition,
        compiled: CompiledPrompt,
        variables: dict[str, str],
        *,
        organization_id: uuid.UUID | None,
        capability: str,
        policy: PromptPolicy | None = None,
    ) -> PolicyResult: ...


class PromptSecurityScanner(Protocol):
    def scan(
        self,
        definition: PromptDefinition,
        compiled: CompiledPrompt,
        variables: dict[str, str],
        *,
        partials_dir: Path | None = None,
    ) -> SecurityScanResult: ...


class PromptLinter(Protocol):
    def lint(
        self,
        definition: PromptDefinition,
        *,
        partials_dir: Path | None = None,
    ) -> LintResult: ...


class PromptBuilder(Protocol):
    async def build(self, inp: PromptBuildInput) -> PromptRequest: ...

    async def preview(self, inp: PromptBuildInput) -> PromptRequest: ...


class OutputSchemaRegistry(Protocol):
    def get(self, schema_id: str) -> OutputSchema | None: ...

    def list_ids(self) -> list[str]: ...


class PromptEvaluator(Protocol):
    async def run_case(
        self, case: EvalCase, request: PromptRequest
    ) -> EvalRunResult: ...

    async def run_suite(
        self, cases: list[EvalCase], builder: PromptBuilder
    ) -> list[EvalRunResult]: ...


class PromptReplayStore(Protocol):
    async def save(self, record: PromptReplayRecord) -> None: ...

    async def get(self, replay_id: str) -> PromptReplayRecord | None: ...


class PromptDiffer(Protocol):
    def diff(
        self, left: PromptDefinition, right: PromptDefinition
    ) -> PromptDiff: ...


class PromptBenchmarkRunner(Protocol):
    def load_suite(self, suite_id: str) -> BenchmarkSuite: ...

    async def prepare(
        self, suite: BenchmarkSuite, registry: PromptRegistry
    ) -> list[BenchmarkResult]: ...
