"""Add org-scoped brand client profile Markdown.

Revision ID: 0021
Revises: 0020
Create Date: 2026-08-07
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PROFILE_CANDIDATES = (
    Path(__file__).resolve().parents[1].parent / "configs" / "brand" / "client-profile.md",
    Path(__file__).resolve().parents[2] / "configs" / "brand" / "client-profile.md",
)


def _read_default_profile() -> str | None:
    for path in _PROFILE_CANDIDATES:
        if path.exists():
            return path.read_text(encoding="utf-8")
    return None


def upgrade() -> None:
    op.add_column(
        "brand_kits",
        sa.Column("client_profile_md", sa.Text(), nullable=True),
    )

    profile = _read_default_profile()
    if profile:
        conn = op.get_bind()
        conn.execute(
            sa.text(
                """
                UPDATE brand_kits
                SET client_profile_md = :profile
                WHERE client_profile_md IS NULL
                  AND (
                    client_profile_path IS NULL
                    OR client_profile_path LIKE '%client-profile.md'
                  )
                """
            ),
            {"profile": profile},
        )


def downgrade() -> None:
    op.drop_column("brand_kits", "client_profile_md")
