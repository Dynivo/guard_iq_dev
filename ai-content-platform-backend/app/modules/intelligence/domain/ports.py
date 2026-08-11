"""Intelligence module ports — relevance scoring."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass
class RelevanceResult:
    score: int
    sector: str | None
    framework: str | None
    audience: str | None
    angle: str | None
    reason: str | None


class RelevanceScorer(Protocol):
    """Port for article relevance scoring using the client profile."""

    async def score(self, org_id: uuid.UUID, article_id: uuid.UUID) -> RelevanceResult: ...
