"""Visual Story Engine — turn message + pattern into a 2-second visual narrative."""

from __future__ import annotations

from typing import Any


def build_visual_story(
    *,
    pattern: dict[str, Any],
    message: dict[str, Any],
    short_labels: str = "",
) -> dict[str, Any]:
    """Produce story beats and a prompt-ready narrative clause."""
    beats = list(pattern.get("story_beats") or [])
    if not beats:
        beats = [
            "Headline-safe top band",
            "One clear diagram metaphor",
            "Focused outcome / takeaway",
        ]
    labels = [x.strip() for x in (short_labels or "").split(";") if x.strip()]
    primary = str(message.get("primary_message") or "")
    takeaway = str(message.get("key_takeaway") or "")
    value = str(message.get("business_value") or "")
    pain = str(message.get("pain_point") or "")

    narrative = (
        f"Visual story (readable in under 2 seconds): "
        f"Theme — {primary or value}. "
        f"Conflict — {pain}. "
        f"Resolution — {takeaway or value}. "
        f"Beats: {' → '.join(str(b) for b in beats)}. "
    )
    if labels:
        narrative += f"Card/node labels (exact short English): {'; '.join(labels[:4])}. "

    focus = str(pattern.get("prompt_focus") or pattern.get("usage") or "")
    hierarchy = str(pattern.get("visual_hierarchy") or "top → middle → bottom")
    return {
        "beats": beats,
        "narrative": narrative.strip(),
        "prompt_focus": focus,
        "visual_hierarchy": hierarchy,
        "two_second_test": (
            "A busy LinkedIn scroller must grasp the idea without reading the post body."
        ),
    }
