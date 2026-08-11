"""ContentGenerator — bridges article/API path to Content Generation Engine via PromptRequest.

Prompt composition uses Prompt Builder (or an explicit PromptRequest). This class never
calls vendor SDKs and does not embed generation validation logic.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.infrastructure.postgres.models.intelligence import RelevanceScore
from app.infrastructure.postgres.models.learning import Example, Rule
from app.modules.ai.application.factory import AIOrchestratorFactory
from app.modules.ai.domain.ports import AIOrchestrator
from app.modules.content.application.generation.engine import DefaultContentGenerationEngine
from app.modules.content.domain.models import GenerationRequest
from app.modules.organization.application.client_profile import load_client_profile
from app.modules.prompts.application.factory import PromptBuilderFactory
from app.modules.prompts.domain.models import PromptBuildInput, PromptRequest

logger = get_logger(__name__)

_CONTENT_DIR = Path(__file__).resolve().parents[4] / "configs" / "content"


def _load_viral_style_guide() -> tuple[str, str, str]:
    """Return (guide_text, hook_style_instruction, cta_style)."""
    import random

    import yaml

    path = _CONTENT_DIR / "linkedin_viral_style.yaml"
    if not path.exists():
        return (
            "Write a scroll-stopping LinkedIn post with a strong hook and short paragraphs.",
            "pattern interrupt hook",
            "Ask a specific opinion question.",
        )
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    hooks = raw.get("hook_styles") or []
    ctas = raw.get("cta_styles") or []
    body = str(raw.get("body_structure") or "").strip()
    hashtags = raw.get("hashtag_rules") or []
    visual = str(raw.get("visual_direction") or "").strip()
    hook = random.choice(hooks) if hooks else {"instruction": "strong hook"}
    cta = random.choice(ctas) if ctas else "Invite a comment."
    guide = "\n".join(
        [
            body,
            "Hashtags: " + "; ".join(str(h) for h in hashtags),
            visual,
        ]
    ).strip()
    hook_instr = str(hook.get("instruction") or hook) if isinstance(hook, dict) else str(hook)
    cta_instr = str(cta)
    return guide, hook_instr, cta_instr


class ContentGenerator:
    """Produces draft dicts via Prompt Builder → Content Generation Engine → Orchestrator."""

    def __init__(
        self,
        session: AsyncSession,
        orchestrator: AIOrchestrator | None = None,
        engine: DefaultContentGenerationEngine | None = None,
    ) -> None:
        self._session = session
        self._orchestrator = orchestrator or AIOrchestratorFactory.create()
        if engine is not None:
            self._engine = engine
        else:
            consensus = None
            from app.core.config import get_settings

            if get_settings().CONSENSUS_ENABLED:
                from app.modules.consensus.application.factory import ConsensusEngineFactory

                consensus = ConsensusEngineFactory.create(orchestrator=self._orchestrator)
            self._engine = DefaultContentGenerationEngine(
                self._orchestrator, consensus_engine=consensus
            )
        self._prompt_builder = PromptBuilderFactory.create_memory()

    async def _load_examples(self, org_id: uuid.UUID) -> str:
        stmt = (
            select(Example)
            .where(Example.organization_id == org_id, Example.is_active.is_(True))
            .order_by(Example.weight.desc())
            .limit(5)
        )
        result = await self._session.execute(stmt)
        examples = list(result.scalars().all())
        seeded = ""
        seed_path = _CONTENT_DIR / "client_post_examples.md"
        if seed_path.exists():
            seeded = seed_path.read_text(encoding="utf-8").strip()
        if not examples:
            return seeded or "No approved examples available yet."
        learned = "\n---\n".join(f"Hook: {e.hook or 'N/A'}\n{e.text}" for e in examples)
        if seeded:
            return f"{seeded}\n\n---\nLearned org examples:\n{learned}"
        return learned

    async def _load_rules(self, org_id: uuid.UUID) -> str:
        stmt = (
            select(Rule)
            .where(Rule.organization_id == org_id, Rule.is_active.is_(True))
            .order_by(Rule.priority.desc())
            .limit(20)
        )
        result = await self._session.execute(stmt)
        rules = list(result.scalars().all())
        if not rules:
            return "No specific rules configured yet."
        return "\n".join(f"- [{r.category}] {r.text}" for r in rules)

    async def _get_relevance_angle(
        self, article_id: uuid.UUID, *, title: str = "", category: str = ""
    ) -> tuple[str, str]:
        stmt = (
            select(RelevanceScore)
            .where(RelevanceScore.article_id == article_id)
            .order_by(RelevanceScore.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        score = result.scalar_one_or_none()
        if score and (score.angle or score.sector):
            return (
                score.angle or f"Insight on: {title[:120]}",
                score.sector or (category or "cross-sector"),
            )
        # No score yet — derive from the article itself (do not invent a cyber angle).
        return (
            f"LinkedIn insight grounded in: {title[:160]}" if title else "Industry news insight",
            category or "cross-sector",
        )

    async def generate_from_prompt_request(
        self,
        prompt_request: PromptRequest,
        *,
        source_text: str = "",
        content_type: str = "educational",
        content_plan_id: str = "",
        organization_id: uuid.UUID | None = None,
        correlation_id: str = "",
    ) -> dict:
        """Primary M9 entry: PromptRequest → StructuredDraft (validated)."""
        result = await self._engine.generate(
            GenerationRequest(
                prompt_request=prompt_request,
                content_plan_id=content_plan_id,
                source_text=source_text,
                organization_id=organization_id,
                correlation_id=correlation_id,
                content_type=content_type,
            )
        )
        if not result.success or result.draft is None:
            logger.warning(
                "Content generation rejected: %s",
                "; ".join(result.errors),
            )
            # Still return structured fields for API diagnostics; caller decides persist
            return {
                "hook": result.draft.hook if result.draft else "",
                "body": result.draft.body if result.draft else "",
                "cta": result.draft.cta if result.draft else "",
                "hashtags": list(result.draft.hashtags) if result.draft else [],
                "variations": [],
                "validation_passed": False,
                "errors": list(result.errors),
                "draft": result.draft.to_dict() if result.draft else None,
                "metrics": result.metrics,
                "replay_id": result.replay_id,
            }
        d = result.draft
        return {
            "hook": d.hook,
            "body": d.body,
            "cta": d.cta,
            "hashtags": list(d.hashtags),
            "variations": [],
            "validation_passed": True,
            "errors": [],
            "draft": d.to_dict(),
            "metrics": result.metrics,
            "replay_id": result.replay_id,
            "markdown": d.markdown,
            "quality_score": d.quality_score,
            "confidence_score": d.confidence_score,
        }

    async def generate(
        self,
        *,
        org_id: uuid.UUID,
        article_id: uuid.UUID,
        title: str,
        summary: str,
        body_text: str = "",
        content_type: str = "educational",
        prompt_request: PromptRequest | None = None,
        content_plan_id: str = "",
    ) -> dict:
        """Article path: Prompt Builder → Content Generation Engine."""
        source_text = f"{title}\n{summary}\n{body_text}"
        if prompt_request is None:
            client_profile = await load_client_profile(self._session, org_id)
            examples = await self._load_examples(org_id)
            rules = await self._load_rules(org_id)
            angle, sector = await self._get_relevance_angle(article_id, title=title)
            viral_guide, hook_style, cta_style = _load_viral_style_guide()
            brand_text = (
                "Brand voice (tone/style/audience only — do NOT invent unrelated topics):\n"
                f"{client_profile}"
            )
            prompt_request = await self._prompt_builder.build(
                PromptBuildInput(
                    capability="writing_from_plan",
                    organization_id=org_id,
                    prompt_name="writing_from_plan",
                    knowledge_text=source_text[:4000],
                    brand_text=brand_text,
                    rules_text=rules,
                    examples_text=examples,
                    planner_json={
                        "topic": title,
                        "content_type": content_type,
                        "angle": angle,
                        "sector": sector,
                        "summary": summary,
                        "hook_style": hook_style,
                        "cta_style": cta_style,
                    },
                    variables={
                        "task": (
                            f"Write a scroll-stopping LinkedIn {content_type} post "
                            f"in the client's house style (see examples).\n"
                            f"Article title: {title}\n"
                            f"Suggested angle (tone only — facts still from article): {angle}\n"
                            f"Sector lens: {sector}\n"
                            f"Hook style to use: {hook_style}\n"
                            f"CTA style to use: {cta_style}\n"
                            f"Match example rhythm: punchy hook, short lines, plain English, "
                            f"practical takeaway for a non-technical practice manager.\n"
                            f"Formatting: short paragraphs separated by a blank line "
                            f"(never one dense wall of text).\n"
                            f"Ground EVERY fact in the article knowledge. Do not invent cyber "
                            f"incidents unless the article is about security.\n"
                            f"Return JSON with ALL keys required: "
                            f'{{"hook":"...","body":"...","cta":"...","hashtags":["#..."]}}. '
                            f"cta must be a short engagement question (never empty)."
                        ),
                        "topic": title,
                        "content_type": content_type,
                        "angle": angle,
                        "article_summary": summary or "",
                        "hook_style": hook_style,
                        "cta_style": cta_style,
                        "viral_style": viral_guide,
                    },
                    response_format="json",
                    schema_id="json",
                )
            )
        return await self.generate_from_prompt_request(
            prompt_request,
            source_text=source_text,
            content_type=content_type,
            content_plan_id=content_plan_id,
            organization_id=org_id,
        )

    async def generate_from_capture(
        self,
        *,
        org_id: uuid.UUID,
        content_type: str,
        title: str,
        story: str,
        follow_up_answers: dict[str, str] | None = None,
    ) -> dict:
        """Capture path: brand profile + success/achievement story → StructuredDraft."""
        answers = follow_up_answers or {}
        answer_lines = "\n".join(f"- {k}: {v}" for k, v in answers.items() if v)
        knowledge = (
            f"Title: {title or '(none)'}\n\nStory:\n{story}\n\n"
            f"Follow-up answers:\n{answer_lines or '(none)'}"
        )
        client_profile = await load_client_profile(self._session, org_id)
        examples = await self._load_examples(org_id)
        rules = await self._load_rules(org_id)
        viral_guide, hook_style, cta_style = _load_viral_style_guide()
        brand_text = (
            "Brand voice (tone/style/audience only — do NOT invent unrelated topics):\n"
            f"{client_profile}"
        )
        type_label = {
            "success_story": "success story / case study",
            "personal_achievement": "personal achievement",
            "educational": "educational",
        }.get(content_type, content_type)
        angle = (
            "First-person practitioner story with a clear lesson"
            if content_type == "personal_achievement"
            else "Client outcome story: believed problem → real problem → result → lesson"
        )
        prompt_request = await self._prompt_builder.build(
            PromptBuildInput(
                capability="writing_from_plan",
                organization_id=org_id,
                prompt_name="writing_from_capture",
                knowledge_text=knowledge[:4000],
                brand_text=brand_text,
                rules_text=rules,
                examples_text=examples,
                planner_json={
                    "topic": title or story[:120],
                    "content_type": content_type,
                    "angle": angle,
                    "sector": "client_capture",
                    "summary": story[:500],
                    "hook_style": hook_style,
                    "cta_style": cta_style,
                },
                variables={
                    "task": (
                        f"Write a scroll-stopping LinkedIn {type_label} post "
                        f"in the client's house style (see examples).\n"
                        f"Ground EVERY fact in the capture story and follow-up answers. "
                        f"Do not invent metrics, client names, or incidents.\n"
                        f"Respect 'not_public' / privacy answers — omit or anonymize.\n"
                        f"Angle: {angle}\n"
                        f"Hook style: {hook_style}\n"
                        f"CTA style: {cta_style}\n"
                        f"Formatting: short paragraphs separated by a blank line.\n"
                        f"Return JSON with ALL keys required: "
                        f'{{"hook":"...","body":"...","cta":"...","hashtags":["#..."]}}. '
                        f"cta must be a short engagement question (never empty)."
                    ),
                    "topic": title or story[:120],
                    "content_type": content_type,
                    "angle": angle,
                    "article_summary": story[:500],
                    "hook_style": hook_style,
                    "cta_style": cta_style,
                    "viral_style": viral_guide,
                },
                response_format="json",
                schema_id="json",
            )
        )
        return await self.generate_from_prompt_request(
            prompt_request,
            source_text=knowledge,
            content_type=content_type,
            organization_id=org_id,
        )
