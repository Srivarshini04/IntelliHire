"""Integrated Portfolio evidence service — fetch + skill extraction + JD match.

Mirrors the GitHub/LinkedIn provider shape: a fetch step pulls the page, then
self-reported skills are recovered from the page text via the canonical skill
ontology and matched against the role blueprint. Portfolio is intentionally
low-reliability (self-reported), so it complements rather than replaces the
verified GitHub/LeetCode signals.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from app.knowledge.normalizer import normalize_skill_hit
from app.services.evidence.portfolio_extractor import fetch_portfolio_data, normalize_portfolio_url
from app.skills.matching import is_covered

logger = logging.getLogger(__name__)

# Skill mentions are typically 1-3 word phrases; scan those windows against the
# ontology and keep only recognised (non-UNKNOWN) hits.
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#.\-]{1,29}")
_MAX_TEXT_TOKENS = 4000


def _jd_skills(role_blueprint: dict | None) -> list[str]:
    if not role_blueprint:
        return []
    return [str(s) for s in (role_blueprint.get("skills") or []) if str(s).strip()]


def extract_skills_from_text(text: str) -> list[str]:
    """Recover canonical skills mentioned anywhere in the portfolio text."""
    words = _WORD_RE.findall(text or "")[:_MAX_TEXT_TOKENS]
    found: list[str] = []
    seen: set[str] = set()

    def consider(phrase: str) -> None:
        hit = normalize_skill_hit(phrase)
        if hit.skill_id != "SKILL_UNKNOWN" and hit.skill_id not in seen:
            seen.add(hit.skill_id)
            found.append(hit.canonical_name)

    for i, word in enumerate(words):
        consider(word)
        if i + 1 < len(words):
            consider(f"{word} {words[i + 1]}")
        if i + 2 < len(words):
            consider(f"{word} {words[i + 1]} {words[i + 2]}")
    return found


def _analyze(raw: dict[str, Any], jd_skills: list[str]) -> dict[str, Any]:
    text = raw.get("text", "")
    skills = extract_skills_from_text(text)

    matched = [req for req in jd_skills if is_covered(req, skills=skills, text=text)]
    coverage = (len(matched) / len(jd_skills) * 100.0) if jd_skills else min(len(skills) * 6.0, 60.0)

    return {
        "source": "portfolio",
        "portfolio_url": raw.get("url"),
        "title": raw.get("title", ""),
        "skills": skills,
        "projects": raw.get("projects", []),
        "links": raw.get("links", {}),
        "word_count": len(text.split()),
        "jd_match": {
            "required": jd_skills,
            "matched": matched,
            "coverage": round(coverage, 1),
        },
    }


def _run_sync(portfolio_url: str, jd_skills: list[str]) -> dict[str, Any]:
    try:
        raw = fetch_portfolio_data(portfolio_url)
    except Exception as exc:  # noqa: BLE001 — network/HTTP errors degrade gracefully
        logger.warning("Portfolio fetch failed for %s: %s", portfolio_url, exc)
        return {
            "source": "portfolio",
            "portfolio_url": normalize_portfolio_url(portfolio_url),
            "error": str(exc),
        }
    return _analyze(raw, jd_skills)


async def analyze_portfolio_evidence(
    portfolio_url: str,
    role_blueprint: dict | None = None,
) -> dict[str, Any]:
    """Full portfolio evidence package for the hiring pipeline."""
    if not portfolio_url or not portfolio_url.strip():
        return {"source": "portfolio", "portfolio_url": portfolio_url, "error": "No portfolio URL provided"}

    jd_skills = _jd_skills(role_blueprint)
    return await asyncio.to_thread(_run_sync, portfolio_url, jd_skills)
