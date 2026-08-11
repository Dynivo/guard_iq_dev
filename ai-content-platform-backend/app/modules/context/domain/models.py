"""Context Builder domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.modules.knowledge.domain.models import CompressedKnowledge, KnowledgeItem, KnowledgeQuery


@dataclass(frozen=True, slots=True)
class ContextBuildInput:
    query: KnowledgeQuery
    compressed: CompressedKnowledge
    brand_text: str = ""
    examples_text: str = ""
    rules_text: str = ""
    claims_text: str = ""
    preferences_text: str = ""
    planner_output: str = ""  # future M6
    extra_sections: dict[str, str] = field(default_factory=dict)
