"""Deterministic URL extraction stage for resumes."""

from __future__ import annotations

import re

URL_PATTERNS: dict[str, re.Pattern[str]] = {
    "github_url": re.compile(r"https?://(?:www\.)?github\.com/[A-Za-z0-9_.-]+", re.I),
    "linkedin_url": re.compile(r"https?://(?:[\w]+\.)?linkedin\.com/(?:in|company)/[A-Za-z0-9_-]+", re.I),
    "leetcode_url": re.compile(r"https?://(?:www\.)?leetcode\.com/(?:u/)?[A-Za-z0-9_-]+", re.I),
    "gitlab_url": re.compile(r"https?://(?:www\.)?gitlab\.com/[A-Za-z0-9_.-]+", re.I),
    "kaggle_url": re.compile(r"https?://(?:www\.)?kaggle\.com/[A-Za-z0-9_.-]+", re.I),
    "huggingface_url": re.compile(r"https?://(?:www\.)?huggingface\.co/[A-Za-z0-9_.-]+", re.I),
    "portfolio_url": re.compile(r"https?://[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?:/[^\s]*)?", re.I),
    "stackoverflow_url": re.compile(r"https?://(?:www\.)?stackoverflow\.com/users/\d+/[A-Za-z0-9_-]+", re.I),
}


def extract_urls(text: str) -> dict[str, str]:
    hits: dict[str, str] = {}
    for field, pattern in URL_PATTERNS.items():
        if field == "portfolio_url":
            continue
        match = pattern.search(text)
        if match:
            hits[field] = match.group(0)

    # Portfolio should avoid duplicating known platform URLs/domains.
    known_domains = (
        "github.com",
        "linkedin.com",
        "leetcode.com",
        "gitlab.com",
        "kaggle.com",
        "huggingface.co",
        "stackoverflow.com",
    )
    for match in URL_PATTERNS["portfolio_url"].finditer(text):
        candidate = match.group(0)
        if any(domain in candidate.lower() for domain in known_domains):
            continue
        hits["portfolio_url"] = candidate
        break

    return hits
