"""LinkedIn extractor via Apify — mirror of github_extractor (REST) for LinkedIn."""

from __future__ import annotations

import logging

import httpx

from app.core.config import get_settings
from app.pipeline.linkedin_scraper import (
    _pick,
    _structured_profile_to_text,
    extract_linkedin_username,
    normalize_linkedin_url,
)

logger = logging.getLogger(__name__)


def _apify_token() -> str:
    settings = get_settings()
    if not settings.apify_token:
        raise ValueError("APIFY_TOKEN missing — set it in backend/.env")
    return settings.apify_token


def parse_linkedin_url(linkedin_url: str) -> dict:
    """Mirror of parse_github_url — returns {username, url}."""
    return {
        "username": extract_linkedin_username(linkedin_url),
        "url": normalize_linkedin_url(linkedin_url),
    }


def run_apify_actor(actor_id: str, run_input: dict) -> list[dict]:
    """Run an Apify actor synchronously and return its dataset items."""
    settings = get_settings()
    base = settings.apify_api_base.rstrip("/")
    # Apify identifies store actors as "username~actorname"; a literal "/" in the
    # path resolves to a different (missing) route and 404s.
    actor_path = actor_id.replace("/", "~")
    url = f"{base}/acts/{actor_path}/run-sync-get-dataset-items"

    with httpx.Client(timeout=180.0) as client:
        resp = client.post(url, params={"token": _apify_token()}, json=run_input)
        if resp.status_code == 401:
            raise ValueError("Invalid APIFY_TOKEN")
        resp.raise_for_status()
        items = resp.json()

    if not isinstance(items, list):
        raise ValueError(f"Unexpected Apify response: {items}")
    return items


def _normalize_experiences(data: dict) -> list[dict]:
    experiences = (
        data.get("experiences")
        or data.get("experience")
        or data.get("positions")
        or data.get("fullExperience")
        or []
    )
    normalized: list[dict] = []
    for exp in experiences:
        if not isinstance(exp, dict):
            continue
        normalized.append(
            {
                "title": _pick(exp, "title", "position", "role") or "",
                "company": _pick(exp, "company", "companyName", "organization") or "",
                "description": _pick(exp, "description", "summary") or "",
                "start_date": exp.get("startDate") or exp.get("starts_at") or "",
                "end_date": exp.get("endDate") or exp.get("ends_at") or "",
                "location": _pick(exp, "location") or "",
            }
        )
    return normalized


def _normalize_education(data: dict) -> list[dict]:
    education = data.get("education") or data.get("educations") or []
    normalized: list[dict] = []
    for edu in education:
        if not isinstance(edu, dict):
            continue
        normalized.append(
            {
                "school": _pick(edu, "school", "schoolName", "institution") or "",
                "degree": _pick(edu, "degree", "degreeName") or "",
                "field": _pick(edu, "fieldOfStudy", "field") or "",
            }
        )
    return normalized


def _normalize_skills(data: dict) -> list[str]:
    skills = data.get("skills") or []
    names: list[str] = []
    for s in skills:
        if isinstance(s, dict):
            n = _pick(s, "name", "skill", "title")
            if n:
                names.append(n)
        elif s:
            names.append(str(s))
    return list(dict.fromkeys(names))


def _normalize_certifications(data: dict) -> list[str]:
    certs = data.get("certifications") or data.get("certificates") or []
    names: list[str] = []
    for cert in certs:
        if isinstance(cert, dict):
            n = _pick(cert, "name", "title")
            if n:
                names.append(n)
        elif cert:
            names.append(str(cert))
    return names


def _full_name(data: dict) -> str | None:
    name = _pick(data, "fullName", "full_name", "name")
    if name:
        return name
    combined = f"{data.get('firstName') or ''} {data.get('lastName') or ''}".strip()
    return combined or None


def _location_str(data: dict) -> str | None:
    loc = data.get("location")
    if isinstance(loc, dict):
        return loc.get("linkedinText") or loc.get("parsed") or None
    return _pick(data, "location", "addressWithCountry", "geoLocationName")


def _normalize_profile(data: dict, parsed: dict) -> dict:
    """Shape an Apify dataset item into the evidence package contract."""
    return {
        "profile": {
            "name": _full_name(data),
            "headline": _pick(data, "headline", "tagline"),
            "location": _location_str(data),
            "about": _pick(data, "summary", "about", "aboutText", "description"),
            "followers": data.get("followers") or data.get("followersCount") or data.get("followerCount"),
            "connections": data.get("connections") or data.get("connectionsCount"),
            "url": parsed["url"],
        },
        "experiences": _normalize_experiences(data),
        "education": _normalize_education(data),
        "skills": _normalize_skills(data),
        "certifications": _normalize_certifications(data),
        "profile_text": _structured_profile_to_text(data),
    }


def fetch_linkedin_data(linkedin_url: str) -> dict:
    """Fetch and normalize a LinkedIn profile through Apify.

    Mirror of fetch_github_data: requires a token, resolves the target,
    calls the data provider, and returns normalized profile evidence.
    """
    settings = get_settings()
    if not settings.apify_token:
        raise ValueError("APIFY_TOKEN missing — set it in backend/.env")

    parsed = parse_linkedin_url(linkedin_url)
    run_input = {settings.apify_linkedin_input_field: [parsed["url"]]}

    items = run_apify_actor(settings.apify_linkedin_actor, run_input)
    if not items:
        raise ValueError(f"Apify returned no data for {parsed['url']}")

    data = items[0]
    if isinstance(data, dict) and data.get("error"):
        raise ValueError(f"Apify actor error: {data.get('error')}")

    return _normalize_profile(data, parsed)
