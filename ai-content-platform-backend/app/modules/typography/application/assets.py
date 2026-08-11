"""In-memory typography asset store with version history."""

from __future__ import annotations

from app.modules.typography.domain.models import TypographyAsset


class InMemoryTypographyAssetStore:
    def __init__(self) -> None:
        self._items: dict[str, TypographyAsset] = {}
        self._history: dict[str, list[str]] = {}

    async def store(self, asset: TypographyAsset) -> TypographyAsset:
        self._items[asset.asset_id] = asset
        root = asset.parent_asset_id or asset.asset_id
        self._history.setdefault(root, []).append(asset.asset_id)
        return asset

    def get(self, asset_id: str) -> TypographyAsset | None:
        return self._items.get(asset_id)

    def history(self, asset_id: str) -> list[TypographyAsset]:
        root = asset_id
        asset = self._items.get(asset_id)
        if asset and asset.parent_asset_id:
            root = asset.parent_asset_id
        ids = self._history.get(root) or ([asset_id] if asset_id in self._items else [])
        return [self._items[i] for i in ids if i in self._items]
