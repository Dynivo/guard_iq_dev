"""Orchestrator pre/post processors and response validators."""

from __future__ import annotations

import json
import re
from typing import Any, Protocol

from app.modules.ai.domain.models import OrchestratorRequest, OrchestratorResult


class PreProcessor(Protocol):
    async def process(self, request: OrchestratorRequest) -> OrchestratorRequest: ...


class PostProcessor(Protocol):
    async def process(
        self, request: OrchestratorRequest, result: OrchestratorResult
    ) -> OrchestratorResult: ...


class ResponseValidator(Protocol):
    def validate(self, text: str, *, response_format: str = "json") -> tuple[bool, str | None]: ...


class PromptSanitizer:
    async def process(self, request: OrchestratorRequest) -> OrchestratorRequest:
        cleaned = request.prompt.replace("\x00", "").strip()
        request.prompt = cleaned
        return request


class JsonValidator:
    def validate(self, text: str, *, response_format: str = "json") -> tuple[bool, str | None]:
        if response_format != "json":
            return True, None
        try:
            json.loads(text)
            return True, None
        except json.JSONDecodeError:
            # allow fenced json
            if "```json" in text:
                try:
                    body = text.split("```json", 1)[1].split("```", 1)[0]
                    json.loads(body)
                    return True, None
                except (json.JSONDecodeError, IndexError):
                    pass
            return False, "Invalid JSON response"


class MarkdownValidator:
    def validate(self, text: str, *, response_format: str = "json") -> tuple[bool, str | None]:
        if response_format != "markdown":
            return True, None
        if not text.strip():
            return False, "Empty markdown"
        return True, None


class LengthValidator:
    def __init__(self, min_chars: int = 1, max_chars: int = 100_000) -> None:
        self._min = min_chars
        self._max = max_chars

    def validate(self, text: str, *, response_format: str = "json") -> tuple[bool, str | None]:
        n = len(text)
        if n < self._min:
            return False, f"Response too short ({n})"
        if n > self._max:
            return False, f"Response too long ({n})"
        return True, None


class ForbiddenWordsValidator:
    def __init__(self, words: list[str] | None = None) -> None:
        self._words = [w.lower() for w in (words or [])]

    def validate(self, text: str, *, response_format: str = "json") -> tuple[bool, str | None]:
        lower = text.lower()
        for w in self._words:
            if w and w in lower:
                return False, f"Forbidden word: {w}"
        return True, None


class SchemaValidator:
    """Lightweight required-keys check for JSON objects."""

    def __init__(self, required_keys: list[str] | None = None) -> None:
        self._keys = required_keys or []

    def validate(self, text: str, *, response_format: str = "json") -> tuple[bool, str | None]:
        if response_format != "json" or not self._keys:
            return True, None
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return False, "Schema check requires JSON"
        if not isinstance(data, dict):
            return False, "Expected JSON object"
        missing = [k for k in self._keys if k not in data]
        if missing:
            return False, f"Missing keys: {', '.join(missing)}"
        return True, None


class OutputFormatter:
    async def process(
        self, request: OrchestratorRequest, result: OrchestratorResult
    ) -> OrchestratorResult:
        if result.result and result.result.text:
            result.result.text = result.result.text.strip()
        return result


class CitationExtractor:
    _PATTERN = re.compile(r"\[([a-z_]+:[^\]]+)\]")

    async def process(
        self, request: OrchestratorRequest, result: OrchestratorResult
    ) -> OrchestratorResult:
        if result.result and result.result.text:
            cites = self._PATTERN.findall(result.result.text)
            result.metrics = {**result.metrics, "citations_found": cites}
        return result


class CompositeValidator:
    def __init__(self, validators: list[Any]) -> None:
        self._validators = validators

    def validate(self, text: str, *, response_format: str = "json") -> tuple[bool, str | None]:
        for v in self._validators:
            ok, err = v.validate(text, response_format=response_format)
            if not ok:
                return False, err
        return True, None
