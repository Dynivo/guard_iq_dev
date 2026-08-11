"""ClaimsGuard — flags numbers/statistics in draft text not found in source or active claims."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.infrastructure.postgres.models.intelligence import Claim

logger = get_logger(__name__)

_NUMBER_PATTERN = re.compile(
    r"""
    (?:                          # Non-capturing group for number patterns
        \d{1,3}(?:,\d{3})*      # Comma-separated thousands (1,000 or 1,000,000)
        (?:\.\d+)?              # Optional decimal part
        |                       # OR
        \d+(?:\.\d+)?           # Simple numbers with optional decimal
    )
    \s*                         # Optional whitespace
    (?:%|percent|minutes?|hours?|days?|weeks?|months?|years?|
       million|billion|£|users?|firms?|businesses?|organisations?)?  # Optional unit
    """,
    re.VERBOSE | re.IGNORECASE,
)

_TRIVIAL_NUMBERS = {"1", "2", "3", "4", "5", "10", "100", "0"}


@dataclass
class ClaimCheckResult:
    """Result of a claims guard check."""

    passed: bool
    flagged_claims: list[dict]
    total_numbers_found: int
    verified_count: int


class ClaimsGuard:
    """Verifies that numbers/statistics in generated text are backed by source material or stored claims."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def verify(
        self,
        org_id: uuid.UUID,
        text: str,
        source_text: str = "",
    ) -> ClaimCheckResult:
        """Check all numbers in `text` against source_text and active claims in DB.

        Returns a ClaimCheckResult indicating pass/fail and any flagged items.
        """
        numbers_in_draft = self._extract_numbers(text)
        if not numbers_in_draft:
            return ClaimCheckResult(passed=True, flagged_claims=[], total_numbers_found=0, verified_count=0)

        numbers_in_source = self._extract_numbers(source_text) if source_text else set()
        active_claims = await self._load_active_claims(org_id)
        claims_text = " ".join(c.text for c in active_claims)
        numbers_in_claims = self._extract_numbers(claims_text)

        allowed_numbers = numbers_in_source | numbers_in_claims

        flagged: list[dict] = []
        verified = 0

        for num in numbers_in_draft:
            if num in _TRIVIAL_NUMBERS:
                verified += 1
                continue
            if num in allowed_numbers:
                verified += 1
            else:
                flagged.append({
                    "number": num,
                    "context": self._find_context(text, num),
                    "reason": "Not found in source article or active claims",
                })

        passed = len(flagged) == 0

        if flagged:
            logger.warning(
                "ClaimsGuard flagged %d unverified numbers in draft for org=%s",
                len(flagged),
                org_id,
            )

        return ClaimCheckResult(
            passed=passed,
            flagged_claims=flagged,
            total_numbers_found=len(numbers_in_draft),
            verified_count=verified,
        )

    def _extract_numbers(self, text: str) -> set[str]:
        """Extract all meaningful numbers from text."""
        matches = _NUMBER_PATTERN.findall(text)
        numbers: set[str] = set()
        for match in matches:
            core = re.sub(r"[^\d.,]", "", match).strip().rstrip(".,")
            if core and core not in _TRIVIAL_NUMBERS:
                numbers.add(core)
            elif core in _TRIVIAL_NUMBERS:
                numbers.add(core)
        return numbers

    def _find_context(self, text: str, number: str) -> str:
        """Find the sentence or phrase containing the number."""
        sentences = re.split(r"[.!?\n]", text)
        for sentence in sentences:
            if number in sentence:
                return sentence.strip()[:200]
        return ""

    async def _load_active_claims(self, org_id: uuid.UUID) -> list[Claim]:
        stmt = select(Claim).where(
            Claim.organization_id == org_id,
            Claim.active.is_(True),
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
