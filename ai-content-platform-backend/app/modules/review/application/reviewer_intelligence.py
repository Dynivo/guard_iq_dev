"""Reviewer intelligence — accuracy, rates, specializations, recommendation score."""

from __future__ import annotations

import uuid
from typing import Any

from app.modules.review.application.config_loader import load_review_config
from app.modules.review.domain.models import ReviewerProfile


class ReviewerIntelligenceEngine:
    def __init__(self, config_dir: str | None = None) -> None:
        self._config = load_review_config(config_dir)
        self._profiles: dict[tuple[uuid.UUID, uuid.UUID], ReviewerProfile] = {}

    def _weights(self) -> dict[str, Any]:
        return (self._config.get("reviewer_intelligence") or {}).get("weights") or {
            "approval_rate": 0.25,
            "rejection_rate": 0.15,
            "review_accuracy": 0.35,
            "specialization_bonus": 0.15,
            "edit_penalty": 0.10,
        }

    def _ri_cfg(self) -> dict[str, Any]:
        return self._config.get("reviewer_intelligence") or {}

    def get_or_create(
        self, org_id: uuid.UUID, reviewer_id: uuid.UUID
    ) -> ReviewerProfile:
        key = (org_id, reviewer_id)
        if key not in self._profiles:
            self._profiles[key] = ReviewerProfile(
                reviewer_id=reviewer_id, organization_id=org_id
            )
        return self._profiles[key]

    def get(
        self, org_id: uuid.UUID, reviewer_id: uuid.UUID
    ) -> ReviewerProfile | None:
        return self._profiles.get((org_id, reviewer_id))

    def list_for_org(self, org_id: uuid.UUID) -> list[ReviewerProfile]:
        return [p for (o, _), p in self._profiles.items() if o == org_id]

    def _recompute(self, profile: ReviewerProfile) -> None:
        total = profile.approvals + profile.rejections
        if total > 0:
            profile.approval_rate = profile.approvals / total
            profile.rejection_rate = profile.rejections / total
        else:
            profile.approval_rate = 0.0
            profile.rejection_rate = 0.0
        if profile.edits > 0:
            profile.average_edit_distance = profile.edit_distance_total / profile.edits
        ri = self._ri_cfg()
        prior_a = float(ri.get("accuracy_prior_approvals") or 0.9)
        prior_r = float(ri.get("accuracy_prior_rejections") or 0.7)
        if total > 0:
            profile.review_accuracy = (
                profile.approvals * prior_a + profile.rejections * prior_r
            ) / total
        else:
            profile.review_accuracy = 0.0
        weights = self._weights()
        scale = float(ri.get("edit_penalty_scale") or 100)
        edit_penalty = min(
            1.0, profile.average_edit_distance / scale if scale else 0.0
        )
        spec_bonus = min(1.0, len(profile.specializations) * 0.2)
        score = (
            float(weights.get("approval_rate") or 0) * profile.approval_rate
            + float(weights.get("rejection_rate") or 0) * (1.0 - profile.rejection_rate)
            + float(weights.get("review_accuracy") or 0) * profile.review_accuracy
            + float(weights.get("specialization_bonus") or 0) * spec_bonus
            - float(weights.get("edit_penalty") or 0) * edit_penalty
        )
        profile.recommendation_score = round(max(0.0, min(1.0, score)), 4)

    def record_approve(
        self,
        org_id: uuid.UUID,
        reviewer_id: uuid.UUID,
        *,
        specializations: list[str] | None = None,
    ) -> ReviewerProfile:
        profile = self.get_or_create(org_id, reviewer_id)
        profile.approvals += 1
        if specializations:
            specs = set(profile.specializations)
            specs.update(specializations)
            profile.specializations = tuple(sorted(specs))
        self._recompute(profile)
        return profile

    def record_reject(
        self,
        org_id: uuid.UUID,
        reviewer_id: uuid.UUID,
        *,
        specializations: list[str] | None = None,
    ) -> ReviewerProfile:
        profile = self.get_or_create(org_id, reviewer_id)
        profile.rejections += 1
        if specializations:
            specs = set(profile.specializations)
            specs.update(specializations)
            profile.specializations = tuple(sorted(specs))
        self._recompute(profile)
        return profile

    def record_edit(
        self,
        org_id: uuid.UUID,
        reviewer_id: uuid.UUID,
        *,
        edit_distance: float,
    ) -> ReviewerProfile:
        profile = self.get_or_create(org_id, reviewer_id)
        profile.edits += 1
        profile.edit_distance_total += float(edit_distance)
        self._recompute(profile)
        return profile
