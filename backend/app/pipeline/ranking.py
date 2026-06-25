"""Phase 2 — GitHubRepository Ranking (fast heuristics, no per-repo API calls)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.github_intel.models import GitHubProfile, GitHubRepository


def _normalize(value: float, cap: float) -> float:
    if cap <= 0:
        return 0.0
    return min(value / cap, 1.0) * 100


def _recency_score(updated_at: datetime | None) -> float:
    if not updated_at:
        return 0.0
    now = datetime.now(timezone.utc)
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    days = max((now - updated_at).days, 0)
    return max(0.0, 100.0 - (days / 365.0) * 100.0)


def _topic_match_score(topics: list[str], jd_skills: list[str]) -> float:
    if not topics or not jd_skills:
        return 0.0
    topic_set = {t.lower() for t in topics}
    skill_set = {s.lower().replace(" ", "-") for s in jd_skills}
    skill_set |= {s.lower().replace(" ", "") for s in jd_skills}
    skill_set |= {s.lower() for s in jd_skills}
    matches = sum(
        1
        for skill in skill_set
        if any(skill in topic or topic in skill for topic in topic_set)
    )
    return min(matches / max(len(jd_skills), 1), 1.0) * 100


def _commit_activity_heuristic(repo: GitHubRepository) -> float:
    """Proxy for commit activity — avoids N GitHub API calls during ranking."""
    size = _normalize(repo.size_kb, 5000)
    recency = _recency_score(repo.updated_at)
    forks = _normalize(repo.forks, 20)
    return size * 0.35 + recency * 0.45 + forks * 0.2


def repository_importance_score(
    repo: GitHubRepository,
    commit_activity: float,
    jd_skills: list[str] | None = None,
) -> float:
    stars = _normalize(repo.stars, 50)
    size = _normalize(repo.size_kb, 5000)
    recency = _recency_score(repo.updated_at)
    topic = _topic_match_score(repo.topics, jd_skills or [])

    score = (
        stars * 0.2
        + size * 0.2
        + commit_activity * 0.3
        + recency * 0.2
        + topic * 0.1
    )
    return round(score, 2)


def rank_repositories(
    db: Session,
    candidate: GitHubProfile,
    jd_skills: list[str] | None = None,
    top_n: int | None = None,
) -> list[GitHubRepository]:
    settings = get_settings()
    top_n = top_n or settings.top_n_repos

    for repo in candidate.repositories:
        commit_activity = _commit_activity_heuristic(repo)
        repo.commit_activity = commit_activity
        repo.importance_score = repository_importance_score(repo, commit_activity, jd_skills)

    db.commit()

    ranked = sorted(
        candidate.repositories,
        key=lambda r: r.importance_score,
        reverse=True,
    )
    return ranked[:top_n]
