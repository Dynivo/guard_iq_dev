"""Audience Engine — resolve audience with confidence and hierarchy."""

from __future__ import annotations

from app.modules.content.domain.models import (
    Audience,
    AudienceProfile,
    PlannerInput,
    PlannerPolicy,
)

_INDUSTRY_MAP = {
    "healthcare": Audience.HEALTHCARE,
    "health": Audience.HEALTHCARE,
    "finance": Audience.FINANCE,
    "fintech": Audience.FINANCE,
    "legal": Audience.BUSINESS_OWNERS,  # future Legal → metadata
    "retail": Audience.SMBS,
    "enterprise": Audience.ENTERPRISE,
    "smb": Audience.SMBS,
    "developer": Audience.DEVELOPERS,
    "engineering": Audience.DEVELOPERS,
    "executive": Audience.EXECUTIVES,
}

_HIERARCHY = {
    Audience.HEALTHCARE: (Audience.HEALTHCARE.value, Audience.BUSINESS_OWNERS.value),
    Audience.FINANCE: (Audience.FINANCE.value, Audience.ENTERPRISE.value),
    Audience.SECURITY_TEAMS: (Audience.SECURITY_TEAMS.value, Audience.IT_MANAGERS.value),
    Audience.DEVELOPERS: (Audience.DEVELOPERS.value, Audience.IT_MANAGERS.value),
    Audience.EXECUTIVES: (Audience.EXECUTIVES.value, Audience.ENTERPRISE.value),
    Audience.SMBS: (Audience.SMBS.value, Audience.BUSINESS_OWNERS.value),
}


class DefaultAudienceEngine:
    def resolve(self, inp: PlannerInput, policy: PlannerPolicy) -> AudienceProfile:
        metadata: dict = {"future_segments": ["legal", "retail"]}
        hint = (inp.target_audience_hint or "").lower().replace(" ", "_")
        industry = inp.industry.lower().strip()

        if hint:
            try:
                primary = Audience(hint)
                return AudienceProfile(
                    primary=primary,
                    confidence=0.9,
                    hierarchy=_HIERARCHY.get(primary, (primary.value,)),
                    metadata={**metadata, "source": "hint"},
                )
            except ValueError:
                pass

        if industry in _INDUSTRY_MAP:
            primary = _INDUSTRY_MAP[industry]
            return AudienceProfile(
                primary=primary,
                confidence=0.85,
                hierarchy=_HIERARCHY.get(primary, (primary.value,)),
                metadata={
                    **metadata,
                    "source": "industry",
                    "industry": industry,
                    "segment_hint": industry,
                },
            )

        industry_rules = policy.industry_rules or {}
        if industry in industry_rules:
            pref = str(industry_rules[industry].get("preferred_audience") or "")
            try:
                primary = Audience(pref)
                return AudienceProfile(
                    primary=primary,
                    confidence=0.8,
                    hierarchy=_HIERARCHY.get(primary, (primary.value,)),
                    metadata={**metadata, "source": "industry_rules"},
                )
            except ValueError:
                pass

        if policy.preferred_audiences:
            try:
                primary = Audience(policy.preferred_audiences[0])
                return AudienceProfile(
                    primary=primary,
                    confidence=0.65,
                    hierarchy=_HIERARCHY.get(primary, (primary.value,)),
                    metadata={**metadata, "source": "preferred_audiences"},
                )
            except ValueError:
                pass

        try:
            primary = Audience(policy.default_audience)
        except ValueError:
            primary = Audience.BUSINESS_OWNERS
        return AudienceProfile(
            primary=primary,
            confidence=0.5,
            hierarchy=_HIERARCHY.get(primary, (primary.value,)),
            metadata={**metadata, "source": "default"},
        )
