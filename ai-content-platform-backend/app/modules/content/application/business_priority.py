"""Business Priority Engine — org/industry/brand priority signals."""

from __future__ import annotations

from app.modules.content.domain.models import PlannerInput, PlannerPolicy, PrioritySignals


class DefaultBusinessPriorityEngine:
    def score(self, inp: PlannerInput, policy: PlannerPolicy) -> PrioritySignals:
        priorities = dict(policy.priorities or {})
        industry = inp.industry.lower().strip()
        reasons: list[str] = []

        industry_weight = float(priorities.get("industry_default", 0.5))
        industry_map = priorities.get("industries") or {}
        if industry and industry in industry_map:
            industry_weight = float(industry_map[industry])
            reasons.append(f"industry_priority={industry}:{industry_weight}")

        framework_weight = float(priorities.get("frameworks_default", 0.5))
        compliance_weight = float(priorities.get("compliance_default", 0.5))
        brand_weight = float(priorities.get("brand_default", 0.5))

        blob = f"{inp.topic} {inp.context.text[:400] if inp.context.text else ''}".lower()
        if any(x in blob for x in ("compliance", "dspt", "gdpr", "hipaa")):
            compliance_weight = max(
                compliance_weight, float(priorities.get("compliance_boost", 0.8))
            )
            reasons.append("compliance_boost")

        brand = policy.brand_rules or {}
        if brand:
            brand_weight = max(brand_weight, float(priorities.get("brand_boost", 0.7)))
            reasons.append("brand_rules_present")

        preferred_type = None
        type_prefs = priorities.get("preferred_types") or {}
        if industry in type_prefs:
            preferred_type = str(type_prefs[industry])
            reasons.append(f"preferred_type={preferred_type}")
        elif policy.preferred_content_types:
            preferred_type = policy.preferred_content_types[0]

        score = round(
            0.3 * industry_weight
            + 0.25 * compliance_weight
            + 0.25 * brand_weight
            + 0.2 * framework_weight,
            3,
        )
        return PrioritySignals(
            score=score,
            industry_weight=round(industry_weight, 3),
            framework_weight=round(framework_weight, 3),
            compliance_weight=round(compliance_weight, 3),
            brand_weight=round(brand_weight, 3),
            preferred_type=preferred_type,
            reasons=tuple(reasons),
        )
