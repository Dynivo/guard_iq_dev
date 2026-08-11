"""Partial / full draft regeneration — section PromptRequest → Orchestrator → merge → re-enrich."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import replace
from typing import Any

from app.modules.ai.domain.models import OrchestratorRequest
from app.modules.ai.domain.ports import AIOrchestrator
from app.modules.content.application.generation.engine import DefaultContentGenerationEngine
from app.modules.content.domain.models import (
    DraftSlide,
    DraftVersionSnapshot,
    GenerationRequest,
    RegenSection,
    StructuredDraft,
)
from app.modules.prompts.domain.models import PromptRequest

_SPACING_RULE = (
    "Formatting (required): use short paragraphs separated by a blank line "
    "(double newline). Never return one dense wall of text."
)


def resolve_regen_section(section: str, guidance: str) -> str:
    """If UI sent ``full`` but guidance clearly targets one field, narrow the section."""
    sec = (section or "full").strip().lower() or "full"
    if sec != "full":
        return sec
    g = (guidance or "").strip().lower()
    if not g:
        return "full"

    mentions_hook = bool(
        re.search(r"\b(hook|headline|opening|first line|opener)\b", g)
    )
    mentions_body = bool(
        re.search(r"\b(body|middle|paragraphs?|copy|content)\b", g)
    )
    mentions_cta = bool(
        re.search(r"\b(cta|call to action|closing|ending question)\b", g)
    )
    wants_full = bool(
        re.search(r"\b(whole|full|entire|everything|whole post|rewrite (the )?post)\b", g)
    )
    if wants_full:
        return "full"
    if mentions_hook and not mentions_body and not mentions_cta:
        return "hook"
    if mentions_body and not mentions_hook and not mentions_cta:
        return "body"
    if mentions_cta and not mentions_hook and not mentions_body:
        return "cta"
    return "full"


def linkedin_spacing(text: str) -> str:
    """Normalize body text to LinkedIn-friendly short paragraphs with blank lines."""
    if not text or not str(text).strip():
        return text or ""
    t = str(text).replace("\r\n", "\n").strip()
    t = re.sub(r"\n{3,}", "\n\n", t)

    if "\n\n" in t:
        paras = [p.strip() for p in t.split("\n\n") if p.strip()]
        return "\n\n".join(paras)

    lines = [ln.strip() for ln in t.split("\n") if ln.strip()]
    if len(lines) >= 2:
        return "\n\n".join(lines)

    # Single block — split into 1–2 sentence paragraphs
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z"“‘])', t)
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) <= 1:
        return t
    paras: list[str] = []
    buf: list[str] = []
    for sent in parts:
        buf.append(sent)
        if len(buf) >= 2:
            paras.append(" ".join(buf))
            buf = []
    if buf:
        paras.append(" ".join(buf))
    return "\n\n".join(paras)


class DefaultDraftRegenerator:
    """Regenerate one section or the full post, optionally with client guidance."""

    def __init__(
        self,
        orchestrator: AIOrchestrator,
        engine: DefaultContentGenerationEngine,
    ) -> None:
        self._orch = orchestrator
        self._engine = engine

    async def regenerate(
        self,
        draft: StructuredDraft,
        section: RegenSection | str,
        *,
        prompt_request: PromptRequest | None = None,
        source_text: str = "",
        content_plan: dict[str, Any] | None = None,
        organization_id: uuid.UUID | None = None,
        correlation_id: str = "",
        guidance: str = "",
    ) -> StructuredDraft:
        sec = section.value if isinstance(section, RegenSection) else str(section)
        sec = resolve_regen_section(sec, guidance)
        pr = prompt_request or _section_prompt(
            draft, sec, guidance=guidance, source_text=source_text
        )
        orch = await self._orch.execute(
            OrchestratorRequest(
                capability=pr.capability or "writing",
                prompt=pr.prompt,
                organization_id=organization_id or pr.organization_id,
                correlation_id=correlation_id or pr.correlation_id,
                system_message=pr.system_message,
                response_format=pr.response_format or "json",
                prompt_version=pr.prompt_version,
            )
        )
        if not orch.success or orch.result is None:
            raise RuntimeError(orch.error_message or "section regeneration failed")

        merged = _merge_section(draft, sec, orch.result.text or "")
        req = GenerationRequest(
            prompt_request=pr,
            content_plan_id=draft.content_plan_id,
            content_plan=content_plan or {},
            source_text=source_text,
            organization_id=organization_id,
            correlation_id=correlation_id,
            content_type=draft.content_type,
            format=draft.format,
            context_metadata=_metadata_context(draft),
        )
        enriched = self._engine.enrich_draft(merged, req)
        draft_id = str(
            enriched.metadata.get("draft_id")
            or (draft.metadata or {}).get("draft_id")
            or uuid.uuid4()
        )
        versions = self._engine.lifecycle.list_versions(draft_id)
        next_v = (max((v.version for v in versions), default=0) + 1) if versions else 2
        self._engine.lifecycle.save_version(
            DraftVersionSnapshot(
                draft_id=draft_id,
                version=next_v,
                text=enriched.markdown or enriched.body,
                draft_json=enriched.to_dict(),
                change_summary=f"regenerated:{sec}",
            )
        )
        return replace(
            enriched,
            metadata={
                **enriched.metadata,
                "draft_id": draft_id,
                "regenerated_section": sec,
                "regen_guidance": guidance.strip() or None,
            },
        )


def _section_prompt(
    draft: StructuredDraft,
    section: str,
    *,
    guidance: str = "",
    source_text: str = "",
) -> PromptRequest:
    ctx = (
        f"Hook:\n{draft.hook}\n\n"
        f"Body:\n{draft.body}\n\n"
        f"CTA:\n{draft.cta}\n\n"
        f"Hashtags: {list(draft.hashtags)}"
    )
    guide = f"\n\nClient guidance (must follow): {guidance.strip()}" if guidance.strip() else ""
    knowledge = (
        f"\n\nSource article facts (do not invent beyond this):\n{source_text[:3000]}"
        if source_text
        else ""
    )

    instructions = {
        RegenSection.FULL.value: (
            "Rewrite the full LinkedIn post in the same house style.\n"
            f"{_SPACING_RULE}\n"
            "Return JSON only: "
            '{"hook":"...","body":"...","cta":"...","hashtags":["..."]}\n'
            "Body must contain blank lines between short paragraphs."
        ),
        RegenSection.BODY.value: (
            "Rewrite ONLY the body. Keep the existing hook, CTA, and hashtags unchanged.\n"
            "Do not return hook/cta/hashtags.\n"
            f"{_SPACING_RULE}\n"
            'Return JSON only: {"body":"..."}'
        ),
        RegenSection.HOOK.value: (
            "Rewrite ONLY the LinkedIn hook (opening line).\n"
            "CRITICAL: Do NOT change, rewrite, or return the body, CTA, or hashtags.\n"
            "Return JSON only with a single key: "
            '{"hook":"..."}\n'
            "Hook should be one punchy line (max ~180 characters)."
        ),
        RegenSection.CTA.value: (
            "Rewrite ONLY the CTA. Keep hook/body/hashtags unchanged.\n"
            'Return JSON only: {"cta":"..."}'
        ),
        RegenSection.HASHTAGS.value: (
            'Suggest hashtags only. Return JSON {"hashtags":["..."]}'
        ),
        RegenSection.CAROUSEL.value: (
            'Rewrite carousel slides. Return JSON {"slides":[{"index":1,"title":"...","body":"..."}]}'
        ),
        RegenSection.SUMMARY.value: (
            'Rewrite a short summary of the post. Return JSON {"summary":"..."}'
        ),
    }
    task = instructions.get(section, "Return JSON for the requested section.")
    system = (
        "You are a LinkedIn ghostwriter for a UK security-led IT provider. "
        "UK spelling. Short mobile-friendly paragraphs with a blank line between each. "
        "Ground facts in the source. "
        "When asked to change only one section, change ONLY that section."
    )
    return PromptRequest(
        prompt=f"{task}{guide}{knowledge}\n\nCurrent draft:\n{ctx}",
        system_message=system,
        capability="writing",
        prompt_version="regen-1.2",
        response_format="json",
        schema_id="json",
        valid=True,
    )


def _merge_section(draft: StructuredDraft, section: str, raw_text: str) -> StructuredDraft:
    data = _parse_json(raw_text)
    if section == RegenSection.FULL.value:
        hook = str(data.get("hook") or draft.hook).strip()
        body = linkedin_spacing(str(data.get("body") or data.get("generated_text") or draft.body))
        cta = str(data.get("cta") or draft.cta).strip()
        tags = data.get("hashtags") or draft.hashtags
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.replace(",", " ").split() if t.strip()]
        return replace(
            draft,
            hook=hook,
            body=body,
            cta=cta,
            hashtags=tuple(str(t) for t in tags),
            markdown=f"{hook}\n\n{body}\n\n{cta}",
        )
    if section == RegenSection.BODY.value:
        body = linkedin_spacing(str(data.get("body") or draft.body))
        return replace(
            draft,
            body=body,
            markdown=f"{draft.hook}\n\n{body}\n\n{draft.cta}",
        )
    if section == RegenSection.HOOK.value:
        hook = str(data.get("hook") or draft.hook).strip()
        # Model sometimes dumps the whole post into hook — keep first non-empty line
        if "\n" in hook:
            hook = next((ln.strip() for ln in hook.splitlines() if ln.strip()), hook)
        # Ignore any body/cta the model wrongly included
        return replace(
            draft,
            hook=hook,
            body=draft.body,  # explicitly preserve
            cta=draft.cta,
            hashtags=draft.hashtags,
            markdown=f"{hook}\n\n{draft.body}\n\n{draft.cta}",
        )
    if section == RegenSection.CTA.value:
        cta = str(data.get("cta") or draft.cta).strip()
        return replace(
            draft,
            cta=cta,
            body=draft.body,
            hook=draft.hook,
            markdown=f"{draft.hook}\n\n{draft.body}\n\n{cta}",
        )
    if section == RegenSection.HASHTAGS.value:
        tags = data.get("hashtags") or draft.hashtags
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.replace(",", " ").split() if t.strip()]
        return replace(draft, hashtags=tuple(str(t) for t in tags))
    if section == RegenSection.CAROUSEL.value:
        slides_raw = data.get("slides") or []
        slides = tuple(
            DraftSlide(
                index=int(s.get("index", i + 1)),
                title=str(s.get("title") or ""),
                body=str(s.get("body") or ""),
            )
            for i, s in enumerate(slides_raw)
            if isinstance(s, dict)
        )
        if slides:
            return replace(draft, slides=slides, format="carousel")
        return draft
    if section == RegenSection.SUMMARY.value:
        summary = str(data.get("summary") or data.get("body") or "")
        sections = dict(draft.sections)
        sections["summary"] = summary
        return replace(draft, sections=sections)
    return draft


def _parse_json(text: str) -> dict:
    blob = text.strip()
    try:
        data = json.loads(blob)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        start, end = blob.find("{"), blob.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(blob[start : end + 1])
                return data if isinstance(data, dict) else {}
            except json.JSONDecodeError:
                return {}
        return {}


def _metadata_context(draft: StructuredDraft) -> dict[str, Any]:
    if draft.draft_metadata is not None:
        if hasattr(draft.draft_metadata, "to_dict"):
            return dict(draft.draft_metadata.to_dict())
        if isinstance(draft.draft_metadata, dict):
            return dict(draft.draft_metadata)
    raw = draft.metadata.get("draft_metadata") if draft.metadata else None
    return dict(raw) if isinstance(raw, dict) else {}
