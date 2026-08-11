"""Decision engine — apply YAML approval policies + dynamic rules."""

from __future__ import annotations

from typing import Any

from app.modules.review.application.config_loader import load_review_config
from app.modules.review.domain.models import PolicyEvaluation, ReviewSession


class DecisionEngine:
    def __init__(self, config_dir: str | None = None) -> None:
        self._config = load_review_config(config_dir)

    def _approval(self) -> dict[str, Any]:
        return (self._config.get("policies") or {}).get("approval") or {}

    def _dynamic_rules(self) -> list[dict[str, Any]]:
        return list((self._config.get("policies") or {}).get("dynamic_rules") or [])

    def _transitions(self) -> dict[str, list[str]]:
        return (self._config.get("policies") or {}).get("status_transitions") or {}

    def can_transition(self, current: str, target: str) -> bool:
        allowed = self._transitions().get(current) or []
        return target in allowed

    def resolve_requirements(self, session: ReviewSession) -> dict[str, Any]:
        """Static defaults overridden by first matching dynamic_rule, then template meta."""
        approval = self._approval()
        required = int(approval.get("required_reviewers") or 1)
        quorum = int(approval.get("quorum") or required)
        matched_rule: dict[str, Any] | None = None
        meta = dict(session.metadata or {})

        for rule in self._dynamic_rules():
            when = rule.get("when") or {}
            if not when:
                continue
            if all(str(meta.get(k)) == str(v) for k, v in when.items()):
                req = rule.get("require") or {}
                if req.get("required_reviewers") is not None:
                    required = int(req["required_reviewers"])
                if req.get("quorum") is not None:
                    quorum = int(req["quorum"])
                matched_rule = {"when": when, "require": req}
                break

        # Template overlays only if no dynamic rule matched and template set counts
        if matched_rule is None:
            if meta.get("template_required_reviewers") is not None:
                required = int(meta["template_required_reviewers"])
            if meta.get("template_quorum") is not None:
                quorum = int(meta["template_quorum"])

        return {
            "required_reviewers": required,
            "quorum": quorum,
            "matched_rule": matched_rule,
            "topic": meta.get("topic"),
            "risk": meta.get("risk"),
            "template_id": meta.get("template_id"),
        }

    def evaluate(
        self,
        session: ReviewSession,
        *,
        decision_type: str,
        reviewer_count: int = 0,
        reason_codes: list[str] | None = None,
        categories: list[str] | None = None,
    ) -> PolicyEvaluation:
        approval = self._approval()
        resolved = self.resolve_requirements(session)
        required = int(resolved["required_reviewers"])
        quorum = int(resolved["quorum"])
        reasons: list[str] = []
        allowed = True

        target_map = {
            "approve": "approved",
            "reject": "rejected",
            "edit": "in_review",
            "partial_approve": "partial_approved",
            "needs_changes": "needs_changes",
            "comment": str(session.status),
        }
        target = target_map.get(decision_type, decision_type)
        if decision_type != "comment" and not self.can_transition(str(session.status), target):
            if str(session.status) == "pending" and target in {
                "approved",
                "rejected",
                "needs_changes",
                "partial_approved",
            }:
                if not self.can_transition("in_review", target):
                    allowed = False
                    reasons.append(f"invalid_transition:{session.status}->{target}")
            else:
                allowed = False
                reasons.append(f"invalid_transition:{session.status}->{target}")

        if decision_type in {"approve", "partial_approve"} and reviewer_count < quorum:
            allowed = False
            reasons.append(f"insufficient_reviewers:{reviewer_count}<{quorum}")

        if decision_type == "reject" and approval.get("require_reason_on_reject", True):
            if approval.get("require_reason_codes_on_reject") and not reason_codes:
                allowed = False
                reasons.append("reason_codes_required")

        compliance_ok = True
        if approval.get("compliance_gate_enabled") and decision_type == "approve":
            cats = set(categories or [])
            required_cats = set(approval.get("compliance_required_categories") or [])
            if cats & required_cats and not reason_codes:
                compliance_ok = False
                allowed = False
                reasons.append("compliance_gate")

        auto = bool(approval.get("auto_approve_enabled")) and decision_type == "approve"

        snapshot = {
            "required_reviewers": required,
            "quorum": quorum,
            "decision_type": decision_type,
            "auto_approve_enabled": bool(approval.get("auto_approve_enabled")),
            "mode": approval.get("default_mode") or "manual",
            "dynamic_rule": resolved.get("matched_rule"),
            "topic": resolved.get("topic"),
            "risk": resolved.get("risk"),
            "template_id": resolved.get("template_id"),
        }
        return PolicyEvaluation(
            allowed=allowed,
            reasons=tuple(reasons),
            required_reviewers=required,
            compliance_ok=compliance_ok,
            auto_approve=auto,
            snapshot=snapshot,
        )
