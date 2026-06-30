"""Portfolio website extractor — fetch a candidate's personal site and distil it.

Personal portfolio / project sites are weak-but-useful evidence: they reveal
self-reported skills, project names and outbound links to stronger sources
(GitHub, LinkedIn, LeetCode). This module fetches the page, strips it to plain
text, and pulls out links + heading-like project names without any heavy HTML
dependency (regex over the markup keeps the provider dependency-light).
"""

from __future__ import annotations

import logging
import re

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 15.0
_MAX_BYTES = 1_500_000  # don't ingest huge pages

_SCRIPT_STYLE_RE = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\r\f\v]+")
_BLANKLINES_RE = re.compile(r"\n\s*\n+")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.DOTALL | re.IGNORECASE)
_HEADING_RE = re.compile(r"<h[1-3][^>]*>(.*?)</h[1-3]>", re.DOTALL | re.IGNORECASE)
_HREF_RE = re.compile(r'href\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)

_LINK_PATTERNS = {
    "github": re.compile(r"(?:https?://)?(?:www\.)?github\.com/[^/\s\"'<>]+", re.IGNORECASE),
    "linkedin": re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[^/\s\"'<>]+", re.IGNORECASE),
    "leetcode": re.compile(r"(?:https?://)?(?:www\.)?leetcode\.com/(?:u/)?[^/\s\"'<>]+", re.IGNORECASE),
}


def normalize_portfolio_url(url: str) -> str:
    url = (url or "").strip()
    if url and not re.match(r"^https?://", url, re.IGNORECASE):
        url = "https://" + url
    return url


def _strip_html(html: str) -> str:
    text = _SCRIPT_STYLE_RE.sub(" ", html)
    text = _TAG_RE.sub(" ", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&#39;", "'")
        .replace("&quot;", '"')
    )
    text = _WS_RE.sub(" ", text)
    text = _BLANKLINES_RE.sub("\n", text)
    return text.strip()


def _clean(fragment: str) -> str:
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", fragment)).strip()


def _extract_links(html: str) -> dict[str, str]:
    links: dict[str, str] = {}
    hrefs = _HREF_RE.findall(html)
    haystack = " ".join(hrefs) + " " + html
    for platform, pattern in _LINK_PATTERNS.items():
        match = pattern.search(haystack)
        if match:
            found = match.group(0)
            links[platform] = found if found.startswith("http") else "https://" + found
    return links


def _extract_projects(html: str) -> list[str]:
    projects: list[str] = []
    seen: set[str] = set()
    for raw in _HEADING_RE.findall(html):
        heading = _clean(raw)
        key = heading.lower()
        if 2 < len(heading) <= 80 and key not in seen:
            seen.add(key)
            projects.append(heading)
    return projects[:25]


def fetch_portfolio_data(portfolio_url: str) -> dict:
    """Fetch and parse a portfolio page. Raises on network/HTTP failure.

    Returns ``{url, title, text, links, projects}``.
    """
    url = normalize_portfolio_url(portfolio_url)
    if not url:
        raise ValueError("Empty portfolio URL")

    with httpx.Client(timeout=_DEFAULT_TIMEOUT, follow_redirects=True) as client:
        resp = client.get(url, headers={"User-Agent": "Mozilla/5.0 (DELULU-Portfolio)"})
        resp.raise_for_status()
        html = resp.text[:_MAX_BYTES]

    title_match = _TITLE_RE.search(html)
    return {
        "url": url,
        "title": _clean(title_match.group(1)) if title_match else "",
        "text": _strip_html(html),
        "links": _extract_links(html),
        "projects": _extract_projects(html),
    }
