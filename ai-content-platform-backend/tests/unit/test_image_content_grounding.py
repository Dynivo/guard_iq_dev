"""Unit tests for content-grounded image subjects, brand palette prompts, gallery dedupe."""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.image.application.content_subject import (
    build_content_subject,
    inject_content_into_brief,
)
from app.modules.image.application.gallery_assets import (
    media_belongs_to_jobs,
    select_gallery_media,
)
from app.modules.image.application.prompt_builder import (
    DefaultImagePromptBuilder,
    resolve_brand_palette,
)
from app.modules.image.domain.models import CompositionPlan, EnrichedVisualBrief, ScenePlan


@dataclass
class _Row:
    object_key: str
    label: str = ""


def test_select_gallery_prefers_optimized_per_job() -> None:
    org = "org-1"
    job = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    rows = [
        _Row(f"{org}/images/{job}/original.png", "orig"),
        _Row(f"{org}/images/{job}/optimized.png", "opt"),
    ]
    out = select_gallery_media(rows)
    assert len(out) == 1
    assert out[0].label == "opt"


def test_select_gallery_keeps_distinct_jobs() -> None:
    org = "org-1"
    j1 = "11111111-1111-1111-1111-111111111111"
    j2 = "22222222-2222-2222-2222-222222222222"
    rows = [
        _Row(f"{org}/images/{j1}/optimized.png", "a"),
        _Row(f"{org}/images/{j2}/optimized.png", "b"),
    ]
    out = select_gallery_media(rows)
    assert [r.label for r in out] == ["a", "b"]


def test_media_belongs_to_jobs() -> None:
    jid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert media_belongs_to_jobs(f"org/images/{jid}/optimized.png", {jid})
    assert not media_belongs_to_jobs(f"org/images/{jid}/optimized.png", {"other"})


def test_body_bullets_drive_connected_or_process_visual() -> None:
    subject = build_content_subject(
        hook="Could AI be your next security threat?",
        body=(
            "Recent tests revealed AI agents creating fake identities.\n"
            "- robust authentication\n"
            "- AI-driven scans\n"
            "- cybersecurity protocols\n"
            "Teams need layered defenses."
        ),
    )
    assert subject["visual_mode"] in {"connected_nodes", "process_pictogram", "flow_nodes"}
    assert subject["short_labels"]
    assert "floating" in subject["visual_elements"].lower() or "NOT" in subject["must_depict"]


def test_thirty_four_malware_uses_big_stat_layout() -> None:
    subject = build_content_subject(
        hook="What if 34 hidden threats were lurking in your practice's essential software?",
        body=(
            "We recently helped a client uncover 34 instances of malware embedded deep "
            "within their operational codebase. These weren't obvious threats; they were "
            "quiet, persistent risks to their data and systems. "
            "For regulated practices in care, legal, or accountancy, undetected malware "
            "can mean data breaches and serious compliance issues."
        ),
        content_type="educational",
    )
    assert subject["visual_mode"] == "big_stat"
    assert "34" in subject["stat_hints"] or "34" in subject["must_depict"]
    assert "infographic" in subject["must_depict"].lower() or "STAT" in subject["must_depict"]
    assert "portrait" in subject["must_depict"].lower() or "floating" in subject["must_depict"].lower()


def test_azure_vuln_uses_access_control_layout() -> None:
    subject = build_content_subject(
        hook="Ignoring the latest Azure vulnerability could expose your practice to serious risk.",
        body=(
            "The recent CVE-2026-35425 vulnerability in Azure API Management allows an "
            "authorized attacker to execute code over a network due to improper access control."
        ),
    )
    assert subject["visual_mode"] == "access_control"


