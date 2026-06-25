"""GitHubRepository cloning utilities."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from app.core.config import get_settings


def clone_repository(clone_url: str, full_name: str) -> Path:
    settings = get_settings()
    base = Path(settings.clone_dir)
    base.mkdir(parents=True, exist_ok=True)

    safe_name = full_name.replace("/", "__")
    target = base / safe_name

    if target.exists():
        shutil.rmtree(target, ignore_errors=True)

    if not settings.clone_repos:
        target.mkdir(parents=True, exist_ok=True)
        return target

    subprocess.run(
        ["git", "clone", "--depth", "50", clone_url, str(target)],
        capture_output=True,
        check=False,
    )
    return target
