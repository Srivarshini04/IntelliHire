"""Integrated LinkedIn evidence service — Apify extractor + LLM feature pipeline.

Mirror of github_service: a "basic" extraction (Apify profile data) runs alongside
a "deep" extraction (LLM feature/evidence pipeline) and both fold into one package.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.config import get_settings
from app.pipeline.linkedin_llm import extract_linkedin
from app.services.evidence.linkedin_extractor import fetch_linkedin_data

logger = logging.getLogger(__name__)


def _jd_skills_from_blueprint(role_blueprint: dict | None) -> list[str]:
    if not role_blueprint:
        return []
    skills = role_blueprint.get("skills") or []
    return [str(s) for s in skills]


def _jd_capabilities_from_blueprint(role_blueprint: dict | None) -> list[str]:
    if not role_blueprint:
        return []
    capabilities = role_blueprint.get("capabilities") or []
    return [str(c) for c in capabilities]


def _empty_basic() -> dict[str, Any]:
    return {
        "profile": {},
        "experiences": [],
        "education": [],
        "skills": [],
        "certifications": [],
        "profile_text": "",
    }


def _fetch_raw(linkedin_url: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.apify_token:
        logger.warning("APIFY_TOKEN not set — skipping Apify LinkedIn extraction")
        # Make the gap explicit so the UI shows "data unavailable" rather than
        # mistaking an empty profile for a weak candidate.
        return {**_empty_basic(), "error": "LinkedIn data unavailable — APIFY_TOKEN not configured"}

    try:
        return fetch_linkedin_data(linkedin_url)
    except Exception as exc:
        logger.warning("Apify LinkedIn extraction failed: %s", exc)
        return {**_empty_basic(), "error": str(exc)}


def _shape_basic(raw: dict[str, Any]) -> dict[str, Any]:
    basic = {
        "profile": raw.get("profile", {}),
        "experiences": raw.get("experiences", []),
        "education": raw.get("education", []),
        "skills": raw.get("skills", []),
        "certifications": raw.get("certifications", []),
        "profile_text": raw.get("profile_text", ""),
    }
    if raw.get("error"):
        basic["error"] = raw["error"]
    return basic


def _run_deep_analysis(
    profile_text: str,
    jd_skills: list[str],
    jd_capabilities: list[str],
) -> dict[str, Any]:
    if not profile_text:
        return {
            "features": [],
            "feature_evidence": {},
            "skill_claims": [],
            "scale": {},
            "ownership": "Unknown",
            "production": False,
            "experiences": [],
            "extraction_source": "none",
        }

    extraction, _source = extract_linkedin(profile_text, jd_skills, jd_capabilities)
    return extraction.to_dict()


async def analyze_linkedin_evidence(
    linkedin_url: str,
    role_blueprint: dict | None = None,
    resume_text: str | None = None,
) -> dict[str, Any]:
    """Full LinkedIn evidence package for the hiring pipeline."""
    jd_skills = _jd_skills_from_blueprint(role_blueprint)
    jd_capabilities = _jd_capabilities_from_blueprint(role_blueprint)

    raw = await asyncio.to_thread(_fetch_raw, linkedin_url)
    profile_text = raw.get("profile_text", "")

    basic_task = asyncio.to_thread(_shape_basic, raw)
    deep_task = asyncio.to_thread(
        _run_deep_analysis, profile_text, jd_skills, jd_capabilities
    )
    basic, deep = await asyncio.gather(basic_task, deep_task)

    experiences = deep.get("experiences", []) or basic.get("experiences", [])
    skills = basic.get("skills", []) or (deep.get("skill_claims") or [])
    # "Available" means we actually retrieved profile content to reason about —
    # not just that a URL was supplied. Empty => show as unavailable, not weak.
    available = bool(experiences or skills or deep.get("features") or basic.get("profile"))

    return {
        "source": "linkedin",
        "linkedin_url": linkedin_url,
        "available": available,
        "error": basic.get("error"),
        "basic": basic,
        "deep": deep,
        "skills": {
            "skills": list(
                dict.fromkeys(
                    basic.get("skills", [])
                    + (deep.get("skill_claims") or [])
                )
            ),
            "certifications": basic.get("certifications", []),
        },
        "features": deep.get("features", []),
        "feature_evidence": deep.get("feature_evidence", {}),
        "scale": deep.get("scale", {}),
        "ownership": deep.get("ownership", "Unknown"),
        "production": deep.get("production", False),
        "experiences": deep.get("experiences", []) or basic.get("experiences", []),
        "education": basic.get("education", []),
        "profile": basic.get("profile", {}),
        "extraction_source": deep.get("extraction_source", "none"),
    }