def test_lawsuit_uses_legal_context_not_cyber_portrait() -> None:
    subject = build_content_subject(
        hook="A significant tech company is now facing a class action lawsuit.",
        body=(
            "Rosen Law Firm has announced a class action lawsuit targeting Rackspace. "
            "This isn't about IT security, but it's a reminder that understanding key partners "
            "is part of robust business management."
        ),
    )
    assert subject["visual_mode"] == "legal_context"
    assert subject["short_labels"] == "Legal landscape; Due diligence; Key providers"
    assert "three equal" in subject["must_depict"].lower() or "EXACTLY three" in subject["must_depict"]
    assert "mind-map" in subject["must_depict"].lower()
    assert "angry" in subject["must_depict"].lower() or "courtroom" in subject["must_depict"].lower()
    assert "Distributor" not in subject["short_labels"]


def test_inject_brief_sets_educational_infographic_for_body_layout() -> None:
    brief = inject_content_into_brief(
        {},
        hook="Could AI be your next security threat?",
        body=(
            "Step 1: verify identity\n"
            "Step 2: scan agents\n"
            "Step 3: harden protocols\n"
        ),
    )
    assert brief["illustration_style"] == "educational_infographic"
    assert brief["metadata"]["content_grounded"] is True
    assert brief["metadata"]["text_in_image"] is True
    assert brief["metadata"]["visual_mode"]
    assert "neon" in brief["negative_prompt"].lower() or "portrait" in brief["negative_prompt"].lower()


def test_noise_filter_post_does_not_depict_foreign_gun_news() -> None:
    subject = build_content_subject(
        hook="Not every headline impacts your practice.",
        body=(
            "We're constantly sifting through global news to find what genuinely matters "
            "for UK care, legal, and accountancy practices. "
            "Today, we saw an appeals court in Texas rejected an effort to overturn a gun ban "
            "at the State Fair. This followed a shooting there in 2024. "
            "While significant news in its own context, this specific legal decision in the US "
            "doesn't directly affect the IT security of your business here in the UK. "
            "What does matter? The latest CQC guidance and SRA updates."
        ),
        content_type="educational",
    )
    assert subject["style_note"] == "signal_vs_noise"
    assert "texas" not in subject["must_depict"].lower() or "DO NOT" in subject["must_depict"]
    assert "gun" not in subject["must_depict"].lower() or "DO NOT" in subject["must_depict"]


def test_prompt_builder_injects_brand_kit_hexes() -> None:
    builder = DefaultImagePromptBuilder()
    brief = EnrichedVisualBrief(
        illustration_style="educational_infographic",
        theme="professional",
        purpose="educate",
        audience="uk",
        visual_tone="calm",
        typography_safe_area="bottom_third",
        negative_prompt="neon cyberpunk glow, black void background",
        color_palette=("#111111",),
        brand_direction="",
        image_intent="inform",
        scene_hint="clean educational infographic",
        metadata={
            "content_subject": "UK compliance focus",
            "must_depict": "stat callout",
            "short_labels": "34 threats; Detect; Resolve",
            "text_in_image": True,
        },
    )
    scene = ScenePlan(
        layout="educational_infographic",
        foreground=("infographic",),
        background=("soft_off_white",),
        icons=("shield",),
    )
    composition = CompositionPlan(
        width=1080, height=1080, balance="centered", camera="eye", focus="subject"
    )
    brand = {
        "name": "Guard IQ",
        "primary_color": "#0A1F2B",
        "secondary_color": "#FFFFFF",
        "accent_color": "#1A5CB0",
    }
    req = builder.build(brief, scene, composition, brand=brand)
    assert "#0A1F2B" in req.positive_prompt
    assert "#1A5CB0" in req.positive_prompt
    assert "INFOGRAPHIC" in req.positive_prompt.upper() or "infographic" in req.positive_prompt.lower()
    assert "34 threats" in req.positive_prompt
    assert req.parameters["palette"][0] == "#0A1F2B"
    assert req.metadata["text_in_image"] is True


def test_resolve_brand_palette_prefers_kit() -> None:
    colours = resolve_brand_palette(
        {"primary_color": "#0A1F2B", "accent_color": "#1A5CB0"},
        ("#0B3D5C",),
    )
    assert colours[0] == "#0A1F2B"
    assert "#1A5CB0" in colours
