"""Relevance Filter — remove role-irrelevant evidence (HLD Engine #3).

Scores each evidence artifact (e.g. a GitHub repo or a project) against the
role and its required skills, then keeps the ones above the threshold. This is
what lets DELULU keep "ClinicBot / Forge / WattWise" for an AI role while
discarding "Calculator App / HTML Assignment".
"""

from __future__ import annotations

import re

KEEP_THRESHOLD = 60.0

_TOKEN_RE = re.compile(r"[a-z0-9+#.]+")


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall((text or "").lower()) if len(t) > 1}


def _keywords(role: str, jd_skills: list[str]) -> set[str]:
    kws: set[str] = set()
    for skill in jd_skills:
        kws |= _tokens(str(skill))
    # Role title words help, but drop generic filler.
    kws |= {t for t in _tokens(role) if t not in {"engineer", "developer", "senior", "junior", "lead"}}
    return kws


def score_relevance(text: str, keywords: set[str]) -> float:
    """0-100 relevance of an artifact's text to the role keywords."""
    if not keywords:
        return 80.0  # no JD context to filter against — keep by default
    hits = len(_tokens(text) & keywords)
    if hits == 0:
        return 20.0
    # 1 keyword match clears the threshold; more saturates quickly.
    return min(40.0 + hits * 30.0, 100.0)


async def filter_evidence(
    role: str,
    artifacts: list[dict],
    jd_skills: list[str] | None = None,
) -> dict:
    """Score and partition artifacts into kept vs discarded.

    Each artifact: {"name": str, "text": str, "source": str}.
    Returns kept/discarded lists plus a relevance_ratio (0-1).
    """
    keywords = _keywords(role, jd_skills or [])
    kept: list[dict] = []
    discarded: list[dict] = []

    for art in artifacts:
        score = score_relevance(art.get("text") or art.get("name") or "", keywords)
        entry = {"name": art.get("name"), "source": art.get("source"), "relevance": round(score, 1)}
        (kept if score >= KEEP_THRESHOLD else discarded).append(entry)

    total = len(kept) + len(discarded)
    return {
        "kept": kept,
        "discarded": discarded,
        "relevance_ratio": round(len(kept) / total, 3) if total else 1.0,
        "threshold": KEEP_THRESHOLD,
    }


def github_artifacts(github_evidence: dict) -> list[dict]:
    """Build relevance-scorable artifacts from a GitHub evidence package."""
    artifacts: list[dict] = []
    for repo in github_evidence.get("repos") or []:
        text = " ".join(
            str(x)
            for x in [
                repo.get("name"),
                repo.get("description"),
                repo.get("language"),
                " ".join(repo.get("topics") or []),
                " ".join((repo.get("languages") or {}).keys()),
            ]
            if x
        )
        artifacts.append({"name": repo.get("name"), "text": text, "source": "github"})
    return artifacts


def resume_artifacts(resume_evidence: dict) -> list[dict]:
    """Build artifacts from resume projects/experience when available."""
    profile = resume_evidence.get("profile") or {}
    artifacts: list[dict] = []
    for proj in profile.get("projects") or []:
        if not isinstance(proj, dict):
            continue
        name = (proj.get("name") or {}).get("value") if isinstance(proj.get("name"), dict) else proj.get("name")
        desc = (proj.get("description") or {}).get("value") if isinstance(proj.get("description"), dict) else proj.get("description")
        text = " ".join(str(x) for x in [name, desc] if x)
        if text:
            artifacts.append({"name": name or "project", "text": text, "source": "resume"})
    return artifacts
