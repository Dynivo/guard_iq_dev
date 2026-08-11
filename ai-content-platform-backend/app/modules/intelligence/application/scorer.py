"""RelevanceScorer — scores articles against the client profile using AI."""

from __future__ import annotations

import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.ai.application.factory import AIOrchestratorFactory
from app.modules.ai.domain.ports import AIOrchestrator
from app.modules.intelligence.domain.ports import RelevanceResult
from app.modules.intelligence.infrastructure.repositories import PgRelevanceScoreRepository
from app.modules.organization.application.client_profile import load_client_profile
from app.modules.prompts.application.registry import PromptRegistryService

logger = get_logger(__name__)


class RelevanceScorer:
    """Scores article relevance using AI Orchestrator + org brand profile memory."""

    def __init__(
        self,
        session: AsyncSession,
        orchestrator: AIOrchestrator | None = None,
    ) -> None:
        self._session = session
        self._orchestrator = orchestrator or AIOrchestratorFactory.create()
        self._prompt_registry = PromptRegistryService(session)
        self._score_repo = PgRelevanceScoreRepository(session)

    async def _load_relevance_preferences(self, org_id: uuid.UUID) -> str:
        """Pull admin relevance overrides stored as writing preferences."""
        from sqlalchemy import select

        from app.infrastructure.postgres.models.learning import WritingPreference

        rows = (
            await self._session.execute(
                select(WritingPreference.preference)
                .where(
                    WritingPreference.organization_id == org_id,
                    WritingPreference.category == "relevance",
                    WritingPreference.is_active.is_(True),
                )
                .order_by(WritingPreference.updated_at.desc())
                .limit(15)
            )
        ).scalars().all()
        if not rows:
            return ""
        return "\n".join(f"- {p}" for p in rows if p)

    async def score(
        self,
        org_id: uuid.UUID,
        article_id: uuid.UUID,
        title: str,
        summary: str,
        body_text: str = "",
    ) -> RelevanceResult:
        """Score an article and persist the result. Returns parsed RelevanceResult."""
        prompt_data = await self._prompt_registry.get_latest("relevance_scoring")
        if prompt_data is None:
            raise RuntimeError("Relevance scoring prompt not found in registry or YAML")

        client_profile = await load_client_profile(self._session, org_id)
        learned = await self._load_relevance_preferences(org_id)
        if learned:
            client_profile = (
                f"{client_profile}\n\n## Admin relevance preferences (learned)\n{learned}\n"
            )
        rendered = self._prompt_registry.render(prompt_data, {
            "client_profile": client_profile,
            "article_title": title,
            "article_summary": summary or "",
            "article_body": body_text[:3000] if body_text else "",
        })

        from app.core.observability import ensure_correlation_id

        correlation_id = ensure_correlation_id()
        result = await self._orchestrator.complete(
            capability="relevance",
            prompt=rendered,
            correlation_id=correlation_id,
            organization_id=org_id,
        )

        await self._prompt_registry.log_llm_call(
            organization_id=org_id,
            prompt_name="relevance_scoring",
            prompt_version=prompt_data.get("version", "1.0"),
            result=result,
            input_text=rendered[:5000],
            correlation_id=correlation_id,
        )

        parsed = self._parse_response(result.text)

        await self._score_repo.create(
            article_id=article_id,
            organization_id=org_id,
            score=parsed.score,
            sector=parsed.sector,
            framework=parsed.framework,
            audience=parsed.audience,
            angle=parsed.angle,
            reason=parsed.reason,
            prompt_version=prompt_data.get("version", "1.0"),
        )

        return parsed

    def _parse_response(self, text: str) -> RelevanceResult:
        """Parse JSON from the LLM response into a RelevanceResult."""
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            cleaned = text.strip()
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0]
            elif "```" in cleaned:
                cleaned = cleaned.split("```")[1].split("```")[0]
            try:
                data = json.loads(cleaned)
            except json.JSONDecodeError:
                logger.error("Failed to parse relevance response: %s", text[:200])
                return RelevanceResult(
                    score=1,
                    sector=None,
                    framework=None,
                    audience=None,
                    angle=None,
                    reason="Failed to parse LLM response",
                )

        return RelevanceResult(
            score=int(data.get("score", 1)),
            sector=data.get("sector"),
            framework=data.get("framework"),
            audience=data.get("audience"),
            angle=data.get("angle"),
            reason=data.get("reason"),
        )
