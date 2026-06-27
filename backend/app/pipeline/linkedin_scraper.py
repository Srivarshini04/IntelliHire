"""Fetch LinkedIn profile text from a profile URL."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class LinkedInScrapeResult:
    url: str
    profile_text: str
    scrape_source: str
    headline: str = ""
    full_name: str = ""

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "scrape_source": self.scrape_source,
            "headline": self.headline,
            "full_name": self.full_name,
            "text_length": len(self.profile_text),
        }


def normalize_linkedin_url(url: str) -> str:
    url = url.strip()
    if not url.startswith("http"):
        url = f"https://{url}"
    parsed = urlparse(url)
    if "linkedin.com" not in parsed.netloc.lower():
        raise ValueError(f"Not a LinkedIn URL: {url}")
    if "/in/" not in parsed.path.lower():
        raise ValueError(f"Expected a profile URL (linkedin.com/in/username): {url}")
    path = parsed.path.rstrip("/")
    return f"https://www.linkedin.com{path}/"


def extract_linkedin_username(url: str) -> str:
    normalized = normalize_linkedin_url(url)
    match = re.search(r"/in/([^/?#]+)", normalized, re.IGNORECASE)
    if not match:
        raise ValueError(f"Could not extract username from: {url}")
    return match.group(1)


def scrape_linkedin_url(url: str) -> LinkedInScrapeResult:
    """
    Fetch LinkedIn profile content from URL.

    Provider priority (auto):
      1. LinkdAPI (LINKDAPI_API_KEY) — recommended Proxycurl replacement
      2. Session cookie (LINKEDIN_SESSION_COOKIE) — dev/demo only
      3. Public page scrape — usually blocked by LinkedIn
    """
    normalized = normalize_linkedin_url(url)
    settings = get_settings()
    provider = settings.linkedin_data_provider.lower()

    if provider in ("auto", "linkdapi") and settings.linkdapi_api_key:
        return _scrape_via_linkdapi(normalized, settings)

    if provider in ("auto", "session") and settings.linkedin_session_cookie:
        return _scrape_via_session(normalized, settings.linkedin_session_cookie)

    if provider == "public":
        return _scrape_public_page(normalized)

    if provider == "linkdapi":
        raise ValueError(
            "LINKDAPI_API_KEY is required. Get a key at https://linkdapi.com "
            "(Proxycurl shut down in 2025 — LinkdAPI is the recommended migration path)."
        )

    raise ValueError(
        "LinkedIn URL scraping requires configuration. Options:\n"
        "  1. LINKDAPI_API_KEY — recommended (https://linkdapi.com)\n"
        "  2. LINKEDIN_SESSION_COOKIE — dev/demo only\n"
        "  3. Paste profile text in linkedin_profile instead of linkedin_url"
    )


def _scrape_via_linkdapi(url: str, settings) -> LinkedInScrapeResult:
    username = extract_linkedin_username(url)
    base = settings.linkdapi_api_base.rstrip("/")

    with httpx.Client(timeout=45.0) as client:
        resp = client.get(
            f"{base}/profile/full",
            params={"username": username},
            headers={"X-linkdapi-apikey": settings.linkdapi_api_key},
        )
        if resp.status_code == 401:
            raise ValueError("Invalid LINKDAPI_API_KEY")
        if resp.status_code == 404:
            raise ValueError(f"LinkedIn profile not found: {username}")
        resp.raise_for_status()
        payload = resp.json()

    data = payload.get("data", payload)
    text = _structured_profile_to_text(data)
    return LinkedInScrapeResult(
        url=url,
        profile_text=text,
        scrape_source="linkdapi",
        headline=_pick(data, "headline", "tagline") or "",
        full_name=_pick(data, "fullName", "full_name", "name") or "",
    )


def _pick(data: dict, *keys: str) -> str | None:
    for key in keys:
        val = data.get(key)
        if val:
            return str(val)
    return None


def _structured_profile_to_text(data: dict) -> str:
    """Normalize LinkdAPI / similar JSON into plain text for feature extraction."""
    parts: list[str] = []

    name = _pick(data, "fullName", "full_name", "name") or (
        f"{data.get('firstName') or ''} {data.get('lastName') or ''}".strip() or None
    )
    if name:
        parts.append(f"Name: {name}")
    headline = _pick(data, "headline", "tagline")
    if headline:
        parts.append(f"Headline: {headline}")
    about = _pick(data, "summary", "about", "aboutText", "description")
    if about:
        parts.append(f"About:\n{about}")

    experiences = (
        data.get("experiences")
        or data.get("experience")
        or data.get("positions")
        or data.get("fullExperience")
        or []
    )
    if experiences:
        parts.append("\nExperience:")
        for exp in experiences:
            if not isinstance(exp, dict):
                continue
            title = _pick(exp, "title", "position", "role") or ""
            company = _pick(exp, "company", "companyName", "organization") or ""
            desc = _pick(exp, "description", "summary") or ""
            period = ""
            start = exp.get("startDate") or exp.get("starts_at") or exp.get("timePeriod", {}).get("startDate")
            end = exp.get("endDate") or exp.get("ends_at") or exp.get("timePeriod", {}).get("endDate")
            if start or end:
                period = f" ({start or ''}-{end or 'present'})"
            parts.append(f"- {title} at {company}{period}")
            if desc:
                parts.append(desc)

    education = data.get("education") or data.get("educations") or []
    if education:
        parts.append("\nEducation:")
        for edu in education:
            if isinstance(edu, dict):
                school = _pick(edu, "school", "schoolName", "institution") or ""
                degree = _pick(edu, "degree", "degreeName") or ""
                parts.append(f"- {degree} at {school}".strip())

    skills = data.get("skills") or []
    if skills:
        names: list[str] = []
        for s in skills[:40]:
            if isinstance(s, dict):
                n = _pick(s, "name", "skill")
                if n:
                    names.append(n)
            elif s:
                names.append(str(s))
        if names:
            parts.append("\nSkills: " + ", ".join(names))

    certifications = data.get("certifications") or []
    if certifications:
        parts.append("\nCertifications:")
        for cert in certifications[:10]:
            if isinstance(cert, dict):
                parts.append(f"- {_pick(cert, 'name', 'title') or cert}")

    text = "\n".join(p for p in parts if p.strip())
    if len(text) < 50:
        raise ValueError("LinkedIn API returned empty profile data")
    return text


def _scrape_via_session(url: str, cookie: str) -> LinkedInScrapeResult:
    """Dev/demo: fetch page using li_at session cookie (not for production)."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Cookie": f"li_at={cookie}",
    }
    with httpx.Client(timeout=30.0, follow_redirects=True, headers=headers) as client:
        resp = client.get(url)
        resp.raise_for_status()
        html = resp.text

    text = _extract_text_from_html(html)
    if len(text) < 100:
        raise ValueError(
            "LinkedIn session scrape returned little content. "
            "Check LINKEDIN_SESSION_COOKIE or set LINKDAPI_API_KEY."
        )
    return LinkedInScrapeResult(url=url, profile_text=text, scrape_source="session_cookie")


