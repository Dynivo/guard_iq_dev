"""Prompt Validator — structural checks only (security lives in SecurityScanner)."""

from __future__ import annotations

from app.modules.prompts.domain.models import (
    CompiledPrompt,
    PromptDefinition,
    ValidationResult,
)


class DefaultPromptValidator:
    """Required vars, empty prompt, unresolved syntax, output_format schema gate.

    Size limits are enforced by PromptPolicyEngine. Injection by SecurityScanner.
    """

    def validate(
        self,
        definition: PromptDefinition,
        compiled: CompiledPrompt,
        variables: dict[str, str],
    ) -> ValidationResult:
        errors: list[str] = []

        for spec in definition.variables:
            if spec.required and not (variables.get(spec.name) or "").strip():
                errors.append(f"missing required variable: {spec.name}")

        for name in definition.required_inputs:
            if not (variables.get(name) or "").strip():
                errors.append(f"missing required input: {name}")

        if not compiled.text.strip() and not compiled.system_message.strip():
            errors.append("compiled prompt is empty")

        if "{{" in compiled.text or "{%" in compiled.text:
            errors.append("unresolved template syntax in compiled prompt")

        if definition.schema_id in {"json", "carousel"} and not compiled.sections.get(
            "output_format"
        ):
            if definition.metadata.get("require_output_format"):
                errors.append("output_format section required for schema")

        return ValidationResult(valid=len(errors) == 0, errors=tuple(errors))
