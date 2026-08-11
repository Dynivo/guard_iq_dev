"""Content formatter — LinkedIn / carousel / markdown envelopes."""

from __future__ import annotations

from dataclasses import replace

from app.modules.content.domain.models import (
    ContentFormat,
    DraftLifecycleStatus,
    StructuredDraft,
)


class DefaultContentFormatter:
    def format(self, draft: StructuredDraft, *, platform: str = "linkedin") -> StructuredDraft:
        from app.modules.content.application.generation.regenerator import linkedin_spacing

        if draft.format == ContentFormat.CAROUSEL.value and draft.slides:
            md_parts = [f"## Slide {s.index}: {s.title}\n{s.body}".strip() for s in draft.slides]
            markdown = "\n\n".join(md_parts)
            body = draft.body or "\n\n".join(
                f"{s.title}\n{s.body}".strip() for s in draft.slides
            )
        else:
            body = linkedin_spacing(draft.body or "")
            tags = " ".join(
                t if t.startswith("#") else f"#{t}" for t in draft.hashtags
            )
            parts = [p for p in (draft.hook, body, draft.cta, tags) if p]
            markdown = "\n\n".join(parts)

        platform_key = platform if platform in {"linkedin", "markdown", "carousel"} else "linkedin"
        return replace(
            draft,
            body=body,
            markdown=markdown,
            platform=platform_key if platform_key != "carousel" else "linkedin",
            lifecycle_status=DraftLifecycleStatus.FORMATTED.value,
            metadata={**draft.metadata, "formatted_platform": platform},
        )
