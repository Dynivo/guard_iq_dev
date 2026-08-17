"""Reference image policy for Gemini generation (logo / brand style / previous)."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from app.modules.image.application.config_loader import load_yaml


@lru_cache(maxsize=1)
def _policy_cfg() -> dict[str, Any]:
    return load_yaml("reference_policy.yaml")


@dataclass(slots=True)
class ReferenceImage:
    role: str
    data: bytes
    mime_type: str = "image/png"
    prompt_hint: str = ""

    def to_provider_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "bytes": self.data,
            "mime_type": self.mime_type,
            "prompt_hint": self.prompt_hint,
        }


@dataclass(slots=True)
class ReferenceBundle:
    images: list[ReferenceImage] = field(default_factory=list)
    logo_as_reference: bool = False
    stamp_policy: dict[str, Any] = field(default_factory=dict)

    def provider_references(self) -> list[dict[str, Any]]:
        return [img.to_provider_dict() for img in self.images]


class ReferenceImagePolicy:
    """Resolve which reference images to send — never invent paths."""

    def resolve(
        self,
        *,
        mode: str | None = "auto",
        include_logo: bool = True,
        logo_bytes: bytes | None = None,
        brand: dict[str, Any] | None = None,
        brand_style_bytes: bytes | None = None,
        brand_style_mime: str | None = None,
        previous_creative_bytes: bytes | None = None,
    ) -> ReferenceBundle:
        cfg = _policy_cfg()
        defaults = cfg.get("defaults") or {}
        mode_key = (mode or defaults.get("mode") or "auto").strip().lower()
        if mode_key not in (cfg.get("modes") or {}):
            mode_key = "auto"
        mode_cfg = (cfg.get("modes") or {}).get(mode_key) or {}
        roles = cfg.get("roles") or {}
        max_refs = int(defaults.get("max_references") or 3)
        stamp = dict(cfg.get("logo_correction") or {})

        images: list[ReferenceImage] = []
        logo_as_ref = False

        if (
            include_logo
            and mode_cfg.get("include_logo_when_enabled", True)
            and logo_bytes
        ):
            role_cfg = roles.get("logo_identity") or {}
            images.append(
                ReferenceImage(
                    role="logo_identity",
                    data=logo_bytes,
                    mime_type=str(role_cfg.get("mime_type") or "image/png"),
                    prompt_hint=str(role_cfg.get("prompt_hint") or ""),
                )
            )
            logo_as_ref = True

        # Brand style from explicit bytes or BrandKit extra_settings object keys are
        # resolved by callers — we only accept already-loaded bytes (never invent paths).
        if mode_cfg.get("include_brand_style") and brand_style_bytes:
            role_cfg = roles.get("brand_style") or {}
            images.append(
                ReferenceImage(
                    role="brand_style",
                    data=brand_style_bytes,
                    mime_type=str(
                        brand_style_mime or role_cfg.get("mime_type") or "image/png"
                    ),
                    prompt_hint=str(role_cfg.get("prompt_hint") or ""),
                )
            )

        if mode_cfg.get("include_previous_creative") and previous_creative_bytes:
            role_cfg = roles.get("previous_creative") or {}
            images.append(
                ReferenceImage(
                    role="previous_creative",
                    data=previous_creative_bytes,
                    mime_type=str(role_cfg.get("mime_type") or "image/png"),
                    prompt_hint=str(role_cfg.get("prompt_hint") or ""),
                )
            )

        # Optional brand kit hint metadata (documentation only; bytes must be provided)
        _ = brand

        return ReferenceBundle(
            images=images[:max_refs],
            logo_as_reference=logo_as_ref,
            stamp_policy=stamp,
        )

    def should_stamp_logo(
        self,
        *,
        critic_result: dict[str, Any] | None,
        logo_enabled: bool,
        stamp_policy: dict[str, Any] | None = None,
    ) -> bool:
        """Stamp only when critic flags missing/wrong logo — avoid duplicates."""
        if not logo_enabled:
            return False
        policy = stamp_policy if stamp_policy is not None else dict(
            (_policy_cfg().get("logo_correction") or {})
        )
        if not policy.get("stamp_when_critic_flags", True):
            return False
        if not critic_result:
            return False
        issues = [str(x).lower() for x in (critic_result.get("issues") or [])]
        flags = critic_result.get("flags") or {}
        logo_ok = flags.get("logo_ok")
        if logo_ok is False:
            return True
        keywords = ("logo missing", "wrong logo", "no logo", "logo incorrect", "logo absent")
        return any(any(k in issue for k in keywords) for issue in issues)
