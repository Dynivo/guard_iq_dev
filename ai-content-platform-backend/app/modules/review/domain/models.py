"""Review domain models — sessions, assignments, decisions, queue items."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class ReviewStatus(StrEnum):
    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_CHANGES = "needs_changes"
    ARCHIVED = "archived"
    PARTIAL_APPROVED = "partial_approved"


class ReviewPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class DecisionType(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    EDIT = "edit"
    PARTIAL_APPROVE = "partial_approve"
    NEEDS_CHANGES = "needs_changes"
    COMMENT = "comment"


class FeedbackCategory(StrEnum):
    WRITING = "writing"
    VISUAL = "visual"
    TYPOGRAPHY = "typography"
    BRAND = "brand"
    COMPLIANCE = "compliance"
    FACT = "fact"
    TONE = "tone"
    GENERAL = "general"


@dataclass(slots=True)
class ReviewVersionRef:
    kind: str  # original | edited | approved | published
    text: str | None = None
    draft_id: str | None = None
    version_id: str | None = None
    created_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "text": self.text,
            "draft_id": self.draft_id,
            "version_id": self.version_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewVersionRef:
        return cls(
            kind=str(data.get("kind") or "original"),
            text=data.get("text"),
            draft_id=data.get("draft_id"),
            version_id=data.get("version_id"),
            created_at=data.get("created_at"),
        )


@dataclass(slots=True)
class ReviewComment:
    id: UUID
    session_id: UUID
    author_id: UUID
    body: str
    created_at: datetime | None = None
    parent_id: UUID | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "session_id": str(self.session_id),
            "author_id": str(self.author_id),
            "body": self.body,
            "parent_id": str(self.parent_id) if self.parent_id else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass(slots=True)
class ReviewAssignment:
    id: UUID
    session_id: UUID
    reviewer_id: UUID
    role: str = "reviewer"
    status: str = "pending"
    escalated: bool = False
    assigned_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "session_id": str(self.session_id),
            "reviewer_id": str(self.reviewer_id),
            "role": self.role,
            "status": self.status,
            "escalated": self.escalated,
            "assigned_at": self.assigned_at.isoformat() if self.assigned_at else None,
        }


@dataclass(slots=True)
class ReviewDecision:
    id: UUID
    session_id: UUID
    decision_type: DecisionType
    actor_id: UUID
    reason: str | None = None
    reason_codes: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    policy_snapshot: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "session_id": str(self.session_id),
            "decision_type": str(self.decision_type),
            "actor_id": str(self.actor_id),
            "reason": self.reason,
            "reason_codes": list(self.reason_codes),
            "categories": list(self.categories),
            "policy_snapshot": dict(self.policy_snapshot),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass(slots=True)
class ReviewSession:
    id: UUID
    organization_id: UUID
    draft_id: UUID
    status: ReviewStatus = ReviewStatus.PENDING
    priority: ReviewPriority = ReviewPriority.NORMAL
    content_type: str = "linkedin_post"
    due_date: datetime | None = None
    title: str | None = None
    version_refs: tuple[ReviewVersionRef, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "draft_id": str(self.draft_id),
            "status": str(self.status),
            "priority": str(self.priority),
            "content_type": self.content_type,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "title": self.title,
            "version_refs": [v.to_dict() for v in self.version_refs],
            "metadata": dict(self.metadata),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewSession:
        from uuid import UUID as _UUID

        refs = tuple(
            ReviewVersionRef.from_dict(x)
            for x in (data.get("version_refs") or [])
            if isinstance(x, dict)
        )
        due = data.get("due_date")
        return cls(
            id=_UUID(str(data["id"])),
            organization_id=_UUID(str(data["organization_id"])),
            draft_id=_UUID(str(data["draft_id"])),
            status=ReviewStatus(str(data.get("status") or ReviewStatus.PENDING)),
            priority=ReviewPriority(str(data.get("priority") or ReviewPriority.NORMAL)),
            content_type=str(data.get("content_type") or "linkedin_post"),
            due_date=datetime.fromisoformat(due) if isinstance(due, str) else due,
            title=data.get("title"),
            version_refs=refs,
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(slots=True)
class ReviewQueueItem:
    session: ReviewSession
    assignee_ids: tuple[UUID, ...] = ()
    comment_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.session.to_dict(),
            "assignee_ids": [str(a) for a in self.assignee_ids],
            "comment_count": self.comment_count,
        }


@dataclass(slots=True)
class PolicyEvaluation:
    allowed: bool
    reasons: tuple[str, ...] = ()
    required_reviewers: int = 1
    compliance_ok: bool = True
    auto_approve: bool = False
    snapshot: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reasons": list(self.reasons),
            "required_reviewers": self.required_reviewers,
            "compliance_ok": self.compliance_ok,
            "auto_approve": self.auto_approve,
            "snapshot": dict(self.snapshot),
        }


@dataclass(slots=True)
class ReviewerProfile:
    reviewer_id: UUID
    organization_id: UUID
    review_accuracy: float = 0.0
    average_edit_distance: float = 0.0
    approval_rate: float = 0.0
    rejection_rate: float = 0.0
    specializations: tuple[str, ...] = ()
    recommendation_score: float = 0.0
    approvals: int = 0
    rejections: int = 0
    edits: int = 0
    edit_distance_total: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "reviewer_id": str(self.reviewer_id),
            "organization_id": str(self.organization_id),
            "review_accuracy": self.review_accuracy,
            "average_edit_distance": self.average_edit_distance,
            "approval_rate": self.approval_rate,
            "rejection_rate": self.rejection_rate,
            "specializations": list(self.specializations),
            "recommendation_score": self.recommendation_score,
            "approvals": self.approvals,
            "rejections": self.rejections,
            "edits": self.edits,
            "edit_distance_total": self.edit_distance_total,
        }
