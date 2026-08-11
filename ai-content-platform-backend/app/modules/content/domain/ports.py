"""Content module ports — planning, strategy, validation, engines."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Protocol

from app.modules.content.domain.models import (
    AudienceProfile,
    CalendarContext,
    ContentPlan,
    DiversityRecommendation,
    DraftDiff,
    DraftValidationResult,
    DraftVersionSnapshot,
    GenerationPolicy,
    GenerationReplayRecord,
    GenerationRequest,
    GenerationResult,
    PlannerInput,
    PlannerPolicy,
    PrioritySignals,
    RawAIOutput,
    RecentContentHistory,
    StrategyDecision,
    StructuredDraft,
    TopicSignals,
    ValidationResult,
)


class PlannerPolicyLoader(Protocol):
    def load(self, policy_id: str = "default") -> PlannerPolicy: ...


class TopicIntelligence(Protocol):
    async def analyze(self, inp: PlannerInput, policy: PlannerPolicy) -> TopicSignals: ...


class AudienceEngine(Protocol):
    def resolve(self, inp: PlannerInput, policy: PlannerPolicy) -> AudienceProfile: ...


class ContentDiversityEngine(Protocol):
    def recommend(
        self,
        inp: PlannerInput,
        policy: PlannerPolicy,
        recent: RecentContentHistory,
    ) -> DiversityRecommendation: ...


class CalendarAwareness(Protocol):
    def snapshot(
        self, org_id: uuid.UUID, now: datetime | None = None
    ) -> CalendarContext: ...


class BusinessPriorityEngine(Protocol):
    def score(self, inp: PlannerInput, policy: PlannerPolicy) -> PrioritySignals: ...


class StrategyEngine(Protocol):
    async def evaluate(
        self, inp: PlannerInput, policy: PlannerPolicy
    ) -> StrategyDecision: ...


class ContentValidator(Protocol):
    def validate(self, plan: ContentPlan, policy: PlannerPolicy) -> ValidationResult: ...


# Compat alias
PlanValidator = ContentValidator


class ContentPlanRepository(Protocol):
    async def save(self, plan: ContentPlan) -> ContentPlan: ...

    async def get_by_id(
        self, org_id: uuid.UUID, plan_id: uuid.UUID
    ) -> ContentPlan | None: ...


class ContentPlanner(Protocol):
    """Assembles candidate ContentPlan — never validates; never calls providers."""

    async def plan(self, inp: PlannerInput) -> ContentPlan: ...

    async def strategy(self, inp: PlannerInput) -> StrategyDecision: ...


class ContentPlanPipeline(Protocol):
    """Planner → ContentValidator → ContentPlan."""

    async def prepare_plan(self, inp: PlannerInput) -> ContentPlan: ...


class ContentGenerator(Protocol):
    async def generate(self, org_id: uuid.UUID, plan: dict) -> dict: ...


class ClaimsGuard(Protocol):
    async def verify(self, org_id: uuid.UUID, text: str) -> dict: ...


class DraftRepository(Protocol):
    async def create(self, draft: dict) -> uuid.UUID: ...

    async def get_by_id(self, draft_id: uuid.UUID) -> dict | None: ...

    async def update(self, draft_id: uuid.UUID, fields: dict) -> None: ...

    async def list_by_org(self, org_id: uuid.UUID, status: str | None = None) -> list[dict]: ...


class ContentGenerationEngine(Protocol):
    async def generate(self, request: GenerationRequest) -> GenerationResult: ...


class OutputParser(Protocol):
    def parse(
        self, raw: RawAIOutput, *, content_type: str = "", format: str = ""
    ) -> StructuredDraft: ...


class ContentDraftValidator(Protocol):
    def validate(
        self, draft: StructuredDraft, policy: GenerationPolicy
    ) -> DraftValidationResult: ...


class FactValidator(Protocol):
    def validate(
        self, draft: StructuredDraft, *, source_text: str = ""
    ) -> DraftValidationResult: ...


class BrandValidator(Protocol):
    def validate(
        self,
        draft: StructuredDraft,
        *,
        policy: GenerationPolicy,
        preferences: dict | None = None,
    ) -> DraftValidationResult: ...


class ToneValidator(Protocol):
    def validate(
        self, draft: StructuredDraft, *, expected_tone: str, profiles: dict
    ) -> DraftValidationResult: ...


class GrammarValidator(Protocol):
    def validate(
        self, draft: StructuredDraft, policy: GenerationPolicy
    ) -> DraftValidationResult: ...


class ContentFormatter(Protocol):
    def format(self, draft: StructuredDraft, *, platform: str = "linkedin") -> StructuredDraft: ...


class DraftLifecycleStore(Protocol):
    def transition(self, draft: StructuredDraft, status: str) -> StructuredDraft: ...

    def save_version(self, snapshot: DraftVersionSnapshot) -> None: ...

    def list_versions(self, draft_id: str) -> list[DraftVersionSnapshot]: ...


class GenerationReplayStore(Protocol):
    def save(self, record: GenerationReplayRecord) -> None: ...

    def get(self, replay_id: str) -> GenerationReplayRecord | None: ...


class DraftDiffService(Protocol):
    def diff(
        self, left: StructuredDraft, right: StructuredDraft, *, left_v: int = 1, right_v: int = 2
    ) -> DraftDiff: ...


class VisualBriefGenerator(Protocol):
    def generate(
        self, draft: StructuredDraft, *, content_plan: dict | None = None
    ) -> Any: ...


class ContentSafetyValidator(Protocol):
    def validate(
        self, draft: StructuredDraft, *, source_text: str = ""
    ) -> Any: ...


class DraftRegenerator(Protocol):
    async def regenerate(
        self,
        draft: StructuredDraft,
        section: str,
        *,
        prompt_request: Any = None,
        source_text: str = "",
        content_plan: dict | None = None,
    ) -> StructuredDraft: ...
