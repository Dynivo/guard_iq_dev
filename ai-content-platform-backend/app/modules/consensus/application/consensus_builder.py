"""Build consensus metrics from section agreement + judge confidence."""

from __future__ import annotations

import re
from typing import Any

from app.modules.consensus.application import sections as section_parser
from app.modules.consensus.domain.models import (
    CandidateResponse,
    ConsensusMetrics,
    EvaluationScore,
    JudgeDecision,
)

_TOKEN_RE = re.compile(r"[a-z0-9#]+", re.I)


class DefaultConsensusBuilder:
    """Jaccard/overlap agreement on section texts, blended with judge confidence."""

    SECTION_KEYS = ("hook", "body", "cta", "hashtags", "statistics", "visual_prompt")

    def build(
        self,
        candidates: list[CandidateResponse],
        evaluations: list[EvaluationScore],
        judge: JudgeDecision | None,
    ) -> ConsensusMetrics:
        successful = [c for c in candidates if c.success]
        details: dict[str, Any] = {
            "pairwise": [],
            "section_agreement": {},
            "eval_mean_composite": 0.0,
        }

        if evaluations:
            details["eval_mean_composite"] = round(
                sum(e.composite for e in evaluations) / len(evaluations), 4
            )

        if len(successful) == 0:
            return ConsensusMetrics(
                agreement=0.0,
                consensus_score=0.0,
                candidate_count=len(candidates),
                successful_count=0,
                details=details,
            )

        if len(successful) == 1:
            agreement = 1.0
            section_scores = {k: 1.0 for k in self.SECTION_KEYS}
        else:
            section_scores = {}
            for key in self.SECTION_KEYS:
                texts = [
                    section_parser.section_text(c.sections or {}, key)
                    for c in successful
                ]
                section_scores[key] = _mean_pairwise_jaccard(texts)
            agreement = sum(section_scores.values()) / len(section_scores)

            # Also record overall text pairwise for diagnostics
            full_texts = [c.text or "" for c in successful]
            details["pairwise"].append(
                {"scope": "full_text", "jaccard": _mean_pairwise_jaccard(full_texts)}
            )

        details["section_agreement"] = {
            k: round(v, 4) for k, v in section_scores.items()
        }

        judge_conf = float(judge.confidence) if judge else 0.0
        judge_conf = max(0.0, min(1.0, judge_conf))
        # Blend agreement with judge confidence (equal weight when judge present)
        if judge is not None and judge.rankings:
            consensus_score = 0.55 * agreement + 0.45 * judge_conf
        elif judge is not None:
            consensus_score = 0.7 * agreement + 0.3 * judge_conf
        else:
            consensus_score = agreement

        details["judge_confidence"] = judge_conf
        details["agreement_raw"] = round(agreement, 4)

        return ConsensusMetrics(
            agreement=round(agreement, 4),
            consensus_score=round(consensus_score, 4),
            candidate_count=len(candidates),
            successful_count=len(successful),
            details=details,
        )


def _tokenize(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text or "")}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _overlap_coefficient(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def _pair_similarity(text_a: str, text_b: str) -> float:
    ta, tb = _tokenize(text_a), _tokenize(text_b)
    # Blend Jaccard with overlap coefficient for short sections
    return 0.65 * _jaccard(ta, tb) + 0.35 * _overlap_coefficient(ta, tb)


def _mean_pairwise_jaccard(texts: list[str]) -> float:
    n = len(texts)
    if n <= 1:
        return 1.0
    total = 0.0
    pairs = 0
    for i in range(n):
        for j in range(i + 1, n):
            total += _pair_similarity(texts[i], texts[j])
            pairs += 1
    return total / pairs if pairs else 0.0
