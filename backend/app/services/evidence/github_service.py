"""Integrated GitHub evidence service — teammate extractor + delulu deep pipeline."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.config import get_settings
from app.github_intel.database import SessionLocal, init_github_intel_db
from app.pipeline.orchestrator import run_analysis
from app.services.evidence.github_extractor import fetch_github_data
from app.services.evidence.skill_extractor import extract_skills

logger = logging.getLogger(__name__)

_init_lock = asyncio.Lock()
_initialized = False


async def _ensure_intel_db() -> None:
    global _initialized
    async with _init_lock:
        if not _initialized:
            await asyncio.to_thread(init_github_intel_db)
            _initialized = True


def _jd_skills_from_blueprint(role_blueprint: dict | None) -> list[str]:
    if not role_blueprint:
        return []
    skills = role_blueprint.get("skills") or []
    return [str(s) for s in skills]


def _run_deep_analysis(
    github_url: str,
    jd_skills: list[str],
    linkedin_url: str | None = None,
    resume_text: str | None = None,
) -> dict[str, Any]:
    db = SessionLocal()
    try:
        result = run_analysis(
            db,
            github_url=github_url,
            jd_skills=jd_skills,
            linkedin_url=linkedin_url,
            resume_text=resume_text,
        )
        return result.model_dump(mode="json")
    finally:
        db.close()


def _run_basic_extraction(github_url: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.github_token:
        logger.warning("GITHUB_TOKEN not set — skipping basic GitHub REST extraction")
        return {"profile": {}, "repos": [], "events": [], "skills": {"languages": [], "topics": []}}

    try:
        raw = fetch_github_data(github_url)
        skills = extract_skills(raw)
        return {
            "profile": raw.get("profile", {}),
            "repos": raw.get("repos", []),
            "events": raw.get("events", []),
            "skills": skills,
        }
    except Exception as exc:
        logger.warning("Basic GitHub extraction failed: %s", exc)
        return {"profile": {}, "repos": [], "events": [], "skills": {"languages": [], "topics": []}, "error": str(exc)}


async def analyze_github_evidence(
    github_url: str,
    role_blueprint: dict | None = None,
    linkedin_url: str | None = None,
    resume_text: str | None = None,
    leetcode_url: str | None = None,
) -> dict[str, Any]:
    """Full GitHub evidence package for the hiring pipeline."""
    await _ensure_intel_db()
    jd_skills = _jd_skills_from_blueprint(role_blueprint)

    basic_task = asyncio.to_thread(_run_basic_extraction, github_url)
    deep_task = asyncio.to_thread(
        _run_deep_analysis, github_url, jd_skills, linkedin_url, resume_text
    )
    basic, deep = await asyncio.gather(basic_task, deep_task)

    leetcode: dict[str, Any] | None = None
    if leetcode_url:
        leetcode = await _evaluate_leetcode(leetcode_url)

    return {
        "source": "github",
        "github_url": github_url,
        "basic": basic,
        "deep": deep,
        "leetcode": leetcode,
        "skills": {
            "languages": list(
                dict.fromkeys(
                    basic.get("skills", {}).get("languages", [])
                    + list((deep.get("skill_scores") or {}).keys())
                )
            ),
            "topics": basic.get("skills", {}).get("topics", []),
        },
        "capabilities": deep.get("candidate_capabilities", {}),
        "features": deep.get("candidate_features", []),
        "feature_evidence": deep.get("feature_evidence", {}),
        "hidden_gem": deep.get("hidden_gem"),
        "engineering_maturity": deep.get("engineering_maturity", 0),
        "maintenance_score": (deep.get("metadata") or {}).get("maintenance_score", 0),
        "repositories_analyzed": deep.get("repositories_analyzed", []),
        "repos": basic.get("repos", []),
        "git_activity": basic.get("events", []),
        "jd_match": deep.get("jd_match", {}),
        "recruiter_assessment": deep.get("recruiter_assessment", {}),
        "evidence_graph": deep.get("evidence_graph", {}),
    }


async def _evaluate_leetcode(leetcode_url: str) -> dict[str, Any] | None:
    try:
        from app.services.evidence.leetcode_engine import LeetCodeEvaluator

        return await asyncio.to_thread(LeetCodeEvaluator.evaluate, leetcode_url)
    except Exception as exc:
        logger.warning("LeetCode evaluation failed: %s", exc)
        return {"error": str(exc)}
