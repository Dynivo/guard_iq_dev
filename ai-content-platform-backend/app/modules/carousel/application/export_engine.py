"""Export engine — PNG / PDF / ZIP from rendered deck; SVG remains SoT."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from PIL import Image

from app.modules.carousel.application.config_loader import load_carousel
from app.modules.carousel.domain.models import ExportArtifact, RenderedDeck, new_id


class DefaultExportEngine:
    def __init__(self, config_dir: Path | None = None) -> None:
        self._cfg = load_carousel("export.yaml", config_dir)

    async def export(
        self,
        rendered: RenderedDeck,
        *,
        formats: tuple[str, ...] = ("png", "pdf", "zip"),
    ) -> tuple[ExportArtifact, ...]:
        artifacts: list[ExportArtifact] = []
        wanted = set(formats) | {"svg"}  # always retain SVG artifacts as SoT
        include_svg_zip = bool(self._cfg.get("include_svg_in_zip", True))

        pngs: list[bytes] = []
        for slide in rendered.slides:
            if "svg" in wanted and slide.svg:
                artifacts.append(
                    ExportArtifact(
                        artifact_id=new_id(),
                        format="svg",
                        object_key=f"slides/{slide.index:02d}.svg",
                        size_bytes=len(slide.svg.encode("utf-8")),
                        slide_index=slide.index,
                        content=slide.svg.encode("utf-8"),
                        metadata={"source_of_truth": True},
                    )
                )
            if "png" in wanted and slide.png_bytes:
                pngs.append(slide.png_bytes)
                artifacts.append(
                    ExportArtifact(
                        artifact_id=new_id(),
                        format="png",
                        object_key=f"slides/{slide.index:02d}.png",
                        size_bytes=len(slide.png_bytes),
                        slide_index=slide.index,
                        content=slide.png_bytes,
                        metadata={"derived": True},
                    )
                )

        if "pdf" in wanted and pngs:
            pdf = self._pngs_to_pdf(pngs)
            artifacts.append(
                ExportArtifact(
                    artifact_id=new_id(),
                    format="pdf",
                    object_key="deck.pdf",
                    size_bytes=len(pdf),
                    content=pdf,
                    metadata={"derived": True, "pages": len(pngs)},
                )
            )

        if "zip" in wanted:
            zbuf = io.BytesIO()
            with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as zf:
                for slide in rendered.slides:
                    if slide.png_bytes:
                        zf.writestr(f"slides/{slide.index:02d}.png", slide.png_bytes)
                    if include_svg_zip and slide.svg:
                        zf.writestr(f"slides/{slide.index:02d}.svg", slide.svg.encode("utf-8"))
                if self._cfg.get("include_deck_metadata", True):
                    zf.writestr(
                        "deck.json",
                        (
                            '{"deck_id":"%s","width":%s,"height":%s,"slide_count":%s}'
                            % (
                                rendered.deck_id,
                                rendered.width,
                                rendered.height,
                                len(rendered.slides),
                            )
                        ).encode("utf-8"),
                    )
            zip_bytes = zbuf.getvalue()
            artifacts.append(
                ExportArtifact(
                    artifact_id=new_id(),
                    format="zip",
                    object_key="deck.zip",
                    size_bytes=len(zip_bytes),
                    content=zip_bytes,
                    metadata={"derived": True},
                )
            )

        return tuple(artifacts)

    def _pngs_to_pdf(self, pngs: list[bytes]) -> bytes:
        images = [Image.open(io.BytesIO(b)).convert("RGB") for b in pngs]
        if not images:
            return b""
        buf = io.BytesIO()
        images[0].save(buf, format="PDF", save_all=True, append_images=images[1:])
        return buf.getvalue()
