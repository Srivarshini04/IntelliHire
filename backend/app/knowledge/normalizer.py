"""Canonical knowledge normalization for skills."""

from __future__ import annotations

import re
from functools import lru_cache

from pydantic import BaseModel, Field

from app.knowledge.loader import load_skills


class CanonicalSkill(BaseModel):
    skill_id: str
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    category: str
    domain: str
    related: list[str] = Field(default_factory=list)
    embedding_key: str
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    source: str | None = None


def _norm(token: str) -> str:
    token = token.strip().lower()
    return re.sub(r"[\s\-_]+", " ", token)


@lru_cache
def _skill_index() -> dict[str, dict]:
    index: dict[str, dict] = {}
    for item in load_skills():
        canonical = item["canonical"]
        index[_norm(canonical)] = item
        for alias in item.get("aliases", []):
            index[_norm(alias)] = item
    return index


def normalize_skill_hit(raw: str, source: str | None = None) -> CanonicalSkill:
    norm = _norm(raw)
    item = _skill_index().get(norm)

    if not item:
        fallback = raw.strip().title() if raw.islower() else raw.strip()
        return CanonicalSkill(
            skill_id="SKILL_UNKNOWN",
            canonical_name=fallback,
            aliases=[],
            category="Unknown",
            domain="Unknown",
            related=[],
            embedding_key=_norm(fallback).replace(" ", "_"),
            confidence=0.65,
            source=source,
        )

    confidence = 0.98 if _norm(item["canonical"]) == norm else 0.95
    return CanonicalSkill(
        skill_id=item["skill_id"],
        canonical_name=item["canonical"],
        aliases=item.get("aliases", []),
        category=item.get("category", "Unknown"),
        domain=item.get("domain", "Unknown"),
        related=item.get("related", []),
        embedding_key=item.get("embedding_key", _norm(item["canonical"])),
        confidence=confidence,
        source=source,
    )


def normalize_skill_name(raw: str) -> str:
    return normalize_skill_hit(raw).canonical_name
