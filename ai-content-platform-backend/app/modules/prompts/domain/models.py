"""Prompt Builder domain models."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PromptStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PromptSectionName(str, Enum):
    SYSTEM = "system"
    KNOWLEDGE = "knowledge"
    BRAND = "brand"
    RULES = "rules"
    EXAMPLES = "examples"
    PLANNER = "planner"
    TASK = "task"
    OUTPUT_FORMAT = "output_format"
    VALIDATION = "validation"


@dataclass(frozen=True, slots=True)
class PromptVariableSpec:
    name: str
    type: str = "text"
    required: bool = True
    description: str = ""


@dataclass(frozen=True, slots=True)
class PromptSection:
    name: str
    body: str
    order: int = 0


@dataclass(frozen=True, slots=True)
class PromptDefinition:
    id: str
    name: str
    version: str
    capability: str
    status: PromptStatus = PromptStatus.ACTIVE
    approval_status: ApprovalStatus = ApprovalStatus.APPROVED
    template: str = ""
    sections: tuple[PromptSection, ...] = ()
    variables: tuple[PromptVariableSpec, ...] = ()
    required_inputs: tuple[str, ...] = ()
    optional_inputs: tuple[str, ...] = ()
    provider_constraints: dict[str, Any] = field(default_factory=dict)
    supported_models: tuple[str, ...] = ()
    schema_id: str = "json"
    tags: tuple[str, ...] = ()
    created_by: str = "platform"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class OutputSchema:
    schema_id: str
    format: str  # markdown | json | carousel | image_prompt
    description: str = ""
    json_schema: dict[str, Any] = field(default_factory=dict)
    instructions: str = ""


@dataclass(frozen=True, slots=True)
class CompiledPrompt:
    text: str
    system_message: str = ""
    sections: dict[str, str] = field(default_factory=dict)
    token_estimate: int = 0
    variables_used: tuple[str, ...] = ()
    prompt_id: str = ""
    prompt_version: str = ""
    capability: str = ""
    schema_id: str = "json"


@dataclass(frozen=True, slots=True)
class PromptSectionPresence:
    present: bool
    length: int = 0
    digest: str = ""


@dataclass(frozen=True, slots=True)
class PromptExplanation:
    """Provenance for debugging — never LinkedIn prose."""

    knowledge_sources: tuple[str, ...] = ()
    planner_inputs: tuple[str, ...] = ()
    rules: PromptSectionPresence = field(default_factory=lambda: PromptSectionPresence(False))
    claims: PromptSectionPresence = field(default_factory=lambda: PromptSectionPresence(False))
    brand: PromptSectionPresence = field(default_factory=lambda: PromptSectionPresence(False))
    examples: PromptSectionPresence = field(default_factory=lambda: PromptSectionPresence(False))
    variables_used: tuple[str, ...] = ()
    sections_present: tuple[str, ...] = ()
    policy_id: str = "default"
    lint_warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        def _presence(p: PromptSectionPresence) -> dict[str, Any]:
            return {"present": p.present, "length": p.length, "digest": p.digest}

        return {
            "knowledge_sources": list(self.knowledge_sources),
            "planner_inputs": list(self.planner_inputs),
            "rules": _presence(self.rules),
            "claims": _presence(self.claims),
            "brand": _presence(self.brand),
            "examples": _presence(self.examples),
            "variables_used": list(self.variables_used),
            "sections_present": list(self.sections_present),
            "policy_id": self.policy_id,
            "lint_warnings": list(self.lint_warnings),
        }


@dataclass(frozen=True, slots=True)
class PromptRequest:
    """Payload for Orchestrator — never LinkedIn prose authored here."""

    prompt: str
    capability: str
    prompt_version: str
    prompt_id: str = ""
    system_message: str = ""
    response_format: str = "json"
    schema_id: str = "json"
    sections: dict[str, str] = field(default_factory=dict)
    token_estimate: int = 0
    correlation_id: str = ""
    organization_id: uuid.UUID | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    valid: bool = True
    errors: tuple[str, ...] = ()
    explanation: PromptExplanation = field(default_factory=PromptExplanation)

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "capability": self.capability,
            "prompt_version": self.prompt_version,
            "prompt_id": self.prompt_id,
            "system_message": self.system_message,
            "response_format": self.response_format,
            "schema_id": self.schema_id,
            "sections": dict(self.sections),
            "token_estimate": self.token_estimate,
            "correlation_id": self.correlation_id,
            "organization_id": str(self.organization_id) if self.organization_id else None,
            "metrics": dict(self.metrics),
            "valid": self.valid,
            "errors": list(self.errors),
            "explanation": self.explanation.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class PromptBuildInput:
    capability: str
    organization_id: uuid.UUID | None = None
    correlation_id: str = ""
    prompt_name: str = ""
    prompt_version: str | None = None
    variables: dict[str, Any] = field(default_factory=dict)
    knowledge_text: str = ""
    brand_text: str = ""
    rules_text: str = ""
    examples_text: str = ""
    claims_text: str = ""
    preferences_text: str = ""
    planner_json: dict[str, Any] = field(default_factory=dict)
    token_budget: int = 6_000
    response_format: str = "json"
    schema_id: str = ""


@dataclass(frozen=True, slots=True)
class ValidationResult:
    valid: bool
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EvalCase:
    case_id: str
    prompt_name: str
    prompt_version: str
    variables: dict[str, Any]
    expected_contains: tuple[str, ...] = ()
    expected_json_keys: tuple[str, ...] = ()
    description: str = ""


@dataclass(frozen=True, slots=True)
class EvalRunResult:
    case_id: str
    passed: bool
    score: float
    details: str = ""
    prompt_version: str = ""


@dataclass(frozen=True, slots=True)
class PromptDiff:
    name: str
    left_version: str
    right_version: str
    added_lines: tuple[str, ...] = ()
    removed_lines: tuple[str, ...] = ()
    identical: bool = False


@dataclass(frozen=True, slots=True)
class PromptReplayRecord:
    replay_id: str
    prompt_id: str
    prompt_version: str
    capability: str
    compiled_hash: str
    compiled_text: str
    correlation_id: str = ""
    organization_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PromptPolicy:
    policy_id: str = "default"
    max_prompt_tokens: int = 12_000
    max_section_tokens: int = 4_000
    allowed_capabilities: tuple[str, ...] = ()
    denied_capabilities: tuple[str, ...] = ()
    restricted_variables: tuple[str, ...] = ()
    forbidden_sections: tuple[str, ...] = ()
    provider_constraints: dict[str, Any] = field(default_factory=dict)
    forbidden_substrings: tuple[str, ...] = ()
    required_sections: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PolicyResult:
    allowed: bool
    errors: tuple[str, ...] = ()
    policy_id: str = "default"
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SecurityScanResult:
    safe: bool
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LintResult:
    ok: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    case_id: str
    prompt_name: str
    prompt_version: str
    variables: dict[str, Any] = field(default_factory=dict)
    description: str = ""


@dataclass(frozen=True, slots=True)
class BenchmarkSuite:
    suite_id: str
    providers: tuple[str, ...] = ()
    cases: tuple[BenchmarkCase, ...] = ()
    compare_versions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    suite_id: str
    provider: str
    prompt_version: str
    case_id: str
    score: float | None = None
    status: str = "pending"  # pending | skipped | completed
    details: str = ""
