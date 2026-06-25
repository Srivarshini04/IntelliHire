"""Step 9 — JD matching using verified evidence only."""

from __future__ import annotations

import re
from functools import lru_cache

from app.core.config import get_settings
from app.pipeline.verification import VerifiedSkill

SKILL_ALIASES: dict[str, list[str]] = {
    "fastapi": ["fast api", "python api", "rest api", "rest apis", "backend services"],
    "postgresql": ["postgres", "psql", "relational database", "sql database"],
    "aws": ["amazon web services", "cloud", "ec2", "s3", "lambda"],
    "docker": ["containerization", "containers"],
    "redis": ["in-memory cache", "caching"],
    "react": ["frontend", "reactjs", "react.js"],
    "node.js": ["nodejs", "node", "express"],
    "pytest": ["unit testing", "testing framework"],
}


def _normalize_skill(skill: str) -> str:
    return re.sub(r"[^a-z0-9.+#]", "", skill.lower())


def exact_match(jd_skill: str, candidate_skills: dict[str, int | None]) -> tuple[str | None, float]:
    jd_norm = _normalize_skill(jd_skill)
    best_skill = None
    best_score = 0.0

    for skill, score in candidate_skills.items():
        if score is None:
            continue
        skill_norm = _normalize_skill(skill)
        if jd_norm == skill_norm:
            return skill, 1.0
        aliases = SKILL_ALIASES.get(skill_norm, []) + SKILL_ALIASES.get(jd_norm, [])
        if jd_norm in skill_norm or skill_norm in jd_norm:
            best_skill, best_score = skill, 0.9
        for alias in aliases:
            if _normalize_skill(alias) == jd_norm or jd_norm in _normalize_skill(alias):
                best_skill, best_score = skill, 0.85

    return best_skill, best_score


@lru_cache(maxsize=1)
def _load_semantic_model():
    try:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer("all-MiniLM-L6-v2")
    except Exception:
        return None


def semantic_match(
    jd_skill: str,
    candidate_skills: dict[str, int | None],
    threshold: float = 0.55,
) -> tuple[str | None, float]:
    settings = get_settings()
    if not settings.semantic_matching:
        return None, 0.0

    model = _load_semantic_model()
    if model is None:
        return None, 0.0

    import numpy as np

    scored = {k: v for k, v in candidate_skills.items() if v is not None}
    if not scored:
        return None, 0.0

    jd_vec = model.encode([jd_skill], normalize_embeddings=True)
    best_skill = None
    best_sim = 0.0

    for skill in scored:
        aliases = SKILL_ALIASES.get(_normalize_skill(skill), [])
        texts = [skill, *aliases]
        skill_vecs = model.encode(texts, normalize_embeddings=True)
        sims = skill_vecs @ jd_vec.T
        sim = float(np.max(sims))
        if sim > best_sim:
            best_sim = sim
            best_skill = skill

    if best_sim >= threshold:
        return best_skill, best_sim
    return None, 0.0


def build_evidence_skill_scores(
    jd_skills: list[str],
    skill_assessments: dict,
    verified: dict[str, VerifiedSkill],
) -> dict[str, int | None]:
    """Only verified/demonstrated skills get numeric scores. Claims return None (unknown)."""
    scores: dict[str, int | None] = {}
    for skill in jd_skills:
        v = verified.get(skill)
        a = skill_assessments.get(skill)
        if not v:
            scores[skill] = None
            continue
        if v.verified and a:
            scores[skill] = a.score
        elif v.status == "weak" and a:
            scores[skill] = min(a.score, 40)
        elif v.status in ("claimed", "unknown"):
            scores[skill] = None
        elif v.status == "demonstrated" and a:
            scores[skill] = a.score
        else:
            scores[skill] = None
    return scores


def match_jd_skills(
    jd_skills: list[str],
    evidence_scores: dict[str, int | None],
    verified: dict[str, VerifiedSkill] | None = None,
) -> dict[str, dict]:
    verified = verified or {}
    matches: dict[str, dict] = {}

    for jd_skill in jd_skills:
        matched_skill, exact_conf = exact_match(jd_skill, evidence_scores)
        match_type = "exact"
        confidence = exact_conf

        if not matched_skill or confidence < 0.8:
            sem_skill, sem_conf = semantic_match(jd_skill, evidence_scores)
            if sem_skill and sem_conf > confidence:
                matched_skill, confidence = sem_skill, sem_conf
                match_type = "semantic"

        raw_score = evidence_scores.get(matched_skill) if matched_skill else None
        v = verified.get(jd_skill) or (verified.get(matched_skill) if matched_skill else None)
        verification_status = v.status if v else "unknown"

        if raw_score is None:
            score = None
        elif matched_skill and confidence < 1.0 and raw_score is not None:
            score = int(raw_score * confidence)
        else:
            score = raw_score

        matches[jd_skill] = {
            "matched_skill": matched_skill,
            "evidence_score": score,
            "match_type": match_type,
            "confidence": round(confidence, 2),
            "verification_status": verification_status,
            "verified": v.verified if v else False,
        }

    return matches


def match_jd_capabilities(
    jd_capabilities: list[str],
    candidate_capabilities: dict[str, int],
    min_score: int = 50,
) -> dict[str, dict]:
    matches: dict[str, dict] = {}
    for cap in jd_capabilities:
        key = cap.lower().replace(" ", "_").replace("-", "_")
        score = candidate_capabilities.get(key, 0)
        alt = cap.lower()
        if score == 0:
            for ck, cv in candidate_capabilities.items():
                if key in ck or ck in key:
                    score = cv
                    key = ck
                    break
        matches[cap] = {
            "capability_key": key,
            "score": score,
            "met": score >= min_score,
            "status": "met" if score >= min_score else ("partial" if score >= 30 else "unknown"),
        }
    return matches


def overall_jd_fit(
    skill_matches: dict[str, dict],
    capability_matches: dict[str, dict],
) -> int | None:
    skill_scores = [
        m["evidence_score"] for m in skill_matches.values()
        if m.get("evidence_score") is not None and m.get("verified")
    ]
    cap_scores = [m["score"] for m in capability_matches.values() if m.get("met")]

    if not skill_scores and not cap_scores:
        return None

    parts: list[float] = []
    if skill_scores:
        parts.append(sum(skill_scores) / len(skill_scores))
    if capability_matches:
        cap_vals = [m["score"] for m in capability_matches.values()]
        if cap_vals:
            parts.append(sum(cap_vals) / len(cap_vals))

    return int(min(sum(parts) / len(parts), 95)) if parts else None
