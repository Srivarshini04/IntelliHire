"""GitHub Tree API — build repository map and fetch only relevant files."""

from __future__ import annotations

import base64
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import httpx
from github import Auth, Github, GithubException

from app.core.config import get_settings
from app.pipeline.repo_context import RepoContext, should_fetch_path

logger = logging.getLogger(__name__)

MAX_FILE_BYTES = 80_000
BLOB_WORKERS = 8


def _headers() -> dict[str, str]:
    settings = get_settings()
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    return headers


def _parse_full_name(full_name: str) -> tuple[str, str]:
    owner, repo = full_name.split("/", 1)
    return owner, repo


def fetch_repository_context(full_name: str, default_branch: str) -> RepoContext:
    """Tree API → repository map → targeted parallel blob fetch."""
    owner, repo = _parse_full_name(full_name)
    settings = get_settings()

    tree_paths: list[str] = []
    blob_shas: dict[str, str] = {}

    try:
        gh = Github(auth=Auth.Token(settings.github_token)) if settings.github_token else Github()
        gh_repo = gh.get_repo(full_name)
        branch = default_branch or gh_repo.default_branch
        tree = gh_repo.get_git_tree(branch, recursive=True)
        for item in tree.tree:
            if item.type == "blob" and item.path:
                tree_paths.append(item.path)
                if should_fetch_path(item.path):
                    blob_shas[item.path] = item.sha
    except GithubException as exc:
        logger.warning("Tree API fallback for %s: %s", full_name, exc)
        tree_paths, blob_shas = _fetch_tree_via_http(owner, repo, default_branch)

    files = _fetch_blobs_parallel(owner, repo, blob_shas, settings.max_fetch_files)
    logger.info("Fetched %d/%d files for %s", len(files), len(blob_shas), full_name)
    return RepoContext(
        full_name=full_name,
        default_branch=default_branch,
        tree_paths=tree_paths,
        files=files,
    )


def _fetch_tree_via_http(owner: str, repo: str, branch: str) -> tuple[list[str], dict[str, str]]:
    settings = get_settings()
    base = settings.github_api_base
    paths: list[str] = []
    blobs: dict[str, str] = {}

    with httpx.Client(headers=_headers(), timeout=30.0) as client:
        ref_resp = client.get(f"{base}/repos/{owner}/{repo}/git/ref/heads/{branch}")
        if ref_resp.status_code != 200:
            ref_resp = client.get(f"{base}/repos/{owner}/{repo}")
            ref_resp.raise_for_status()
            branch = ref_resp.json()["default_branch"]
            ref_resp = client.get(f"{base}/repos/{owner}/{repo}/git/ref/heads/{branch}")
        ref_resp.raise_for_status()
        commit_sha = ref_resp.json()["object"]["sha"]

        tree_resp = client.get(
            f"{base}/repos/{owner}/{repo}/git/trees/{commit_sha}",
            params={"recursive": "1"},
        )
        tree_resp.raise_for_status()
        for item in tree_resp.json().get("tree", []):
            if item.get("type") != "blob":
                continue
            path = item.get("path", "")
            if not path:
                continue
            paths.append(path)
            if should_fetch_path(path):
                blobs[path] = item["sha"]

    return paths, blobs


def _fetch_single_blob(
    base: str, owner: str, repo: str, path: str, sha: str
) -> tuple[str, str] | None:
    with httpx.Client(headers=_headers(), timeout=30.0) as client:
        resp = client.get(f"{base}/repos/{owner}/{repo}/git/blobs/{sha}")
        if resp.status_code != 200:
            return None
        data: dict[str, Any] = resp.json()
        if data.get("size", 0) > MAX_FILE_BYTES:
            return None
        encoding = data.get("encoding")
        content = data.get("content", "")
        if encoding == "base64":
            try:
                raw = base64.b64decode(content)
                return path, raw.decode("utf-8", errors="ignore")
            except Exception:
                return None
        if isinstance(content, str):
            return path, content
    return None


def _fetch_blobs_parallel(
    owner: str, repo: str, blob_shas: dict[str, str], max_files: int
) -> dict[str, str]:
    settings = get_settings()
    base = settings.github_api_base
    files: dict[str, str] = {}
    ordered = sorted(blob_shas.items(), key=lambda kv: _fetch_priority(kv[0]))[:max_files]

    with ThreadPoolExecutor(max_workers=BLOB_WORKERS) as pool:
        futures = {
            pool.submit(_fetch_single_blob, base, owner, repo, path, sha): path
            for path, sha in ordered
        }
        for future in as_completed(futures):
            result = future.result()
            if result:
                files[result[0]] = result[1]

    return files


def _fetch_priority(path: str) -> int:
    lower = path.lower()
    if any(name in lower for name in ("requirements", "pyproject", "package.json", "dockerfile", "readme")):
        return 0
    if ".github/workflows" in lower:
        return 1
    if "/test" in lower or lower.startswith("test"):
        return 3
    return 2
