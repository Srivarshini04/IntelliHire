"""GitHub REST extractor — teammate implementation (Anushakaringula)."""

import os
import re
from concurrent.futures import ThreadPoolExecutor

import requests

from app.core.config import get_settings


def _headers() -> dict:
    settings = get_settings()
    headers = {"Accept": "application/vnd.github+json"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    return headers


def parse_github_url(github_url: str) -> dict:
    parts = github_url.rstrip("/").replace("https://github.com/", "").split("/")

    if len(parts) == 1:
        return {"username": parts[0], "repo": None}

    return {"username": parts[0], "repo": parts[1]}


def fetch_languages(username: str, repo_name: str) -> dict:
    url = f"https://api.github.com/repos/{username}/{repo_name}/languages"
    response = requests.get(url, headers=_headers(), timeout=15)
    if response.status_code != 200:
        return {}
    return response.json()


def fetch_commit_count(username: str, repo_name: str) -> int:
    url = f"https://api.github.com/repos/{username}/{repo_name}/commits"
    params = {"author": username, "per_page": 1}
    response = requests.get(url, headers=_headers(), params=params, timeout=15)
    if response.status_code != 200:
        return 0

    link = response.headers.get("Link", "")
    match = re.search(r'[?&]page=(\d+)>;\s*rel="last"', link)
    if match:
        return int(match.group(1))
    return len(response.json())


def fetch_recent_events(username: str) -> list:
    url = f"https://api.github.com/users/{username}/events"
    response = requests.get(url, headers=_headers(), timeout=15)
    if response.status_code != 200:
        return []

    events = response.json()
    activity: dict = {}

    for event in events:
        repo = event.get("repo", {}).get("name")
        if not repo:
            continue

        owned = repo.split("/")[0].lower() == username.lower()
        payload = event.get("payload", {})
        commit_count = len(payload.get("commits", [])) if event["type"] == "PushEvent" else 0

        if repo not in activity:
            activity[repo] = {
                "repo": repo,
                "owned": owned,
                "event_count": 0,
                "commit_count": 0,
                "last_active": event["created_at"],
            }

        activity[repo]["event_count"] += 1
        activity[repo]["commit_count"] += commit_count
        if event["created_at"] > activity[repo]["last_active"]:
            activity[repo]["last_active"] = event["created_at"]

    return sorted(activity.values(), key=lambda a: a["last_active"], reverse=True)


def build_repo_info(username: str, repo: dict) -> dict:
    repo_name = repo.get("name")
    languages = fetch_languages(username, repo_name)
    commit_count = fetch_commit_count(username, repo_name)

    return {
        "name": repo_name,
        "description": repo.get("description") or "",
        "language": repo.get("language") or "",
        "topics": repo.get("topics", []),
        "stars": repo.get("stargazers_count", 0),
        "forks": repo.get("forks_count", 0),
        "updated_at": repo.get("updated_at"),
        "url": repo.get("html_url"),
        "languages": languages,
        "commit_count": commit_count,
    }


def fetch_github_data(github_url: str) -> dict:
    settings = get_settings()
    if not settings.github_token:
        raise ValueError("GITHUB_TOKEN missing — set it in backend/.env")

    parsed = parse_github_url(github_url)
    username = parsed["username"]

    profile_response = requests.get(
        f"https://api.github.com/users/{username}", headers=_headers(), timeout=15
    )
    repos_response = requests.get(
        f"https://api.github.com/users/{username}/repos", headers=_headers(), timeout=15
    )

    if profile_response.status_code != 200:
        raise ValueError(f"Profile fetch failed: {profile_response.json()}")

    profile = profile_response.json()
    repos = repos_response.json()
    if not isinstance(repos, list):
        raise ValueError(f"Repo fetch failed: {repos}")

    with ThreadPoolExecutor(max_workers=10) as executor:
        repo_data = list(executor.map(lambda r: build_repo_info(username, r), repos))

    return {
        "profile": {
            "name": profile.get("name"),
            "bio": profile.get("bio"),
            "followers": profile.get("followers"),
            "following": profile.get("following"),
            "public_repos": profile.get("public_repos"),
            "created_at": profile.get("created_at"),
        },
        "repos": repo_data,
        "events": fetch_recent_events(username),
    }
