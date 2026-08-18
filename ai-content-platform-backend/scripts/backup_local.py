#!/usr/bin/env python3
"""Create a portable local backup of PostgreSQL data and generated media."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.engine import make_url

from app.core.config import get_settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _find_pg_dump() -> str:
    executable = shutil.which("pg_dump")
    if executable is None:
        raise RuntimeError(
            "pg_dump was not found. On macOS run: "
            "export PATH=\"$(brew --prefix postgresql@16)/bin:$PATH\""
        )
    return executable


def create_backup(output_dir: Path) -> Path:
    settings = get_settings()
    url = make_url(settings.DATABASE_URL)
    if not url.drivername.startswith("postgresql"):
        raise RuntimeError("The delivery backup tool supports PostgreSQL only")

    created = datetime.now(timezone.utc)
    stamp = created.strftime("%Y%m%d-%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / f"guardiq-backup-{stamp}.zip"
    media_root = (PROJECT_ROOT / settings.STORAGE_LOCAL_ROOT).resolve()
    if output_dir.resolve().is_relative_to(media_root):
        raise RuntimeError("Backup output directory cannot be inside the media directory")

    with tempfile.TemporaryDirectory(prefix="guardiq-backup-") as temp_name:
        temp = Path(temp_name)
        dump_path = temp / "database.dump"
        command = [
            _find_pg_dump(),
            "--format=custom",
            "--no-owner",
            "--no-privileges",
            "--no-password",
            f"--file={dump_path}",
            f"--host={url.host or '127.0.0.1'}",
            f"--port={url.port or 5432}",
            f"--username={url.username or 'postgres'}",
            url.database or "ai_content_platform",
        ]
        child_env = os.environ.copy()
        if url.password:
            child_env["PGPASSWORD"] = url.password
        subprocess.run(command, check=True, env=child_env)
        if not dump_path.is_file() or dump_path.stat().st_size == 0:
            raise RuntimeError("pg_dump completed without creating a usable backup")

        manifest = {
            "format_version": 1,
            "created_at": created.isoformat(),
            "database": url.database,
            "includes_media": media_root.is_dir(),
            "restore_requires": "PostgreSQL pg_restore and a stopped Guard IQ app",
        }
        (temp / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            bundle.write(dump_path, "database.dump")
            bundle.write(temp / "manifest.json", "manifest.json")
            if media_root.is_dir():
                for item in media_root.rglob("*"):
                    if item.is_file():
                        bundle.write(item, Path("media") / item.relative_to(media_root))

    # The archive contains client data. Restrict it to the current macOS user;
    # Windows applies the account ACL and safely ignores unsupported mode bits.
    archive.chmod(0o600)

    return archive


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Back up the Guard IQ database and generated media."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "backups",
        help="Directory for the timestamped ZIP (default: backend/backups)",
    )
    args = parser.parse_args()
    try:
        archive = create_backup(args.output_dir.resolve())
    except (RuntimeError, subprocess.CalledProcessError, OSError) as exc:
        print(f"Backup failed: {exc}", file=sys.stderr)
        return 1
    print(f"Backup created: {archive}")
    print("Copy this ZIP to encrypted storage away from the project folder.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
