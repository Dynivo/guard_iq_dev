"""API-facing carousel generation service — engine + persistence."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.infrastructure.postgres.models.carousel import (
    CarouselAssetRow,
    CarouselDeck,
    CarouselSlide,
    DeckVersionRow,
    Export,
    ExportArtifactRow,
    ExportJobRow,
    RenderJobRow,
)
from app.infrastructure.postgres.models.content import Draft
from app.infrastructure.postgres.models.typography import TypographyAssetRow
from app.infrastructure.storage.factory import get_delivery_strategy, get_storage_provider
from app.modules.assets.domain.ports import DeliveryStrategy, StorageProvider
from app.modules.carousel.application.factory import CarouselFactory
from app.modules.carousel.domain.models import CarouselPipelineRequest


class CarouselGenerationService:
    def __init__(
        self,
        session: AsyncSession,
        storage: StorageProvider | None = None,
        delivery: DeliveryStrategy | None = None,
    ) -> None:
        self._session = session
        self._storage = storage or get_storage_provider()
        self._delivery = delivery or get_delivery_strategy()
        self._engine = CarouselFactory.create_memory(use_mock_renderer=True)

    async def generate(
        self,
        org_id: uuid.UUID,
        draft_id: uuid.UUID,
        *,
        size: str = "1080x1350",
        typography_asset_id: uuid.UUID | None = None,
        correlation_id: str = "",
    ) -> dict[str, Any]:
        draft = await self._session.get(Draft, draft_id)
        if draft is None or draft.organization_id != org_id:
            raise NotFoundError("Draft", str(draft_id))

        width, height = (1080, 1350) if size != "1080x1080" else (1080, 1080)
        meta = draft.metadata_json if isinstance(draft.metadata_json, dict) else {}
        draft_meta = (
            draft.draft_metadata_json if isinstance(getattr(draft, "draft_metadata_json", None), dict) else {}
        )
        draft_json = draft.draft_json if isinstance(getattr(draft, "draft_json", None), dict) else {}
        draft_snapshot = {
            "hook": draft.hook,
            "cta": draft.cta,
            "generated_text": draft.generated_text,
            "edited_text": draft.edited_text,
            "carousel": meta.get("carousel")
            or draft_meta.get("carousel")
            or draft_json.get("carousel"),
            "slides": meta.get("slides") or draft_meta.get("slides") or draft_json.get("slides"),
            "slide_outline": meta.get("slide_outline")
            or draft_meta.get("slide_outline")
            or draft_json.get("slide_outline"),
        }

        typography_assets: list[dict] = []
        if typography_asset_id:
            row = await self._session.get(TypographyAssetRow, typography_asset_id)
            if row and row.organization_id == org_id:
                typography_assets.append(self._typography_row_to_dict(row))
        else:
            rows = (
                await self._session.execute(
                    select(TypographyAssetRow)
                    .where(
                        TypographyAssetRow.organization_id == org_id,
                        TypographyAssetRow.draft_id == draft_id,
                    )
                    .order_by(TypographyAssetRow.created_at.desc())
                    .limit(3)
                )
            ).scalars().all()
            typography_assets = [self._typography_row_to_dict(r) for r in rows]

        image_refs: list[str] = []
        for asset in typography_assets:
            ref = asset.get("illustration_ref") or ""
            if ref:
                image_refs.append(str(ref))

        result = await self._engine.run(
            CarouselPipelineRequest(
                organization_id=str(org_id),
                draft_id=str(draft_id),
                draft_snapshot=draft_snapshot,
                typography_assets=tuple(typography_assets),
                image_refs=tuple(image_refs),
                target_width=width,
                target_height=height,
                correlation_id=correlation_id,
                use_mock_renderer=True,
            )
        )

        asset = result.asset
        deck_row = CarouselDeck(
            organization_id=org_id,
            draft_id=draft_id,
            title=asset.deck.title,
            slide_count=len(asset.deck.slides),
            status=asset.status,
        )
        try:
            deck_row.id = uuid.UUID(asset.deck.deck_id)
        except ValueError:
            pass
        self._session.add(deck_row)
        await self._session.flush()

        for slide in asset.deck.slides:
            png_key = None
            for exp in asset.exports:
                if exp.format == "png" and exp.slide_index == slide.index and exp.content:
                    png_key = f"{org_id}/carousels/{deck_row.id}/slide_{slide.index:02d}.png"
                    self._storage.put_bytes(png_key, exp.content, "image/png")
                    break
            svg_key = None
            for exp in asset.exports:
                if exp.format == "svg" and exp.slide_index == slide.index and exp.content:
                    svg_key = f"{org_id}/carousels/{deck_row.id}/slide_{slide.index:02d}.svg"
                    self._storage.put_bytes(svg_key, exp.content, "image/svg+xml")
                    break
            self._session.add(
                CarouselSlide(
                    deck_id=deck_row.id,
                    role=slide.purpose,
                    sort_order=slide.index,
                    structured_json=slide.to_dict(),
                    rendered_object_key=png_key or svg_key,
                    svg_object_key=svg_key,
                    composition_json=slide.composition.to_dict() if slide.composition else None,
                    version=slide.version,
                )
            )

        pdf_url = None
        for exp in asset.exports:
            if not exp.content:
                continue
            key = f"{org_id}/carousels/{deck_row.id}/{exp.object_key or exp.format}"
            content_type = {
                "png": "image/png",
                "pdf": "application/pdf",
                "zip": "application/zip",
                "svg": "image/svg+xml",
            }.get(exp.format, "application/octet-stream")
            if exp.format in ("pdf", "zip") or exp.slide_index is None:
                self._storage.put_bytes(key, exp.content, content_type)
            if exp.format == "pdf":
                pdf_url = self._delivery.resolve(key, content_type="application/pdf").url
            self._session.add(
                Export(
                    organization_id=org_id,
                    deck_id=deck_row.id,
                    format=exp.format,
                    size=size,
                    object_key=key,
                    description=str(exp.metadata),
                )
            )
            self._session.add(
                ExportArtifactRow(
                    organization_id=org_id,
                    deck_id=deck_row.id,
                    format=exp.format,
                    object_key=key,
                    size_bytes=exp.size_bytes or len(exp.content),
                    slide_index=exp.slide_index,
                    metadata_json=dict(exp.metadata),
                )
            )

        asset_row = CarouselAssetRow(
            organization_id=org_id,
            draft_id=draft_id,
            deck_id=deck_row.id,
            status=asset.status,
            version=asset.version,
            deck_json=asset.deck.to_dict(),
            rendered_json=asset.rendered.to_dict() if asset.rendered else None,
            exports_json=[e.to_dict() for e in asset.exports],
            typography_asset_ids=list(asset.typography_asset_ids),
            image_refs=list(asset.image_refs),
            metadata_json=dict(asset.metadata),
            render_time_ms=result.render_time_ms,
            export_time_ms=result.export_time_ms,
            deck_definition_json=(
                asset.deck_definition.to_dict() if asset.deck_definition else None
            ),
            dependency_graph_json=(
                asset.dependency_graph.to_dict() if asset.dependency_graph else None
            ),
            optimization_json=asset.optimization.to_dict() if asset.optimization else None,
            export_profile=asset.export_profile,
        )
        try:
            asset_row.id = uuid.UUID(asset.asset_id)
        except ValueError:
            pass
        self._session.add(asset_row)

        self._session.add(
            DeckVersionRow(
                organization_id=org_id,
                deck_id=deck_row.id,
                version=asset.version,
                deck_json=asset.deck.to_dict(),
                parent_version=asset.version - 1 if asset.version > 1 else None,
            )
        )
        self._session.add(
            RenderJobRow(
                organization_id=org_id,
                deck_id=deck_row.id,
                status="completed",
                width=width,
                height=height,
                render_time_ms=result.render_time_ms,
                metadata_json=result.render_plan.to_dict() if result.render_plan else {},
            )
        )
        self._session.add(
            ExportJobRow(
                organization_id=org_id,
                deck_id=deck_row.id,
                status="completed",
                formats=list(result.asset.metadata.get("export_formats") or ["png", "pdf", "zip"]),
                export_time_ms=result.export_time_ms,
                metadata_json={"export_count": len(asset.exports)},
            )
        )

        await self._session.flush()

        from app.core.observability import ensure_correlation_id
        from app.infrastructure.events.factory import get_event_bus
        from app.shared.events import carousel_generated
        from app.shared.events.session_context import reset_event_session, set_event_session

        corr = correlation_id or ensure_correlation_id()
        token = set_event_session(self._session)
        try:
            await get_event_bus().publish(
                carousel_generated(
                    organization_id=org_id,
                    draft_id=draft_id,
                    deck_id=deck_row.id,
                    slide_count=deck_row.slide_count,
                    correlation_id=corr,
                )
            )
        finally:
            reset_event_session(token)

        return {
            **result.to_dict(),
            "deck_id": str(deck_row.id),
            "persisted_asset_id": str(asset_row.id),
            "size": size,
            "pdf_url": pdf_url,
            "delivery_strategy": self._delivery.name,
            "correlation_id": corr,
        }

    def _typography_row_to_dict(self, row: TypographyAssetRow) -> dict:
        return {
            "asset_id": str(row.id),
            "svg": row.svg_text or "",
            "layers": row.layers_json or [],
            "width": row.width,
            "height": row.height,
            "layout": row.layout_enrichment_json,
            "slide_composition": row.slide_composition_json,
            "illustration_ref": (row.metadata_json or {}).get("illustration_ref")
            if isinstance(row.metadata_json, dict)
            else "",
            "brand": row.brand_application_json,
            "typography_plan": row.typography_plan_json,
        }
