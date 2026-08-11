"""HTML template binder for carousel slides."""

from __future__ import annotations

from pathlib import Path

TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    width: {width}px; height: {height}px;
    font-family: Arial, Helvetica, sans-serif;
    background: {bg};
    color: {fg};
    padding: 64px;
    display: flex; flex-direction: column; justify-content: space-between;
  }}
  .label {{ font-size: 18px; letter-spacing: 0.12em; text-transform: uppercase; color: {muted}; }}
  h1 {{ font-size: 52px; line-height: 1.15; margin-top: 24px; max-width: 90%; }}
  .body {{ font-size: 28px; line-height: 1.4; color: {muted}; margin-top: 28px; max-width: 92%; }}
  .footer {{ font-size: 20px; color: {accent}; border-top: 1px solid {accent}; padding-top: 20px; }}
</style></head>
<body>
  <div>
    <div class="label">{role} · {brand}</div>
    <h1>{headline}</h1>
    <div class="body">{body}</div>
  </div>
  <div class="footer">{footer}</div>
</body></html>
"""


class HtmlTemplateEngine:
    async def bind(self, template_path: str, variables: dict) -> str:
        # Prefer file template if present; else built-in
        path = Path(template_path) if template_path else None
        if path and path.exists():
            raw = path.read_text(encoding="utf-8")
            return raw.format(**variables)
        return TEMPLATE.format(**variables)
