"""Phase 7 — Git History Analysis."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class GitHistoryMetrics:
    first_commit: str | None = None
    last_commit: str | None = None
    total_commits: int = 0
    commits_per_month: float = 0.0
    months_active: float = 0.0
    candidate_commit_share: float = 0.0
    unique_contributors: int = 0

    def to_dict(self) -> dict:
        return {
            "first_commit": self.first_commit,
            "last_commit": self.last_commit,
            "total_commits": self.total_commits,
            "commits_per_month": round(self.commits_per_month, 2),
            "months_active": round(self.months_active, 2),
            "candidate_commit_share": round(self.candidate_commit_share, 2),
            "unique_contributors": self.unique_contributors,
        }


def _run_git(repo_path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_path), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def analyze_git_history(repo_path: Path, candidate_email: str | None = None) -> GitHistoryMetrics:
    metrics = GitHistoryMetrics()

    if not (repo_path / ".git").exists():
        return metrics

    log = _run_git(
        repo_path,
        "log",
        "--pretty=format:%H|%ae|%aI",
        "--reverse",
    )
    if not log:
        return metrics

    lines = [line for line in log.splitlines() if line]
    metrics.total_commits = len(lines)

    first_parts = lines[0].split("|")
    last_parts = lines[-1].split("|")
    metrics.first_commit = first_parts[2] if len(first_parts) > 2 else None
    metrics.last_commit = last_parts[2] if len(last_parts) > 2 else None

    emails = {line.split("|")[1] for line in lines if "|" in line}
    metrics.unique_contributors = len(emails)

    if candidate_email:
        candidate_commits = sum(1 for line in lines if candidate_email.lower() in line.lower())
        metrics.candidate_commit_share = (
            candidate_commits / metrics.total_commits if metrics.total_commits else 0.0
        )
    elif metrics.unique_contributors == 1:
        metrics.candidate_commit_share = 1.0
    else:
        metrics.candidate_commit_share = 1.0 / max(metrics.unique_contributors, 1)

    if metrics.first_commit and metrics.last_commit:
        try:
            first_dt = datetime.fromisoformat(metrics.first_commit.replace("Z", "+00:00"))
            last_dt = datetime.fromisoformat(metrics.last_commit.replace("Z", "+00:00"))
            days = max((last_dt - first_dt).days, 1)
            metrics.months_active = days / 30.44
            metrics.commits_per_month = metrics.total_commits / max(metrics.months_active, 1)
        except ValueError:
            pass

    return metrics