def _scrape_public_page(url: str) -> LinkedInScrapeResult:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    with httpx.Client(timeout=25.0, follow_redirects=True, headers=headers) as client:
        resp = client.get(url, headers=headers)
        html = resp.text

    text = _extract_text_from_html(html)
    if len(text) < 80:
        raise ValueError(
            "Could not scrape LinkedIn anonymously. Set LINKDAPI_API_KEY (https://linkdapi.com) "
            "or paste profile text in linkedin_profile."
        )
    logger.warning("LinkedIn public scrape returned limited content (%d chars)", len(text))
    return LinkedInScrapeResult(url=url, profile_text=text, scrape_source="public_page")


def _extract_text_from_html(html: str) -> str:
    parts: list[str] = []
    for pattern in (
        r'<meta[^>]+property="og:description"[^>]+content="([^"]*)"',
        r'<meta[^>]+property="og:title"[^>]+content="([^"]*)"',
        r'<meta[^>]+name="description"[^>]+content="([^"]*)"',
    ):
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            parts.append(unescape(match.group(1)))

    stripped = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    stripped = re.sub(r"<[^>]+>", " ", stripped)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    if len(stripped) > 200:
        parts.append(stripped[:8000])

    return "\n\n".join(dict.fromkeys(p for p in parts if p.strip()))
