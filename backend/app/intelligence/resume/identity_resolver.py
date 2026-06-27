"""Candidate identity resolution heuristics (warn-only, no auto-merge)."""

from __future__ import annotations

from difflib import SequenceMatcher

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candidate import Candidate
from app.schemas.candidate import CandidateProfile


async def detect_possible_duplicates(
    db: AsyncSession,
    profile: CandidateProfile,
) -> list[str]:
    warnings: list[str] = []

    email = profile.email.value.strip().lower() if profile.email and profile.email.value else None
    github = profile.github_url.value.strip() if profile.github_url and profile.github_url.value else None
    linkedin = profile.linkedin_url.value.strip() if profile.linkedin_url and profile.linkedin_url.value else None
    name = profile.name.value.strip() if profile.name and profile.name.value else ""

    if email or github or linkedin:
        filters = []
        if email:
            filters.append(Candidate.email == email)
        if github:
            filters.append(Candidate.github_url == github)
        if linkedin:
            filters.append(Candidate.linkedin_url == linkedin)
        result = await db.execute(select(Candidate).where(or_(*filters)))
        for existing in result.scalars().all():
            warnings.append(
                f"Possible existing candidate match by identity fields: {existing.id}"
            )

    if name:
        result = await db.execute(select(Candidate.id, Candidate.name))
        for candidate_id, candidate_name in result.all():
            ratio = SequenceMatcher(None, name.lower(), (candidate_name or "").lower()).ratio()
            if ratio >= 0.92:
                warnings.append(
                    f"Possible existing candidate match by name similarity: {candidate_id}"
                )

    # dedupe while keeping order
    seen: set[str] = set()
    uniq: list[str] = []
    for warning in warnings:
        if warning not in seen:
            seen.add(warning)
            uniq.append(warning)
    return uniq
