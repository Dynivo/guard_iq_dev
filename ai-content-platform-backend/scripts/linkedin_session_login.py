#!/usr/bin/env python3
"""One-time LinkedIn login for Brand Intelligence (Playwright storage_state).

Opens a browser, you log into LinkedIn once, then the script prints a base64
storage_state payload to POST to:
  POST /api/v1/brand-intelligence/session/linkedin/save
  { "storage_state_b64": "<output>" }

Usage:
    cd ai-content-platform-backend
    .venv/bin/pip install playwright
    .venv/bin/playwright install chromium
    .venv/bin/python scripts/linkedin_session_login.py
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path


def main() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Install: pip install playwright && playwright install chromium", file=sys.stderr)
        sys.exit(1)

    out = Path("data/linkedin_storage_state.json")
    out.parent.mkdir(parents=True, exist_ok=True)

    print("A Chromium window will open. Log into LinkedIn, open any profile, then return here.")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
        input("After you are logged in and see your LinkedIn feed, press Enter here… ")
        state = context.storage_state()
        out.write_text(json.dumps(state), encoding="utf-8")
        browser.close()

    b64 = base64.b64encode(out.read_bytes()).decode("ascii")
    print("\nSaved:", out.resolve())
    print("\n=== storage_state_b64 (paste into session/linkedin/save) ===\n")
    print(b64)
    print("\n=== end ===")


if __name__ == "__main__":
    main()
