"""Git history via GitHub API — lightweight by default."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from github import Auth, Github, GithubException

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class GitHistoryMetrics:
    first_commit: str | None = None
    last_commit: str | None = None
    total_commits: int = 0
    commits_per_month: float = 0.0
    months_active: float = 0.0
    candidate_commit_share: float = 0.0
    unique_contributors: int = 0
    maintenance_score: float = 0.0
    source: str = "api"

    def to_dict(self) -> dict:
        return {
            "first_commit": self.first_commit,
            "last_commit": self.last_commit,
            "total_commits": self.total_commits,
            "commits_per_month": round(self.commits_per_month, 2),
            "months_active": round(self.months_active, 2),
            "candidate_commit_share": round(self.candidate_commit_share, 2),
            "unique_contributors": self.unique_contributors,
            "maintenance_score": round(self.maintenance_score, 2),
            "source": self.source,
        }


def _compute_maintenance_score(
    months_active: float,
    commits_per_month: float,
    ownership: float,
    total_commits: int,
) -> float:
    longevity = min(months_active / 12.0, 1.0) * 40.0
    consistency = min(commits_per_month / 8.0, 1.0) * 30.0
    ownership_pts = ownership * 20.0
    volume = min(total_commits / 50.0, 1.0) * 10.0
    return min(longevity + consistency + ownership_pts + volume, 100.0)


def estimate_git_history_from_repo_metadata(
    updated_at: datetime | None,
    size_kb: int = 0,
    stars: int = 0,
) -> GitHistoryMetrics:
    """Fast estimate when skipping per-repo commit API calls."""
    metrics = GitHistoryMetrics(source="estimate")
    if not updated_at:
        return metrics

    now = datetime.now(timezone.utc)
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)

    days_since_update = max((now - updated_at).days, 1)
    metrics.months_active = min(size_kb / 100, 24) + min(stars, 20) * 0.5
    metrics.months_active = max(metrics.months_active, 1.0)
    metrics.commits_per_month = min(size_kb / 200, 12)
    metrics.total_commits = int(metrics.commits_per_month * metrics.months_active)
    metrics.candidate_commit_share = 1.0
    metrics.last_commit = updated_at.isoformat()

    recency_bonus = max(0.0, 1.0 - days_since_update / 365.0)
    metrics.maintenance_score = _compute_maintenance_score(
        metrics.months_active,
        metrics.commits_per_month,
        metrics.candidate_commit_share,
        metrics.total_commits,
    ) * (0.6 + recency_bonus * 0.4)
    return metrics


def fetch_git_history(
    full_name: str,
    candidate_username: str | None = None,
    *,
    light: bool = False,
    updated_at: datetime | None = None,
    size_kb: int = 0,
) -> GitHistoryMetrics:
    if light:
        return estimate_git_history_from_repo_metadata(updated_at, size_kb)

    settings = get_settings()
    metrics = GitHistoryMetrics()

    try:
        gh = Github(auth=Auth.Token(settings.github_token)) if settings.github_token else Github()
        repo = gh.get_repo(full_name)
        commits = list(repo.get_commits()[:30])
        if not commits:
            return estimate_git_history_from_repo_metadata(updated_at, size_kb)

        metrics.total_commits = len(commits)
        last = commits[0].commit.author.date
        first = commits[-1].commit.author.date
        metrics.last_commit = last.isoformat()
        metrics.first_commit = first.isoformat()

        days = max((last - first).days, 1)
        metrics.months_active = days / 30.44
        metrics.commits_per_month = metrics.total_commits / max(metrics.months_active, 0.1)
        metrics.candidate_commit_share = 1.0
        metrics.unique_contributors = 1

    except GithubException as exc:
        logger.warning("Git history fallback for %s: %s", full_name, exc)
        return estimate_git_history_from_repo_metadata(updated_at, size_kb)

    metrics.maintenance_score = _compute_maintenance_score(
        metrics.months_active,
        metrics.commits_per_month,
        metrics.candidate_commit_share,
        metrics.total_commits,
    )
    return metrics
