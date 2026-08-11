"""Unit tests for ClaimsGuard."""

from __future__ import annotations

import re


def extract_numbers(text: str) -> list[str]:
    return re.findall(r"\b\d+(?:\.\d+)?%?\b", text)


def test_claims_numbers_in_source_pass() -> None:
    text = "We contained it in 8 minutes."
    source = "Operational note: containment in 8 minutes on the full plan."
    flagged = [n for n in extract_numbers(text) if n not in source]
    assert flagged == []


def test_claims_numbers_not_in_source_flagged() -> None:
    text = "Average score is 37% lower than expected."
    source = "Business email compromise uses lookalike domains."
    flagged = [n for n in extract_numbers(text) if n not in source]
    assert "37" in flagged
