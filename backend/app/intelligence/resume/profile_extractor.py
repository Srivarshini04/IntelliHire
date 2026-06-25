"""Resume Profile Extractor — Document → CandidateProfile via LLM. Phase 3 implementation."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.resume.profile_orchestrator import ResumeProfileOrchestrator
from app.schemas.candidate import CandidateProfile
from app.schemas.document import Document


async def extract_profile(
    document: Document,
    db: AsyncSession | None = None,
) -> CandidateProfile:
    orchestrator = ResumeProfileOrchestrator(db=db)
    profile, _ = await orchestrator.run(document)
    return profile
