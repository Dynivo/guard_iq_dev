#!/usr/bin/env python3
"""Deprecated alias — use seed_shailesh_guardiq_brand.py (company is Guard IQ, not Hybrd)."""

from __future__ import annotations

import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parent / "seed_shailesh_guardiq_brand.py"), run_name="__main__")
