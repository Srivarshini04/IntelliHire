"""Profile validation — confidence thresholds before approve."""

from __future__ import annotations

from app.schemas.candidate import CandidateProfile


def validate_profile(profile: CandidateProfile, min_confidence: float = 0.5) -> list[str]:
  """Return list of validation warnings (empty = OK)."""
  warnings: list[str] = []
  if profile.name.confidence < min_confidence:
    warnings.append(f"Low confidence on name ({profile.name.confidence:.0%})")
  if not profile.skills:
    warnings.append("No skills extracted")
  if profile.email and profile.email.confidence < min_confidence:
    warnings.append(f"Low confidence on email ({profile.email.confidence:.0%})")
  return warnings
