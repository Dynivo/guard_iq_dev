"""Output Schema Registry — markdown/json/carousel/image_prompt."""

from __future__ import annotations

from pathlib import Path

import yaml

from app.modules.prompts.domain.models import OutputSchema

_DEFAULT_DIR = Path(__file__).resolve().parents[4] / "configs" / "prompts" / "schemas"


class YamlOutputSchemaRegistry:
    def __init__(self, schemas_dir: Path | None = None) -> None:
        self._dir = schemas_dir or _DEFAULT_DIR
        self._schemas: dict[str, OutputSchema] = {}
        self._load()

    def _load(self) -> None:
        builtins = {
            "markdown": OutputSchema(
                schema_id="markdown",
                format="markdown",
                description="Freeform markdown post body",
                instructions="Respond in Markdown only.",
            ),
            "json": OutputSchema(
                schema_id="json",
                format="json",
                description="Structured JSON object",
                json_schema={"type": "object"},
                instructions="Respond with a single JSON object only.",
            ),
            "carousel": OutputSchema(
                schema_id="carousel",
                format="carousel",
                description="Carousel slide JSON",
                json_schema={"type": "object", "required": ["slides"]},
                instructions="Respond with JSON containing a slides array.",
            ),
            "image_prompt": OutputSchema(
                schema_id="image_prompt",
                format="image_prompt",
                description="Image generation prompt text",
                instructions="Respond with a single image prompt string.",
            ),
        }
        self._schemas.update(builtins)
        if self._dir.exists():
            for path in self._dir.glob("*.yaml"):
                raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                if not isinstance(raw, dict):
                    continue
                sid = str(raw.get("schema_id") or path.stem)
                self._schemas[sid] = OutputSchema(
                    schema_id=sid,
                    format=str(raw.get("format") or sid),
                    description=str(raw.get("description") or ""),
                    json_schema=dict(raw.get("json_schema") or {}),
                    instructions=str(raw.get("instructions") or ""),
                )

    def get(self, schema_id: str) -> OutputSchema | None:
        return self._schemas.get(schema_id)

    def list_ids(self) -> list[str]:
        return sorted(self._schemas.keys())
