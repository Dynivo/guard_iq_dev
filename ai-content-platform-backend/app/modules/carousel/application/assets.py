"""In-memory carousel asset store with version history."""

from __future__ import annotations

from app.modules.carousel.domain.models import CarouselAsset


class InMemoryCarouselAssetStore:
    def __init__(self) -> None:
        self._items: dict[str, CarouselAsset] = {}
        self._history: dict[str, list[CarouselAsset]] = {}

    async def store(self, asset: CarouselAsset) -> CarouselAsset:
        self._items[asset.asset_id] = asset
        root = asset.parent_asset_id or asset.asset_id
        self._history.setdefault(root, []).append(asset)
        if asset.parent_asset_id:
            self._history.setdefault(asset.asset_id, []).append(asset)
        return asset

    def get(self, asset_id: str) -> CarouselAsset | None:
        return self._items.get(asset_id)

    def history(self, asset_id: str) -> list[CarouselAsset]:
        return list(self._history.get(asset_id, []))
