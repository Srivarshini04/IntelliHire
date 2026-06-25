"""Phase 1 — GitHubRepository Discovery via PyGithub."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from github import Auth, Github, GithubException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.github_intel.models import GitHubProfile, GitHubRepository


GITHUB_USER_RE = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/(?P<user>[^/\s?#]+)", re.IGNORECASE
)


@dataclass
class DiscoveredRepo:
    name: str
    full_name: str
    description: str | None
    language: str | None
    topics: list[str]
    stars: int
    forks: int
    updated_at: datetime | None
    size_kb: int
    clone_url: str
    default_branch: str


def parse_github_username(github_url: str) -> str:
    match = GITHUB_USER_RE.search(github_url.strip())
    if not match:
        raise ValueError(f"Invalid GitHub URL: {github_url}")
    username = match.group("user")
    if username.lower() in {"orgs", "organizations", "settings", "marketplace"}:
        raise ValueError(f"Invalid GitHub user segment: {username}")
    return username


def _github_client() -> Github:
    settings = get_settings()
    if settings.github_token:
        return Github(auth=Auth.Token(settings.github_token))
    return Github()


def discover_repositories(github_url: str) -> tuple[str, list[DiscoveredRepo]]:
    username = parse_github_username(github_url)
    gh = _github_client()

    try:
        user = gh.get_user(username)
    except GithubException as exc:
        raise ValueError(f"GitHub user not found: {username}") from exc

    discovered: list[DiscoveredRepo] = []
    for repo in user.get_repos(type="owner", sort="updated"):
        if repo.fork:
            continue
        updated = repo.updated_at
        if updated and updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        discovered.append(
            DiscoveredRepo(
                name=repo.name,
                full_name=repo.full_name,
                description=repo.description,
                language=repo.language,
                topics=list(repo.get_topics()),
                stars=repo.stargazers_count,
                forks=repo.forks_count,
                updated_at=updated,
                size_kb=repo.size,
                clone_url=repo.clone_url,
                default_branch=repo.default_branch or "main",
            )
        )

    return username, discovered


def persist_repositories(
    db: Session, github_url: str, username: str, repos: list[DiscoveredRepo]
) -> GitHubProfile:
    candidate = db.query(GitHubProfile).filter_by(github_username=username).first()
    if not candidate:
        candidate = GitHubProfile(github_username=username, github_url=github_url)
        db.add(candidate)
        db.flush()
    else:
        candidate.github_url = github_url
        candidate.updated_at = datetime.utcnow()

    existing = {r.full_name: r for r in candidate.repositories}
    seen: set[str] = set()

    for repo in repos:
        seen.add(repo.full_name)
        row = existing.get(repo.full_name)
        if not row:
            row = GitHubRepository(profile_id=candidate.id, name=repo.name, full_name=repo.full_name)
            db.add(row)

        row.description = repo.description
        row.language = repo.language
        row.topics = repo.topics
        row.stars = repo.stars
        row.forks = repo.forks
        row.updated_at = repo.updated_at.replace(tzinfo=None) if repo.updated_at else None
        row.size_kb = repo.size_kb
        row.clone_url = repo.clone_url
        row.default_branch = repo.default_branch

    db.commit()
    db.refresh(candidate)
    return candidate
