"""Typography replay and overlay diff."""

from __future__ import annotations

from app.modules.typography.domain.models import OverlayDiff, TypographyAsset, TypographyReplayRecord


class InMemoryTypographyReplayStore:
    def __init__(self) -> None:
        self._items: dict[str, TypographyReplayRecord] = {}

    def save(self, record: TypographyReplayRecord) -> None:
        self._items[record.replay_id] = record

    def get(self, replay_id: str) -> TypographyReplayRecord | None:
        return self._items.get(replay_id)


class DefaultOverlayDiffService:
    def diff(self, left: TypographyAsset, right: TypographyAsset) -> OverlayDiff:
        left_roles = {layer.role: layer.to_dict() for layer in left.layers}
        right_roles = {layer.role: layer.to_dict() for layer in right.layers}
        changes: dict = {}
        for role in set(left_roles) | set(right_roles):
            if left_roles.get(role) != right_roles.get(role):
                changes[role] = {"left": left_roles.get(role), "right": right_roles.get(role)}
        brand_changed = (left.brand.to_dict() if left.brand else {}) != (
            right.brand.to_dict() if right.brand else {}
        )
        plan_changed = (left.typography_plan.to_dict() if left.typography_plan else {}) != (
            right.typography_plan.to_dict() if right.typography_plan else {}
        )
        return OverlayDiff(
            left_asset_id=left.asset_id,
            right_asset_id=right.asset_id,
            layer_changes=changes,
            brand_changed=brand_changed,
            plan_changed=plan_changed,
        )
