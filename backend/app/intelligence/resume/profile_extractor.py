"""Resume Profile Extractor — Document → CandidateProfile via LLM. Phase 3 implementation."""

from __future__ import annotations

from app.schemas.candidate import CandidateProfile
from app.schemas.document import Document


async def extract_profile(document: Document) -> CandidateProfile:
  """TODO Phase 3: prompt + URL extraction + SkillNormalizer."""
  raise NotImplementedError("Profile extractor — implement in feat/resume-intelligence")
