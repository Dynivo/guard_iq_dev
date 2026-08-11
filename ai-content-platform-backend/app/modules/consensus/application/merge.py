"""Merge engine: winner_take_all (best full draft) or section_best."""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.modules.consensus.application.config_loader import load_consensus_config
from app.modules.consensus.application import sections as section_parser
from app.modules.consensus.domain.models import (
    CandidateResponse,
    EvaluationScore,
    JudgeDecision,
    MergeDecision,
)

logger = get_logger(__name__)


class DefaultMergeEngine:
    """Select best content via scoring — full-draft winner or per-section best."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        cfg = config if config is not None else load_consensus_config()
        self._merge_cfg = dict(cfg.get("merge") or {})
        self._providers_cfg = dict(cfg.get("providers") or {})
        self._strategy = str(self._merge_cfg.get("strategy") or "winner_take_all")
        self._min_section_score = float(self._merge_cfg.get("min_section_score") or 0.0)
        self._section_rules = list(self._merge_cfg.get("sections") or [])
        self._roles_by_provider = self._build_roles_map()

    def merge(
        self,
        candidates: list[CandidateResponse],
        evaluations: list[EvaluationScore],
        judge: JudgeDecision | None,
    ) -> MergeDecision:
        successful = [c for c in candidates if c.success]
        if not successful:
            empty = section_parser.parse_sections("")
            return MergeDecision(
                merged_text=section_parser.sections_to_json_text(empty),
                merged_sections=empty,
                section_sources={},
                strategy=self._strategy,
                metadata={"reason": "no_successful_candidates"},
            )

        if self._strategy in {"winner_take_all", "best_of", "pick_best"}:
            return self._winner_take_all(successful, evaluations, judge)
        return self._section_best(successful, evaluations, judge)

    def _winner_take_all(
        self,
        successful: list[CandidateResponse],
        evaluations: list[EvaluationScore],
        judge: JudgeDecision | None,
    ) -> MergeDecision:
        """Pick the single highest-scoring full draft (eval composite + judge rank)."""
        eval_by_id = {e.candidate_id: e for e in evaluations}
        rank_bonus = self._rank_bonuses(judge, successful)

        scored: list[tuple[float, CandidateResponse, dict[str, float]]] = []
        for cand in successful:
            ev = eval_by_id.get(cand.candidate_id)
            composite = float(ev.composite) if ev else 0.0
            bonus = rank_bonus.get(cand.candidate_id, 0.0)
            gate = 0.08 if (ev and ev.passed) else 0.0
            total = composite + bonus + gate
            breakdown = {
                "composite": round(composite, 4),
                "judge_bonus": round(bonus, 4),
                "passed_bonus": round(gate, 4),
                "total": round(total, 4),
            }
            scored.append((total, cand, breakdown))

        scored.sort(key=lambda row: row[0], reverse=True)
        best_score, best, breakdown = scored[0]
        sections = dict(best.sections or section_parser.parse_sections(best.text or ""))
        for key in section_parser.SECTION_KEYS:
            if key not in sections:
                sections[key] = [] if key == "hashtags" else ""

        section_sources = {k: best.candidate_id for k in section_parser.SECTION_KEYS}
        merged_text = (
            best.text.strip()
            if (best.text or "").strip()
            else section_parser.sections_to_json_text(sections)
        )

        leaderboard = [
            {
                "candidate_id": c.candidate_id,
                "provider": c.provider,
                "model": c.model,
                "score": round(s, 4),
                "breakdown": b,
            }
            for s, c, b in scored
        ]
        logger.info(
            "consensus.merge_winner provider=%s model=%s score=%.3f strategy=winner_take_all",
            best.provider,
            best.model,
            best_score,
        )
        return MergeDecision(
            merged_text=merged_text,
            merged_sections=sections,
            section_sources=section_sources,
            strategy="winner_take_all",
            metadata={
                "winner_candidate_id": best.candidate_id,
                "winner_provider": best.provider,
                "winner_model": best.model,
                "winner_score": round(best_score, 4),
                "winner_breakdown": breakdown,
                "leaderboard": leaderboard,
            },
        )

    def _section_best(
        self,
        successful: list[CandidateResponse],
        evaluations: list[EvaluationScore],
        judge: JudgeDecision | None,
    ) -> MergeDecision:
        eval_by_id = {e.candidate_id: e for e in evaluations}
        rank_bonus = self._rank_bonuses(judge, successful)

        merged_sections: dict[str, Any] = {}
        section_sources: dict[str, str] = {}
        section_scores: dict[str, float] = {}

        rules = self._section_rules or [
            {"key": k, "prefer_roles": []}
            for k in section_parser.SECTION_KEYS
        ]

        for rule in rules:
            if not isinstance(rule, dict):
                continue
            key = str(rule.get("key") or "").strip()
            if not key:
                continue
            prefer_roles = [str(r) for r in (rule.get("prefer_roles") or [])]
            best_id = ""
            best_score = float("-inf")
            best_value: Any = None

            for cand in successful:
                score = self._section_candidate_score(
                    cand,
                    key=key,
                    prefer_roles=prefer_roles,
                    evaluation=eval_by_id.get(cand.candidate_id),
                    rank_bonus=rank_bonus.get(cand.candidate_id, 0.0),
                )
                value = (cand.sections or {}).get(key)
                if key == "hashtags":
                    empty = not value or (isinstance(value, list) and len(value) == 0)
                else:
                    empty = not str(value or "").strip()
                if empty:
                    score -= 0.5
                if score > best_score:
                    best_score = score
                    best_id = cand.candidate_id
                    best_value = value

            if best_id:
                if key == "hashtags":
                    merged_sections[key] = (
                        list(best_value)
                        if isinstance(best_value, list)
                        else section_parser.normalize_hashtags(best_value)
                    )
                else:
                    merged_sections[key] = best_value if best_value is not None else ""
                section_sources[key] = best_id
                section_scores[key] = round(best_score, 4)
            else:
                merged_sections[key] = [] if key == "hashtags" else ""

        for key in section_parser.SECTION_KEYS:
            if key not in merged_sections:
                merged_sections[key] = [] if key == "hashtags" else ""

        merged_text = section_parser.sections_to_json_text(merged_sections)
        logger.info(
            "consensus.merge_complete",
            extra={
                "app_module": "consensus",
                "operation": "merge",
                "strategy": "section_best",
                "section_sources": dict(section_sources),
                "outcome": "success",
            },
        )
        return MergeDecision(
            merged_text=merged_text,
            merged_sections=merged_sections,
            section_sources=section_sources,
            strategy="section_best",
            metadata={"section_scores": section_scores},
        )

    def _section_candidate_score(
        self,
        candidate: CandidateResponse,
        *,
        key: str,
        prefer_roles: list[str],
        evaluation: EvaluationScore | None,
        rank_bonus: float,
    ) -> float:
        composite = float(evaluation.composite) if evaluation else 0.0
        role_bonus = 0.0
        roles = self._roles_by_provider.get(candidate.provider.lower(), [])
        for prefer in prefer_roles:
            if prefer in roles:
                role_bonus += 0.12
                break
            # Partial: provider specialist mapping
        specialists = self._providers_cfg.get("specialists") or {}
        if isinstance(specialists, dict):
            for role in prefer_roles:
                if str(specialists.get(role) or "").lower() == candidate.provider.lower():
                    role_bonus += 0.18
                    break

        # Section-specific eval hints
        section_hint = 0.0
        if evaluation:
            scores = evaluation.scores
            if key == "hook":
                section_hint = float(scores.get("hook") or scores.get("hook_quality") or 0.0) * 0.2
            elif key == "cta":
                section_hint = float(scores.get("cta") or scores.get("cta_quality") or 0.0) * 0.2
            elif key == "hashtags":
                section_hint = float(scores.get("hashtags") or 0.0) * 0.2
            elif key == "body":
                section_hint = float(scores.get("readability") or 0.0) * 0.15

        return composite + rank_bonus + role_bonus + section_hint

    def _rank_bonuses(
        self, judge: JudgeDecision | None, candidates: list[CandidateResponse]
    ) -> dict[str, float]:
        bonuses: dict[str, float] = {c.candidate_id: 0.0 for c in candidates}
        if not judge or not judge.rankings:
            return bonuses
        anon_to_id = {
            (c.anonymous_id or c.candidate_id): c.candidate_id for c in candidates
        }
        n = max(len(candidates), 1)
        for item in judge.rankings:
            if not isinstance(item, dict):
                continue
            anon = str(item.get("candidate_id") or "")
            cid = anon_to_id.get(anon) or anon
            try:
                rank = int(item.get("rank") or n)
            except (TypeError, ValueError):
                rank = n
            # Rank 1 gets highest bonus
            bonuses[cid] = max(bonuses.get(cid, 0.0), (n - rank + 1) / n * 0.35)
            try:
                lq = float(item.get("linkedin_quality") or 0.0)
                bonuses[cid] = bonuses.get(cid, 0.0) + max(0.0, min(1.0, lq)) * 0.1
            except (TypeError, ValueError):
                pass
        return bonuses

    def _build_roles_map(self) -> dict[str, list[str]]:
        mapping: dict[str, list[str]] = {}
        for entry in self._providers_cfg.get("panel") or []:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("provider") or "").lower()
            roles = [str(r) for r in (entry.get("roles") or [])]
            if name:
                mapping[name] = roles
        return mapping
