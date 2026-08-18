#!/usr/bin/env python3
"""Secure local recovery for the single Guard IQ administrator account."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.security.password import hash_password
from app.infrastructure.postgres.models.identity import User
from app.infrastructure.postgres.session import async_session_factory

DEFAULT_ADMIN_EMAIL = "admin@guardiq.com"


def validate_recovery_password(password: str, confirmation: str) -> str:
    if password != confirmation:
        raise ValueError("Passwords do not match")
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters")
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password must be no more than 72 UTF-8 bytes")
    return password


async def reset_password(email: str, password: str) -> None:
    async with async_session_factory() as session:
        user = (
            await session.execute(select(User).where(User.email == email.strip().lower()))
        ).scalar_one_or_none()
        if user is None:
            raise RuntimeError(f"No user exists with email {email}")
        user.password_hash = hash_password(password)
        await session.commit()


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reset the local admin password without displaying or storing it."
    )
    parser.add_argument("--email", default=DEFAULT_ADMIN_EMAIL)
    args = parser.parse_args()
    password = getpass.getpass("New admin password: ")
    confirmation = getpass.getpass("Confirm new admin password: ")
    try:
        validate_recovery_password(password, confirmation)
        await reset_password(args.email, password)
    except (ValueError, RuntimeError) as exc:
        print(f"Password reset failed: {exc}", file=sys.stderr)
        return 1
    print(f"Password reset for {args.email}. Start the app and sign in again.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
