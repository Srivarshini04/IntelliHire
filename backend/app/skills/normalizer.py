"""Skill normalization backed by canonical knowledge ontology."""

from __future__ import annotations

from app.knowledge.normalizer import CanonicalSkill, normalize_skill_hit


def normalize_skill_record(raw: str, source: str | None = None) -> CanonicalSkill:
    """Return canonical skill metadata for downstream engines."""
    return normalize_skill_hit(raw, source=source)


def normalize_skill(raw: str) -> str:
    """Backward-compatible API returning canonical name only."""
    return normalize_skill_record(raw).canonical_name


def normalize_skills(skills: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for skill in skills:
        normalized = normalize_skill(skill)
        key = normalized.lower()
        if key not in seen:
            seen.add(key)
            result.append(normalized)
    return result
