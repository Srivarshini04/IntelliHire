"""Entity resolution for skills/organizations across heterogeneous sources."""

from __future__ import annotations

from app.knowledge.normalizer import normalize_skill_hit

ORG_ALIASES: dict[str, str] = {
    "amazon": "Amazon Web Services",
    "aws": "Amazon Web Services",
    "amazon web services": "Amazon Web Services",
    "google": "Google",
    "meta": "Meta",
}


def resolve_skill(raw: str) -> tuple[str, str]:
    hit = normalize_skill_hit(raw, source="graph")
    if hit.skill_id == "SKILL_UNKNOWN":
        canonical = hit.canonical_name
        return f"SKILL_UNKNOWN::{canonical.lower().replace(' ', '_')}", canonical
    return hit.skill_id, hit.canonical_name


def resolve_organization(raw: str) -> tuple[str, str]:
    key = raw.strip().lower()
    canonical = ORG_ALIASES.get(key, raw.strip().title())
    org_id = f"ORG::{canonical.lower().replace(' ', '_')}"
    return org_id, canonical
