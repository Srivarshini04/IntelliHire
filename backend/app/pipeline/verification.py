"""Cross-source verification — claims vs demonstrated evidence."""

from __future__ import annotations

from dataclasses import dataclass

from app.pipeline.evidence_sources import reliability
from app.pipeline.linkedin_parser import LinkedInExtraction
from app.pipeline.skill_assessment import SkillAssessment


@dataclass
class VerifiedSkill:
    skill: str
    status: str  # verified | claimed | demonstrated | unknown
    verified: bool
    confidence: float
    github_evidence: list[str]
    claim_sources: list[str]
    explanation: str

    def to_dict(self) -> dict:
        return {
            "skill": self.skill,
            "status": self.status,
            "verified": self.verified,
            "confidence": round(self.confidence, 2),
            "github_evidence": self.github_evidence,
            "claim_sources": self.claim_sources,
            "explanation": self.explanation,
        }


def verify_skills(
    github_assessments: dict[str, SkillAssessment],
    linkedin: LinkedInExtraction | None = None,
    resume_skill_claims: list[str] | None = None,
) -> dict[str, VerifiedSkill]:
    linkedin = linkedin or LinkedInExtraction()
    resume_skill_claims = resume_skill_claims or []

    all_skills = set(github_assessments.keys())
    all_skills |= set(linkedin.skill_claims)
    all_skills |= set(resume_skill_claims)

    results: dict[str, VerifiedSkill] = {}

    for skill in all_skills:
        gh = github_assessments.get(skill)
        gh_demonstrated = gh is not None and gh.status == "demonstrated"
        gh_weak = gh is not None and gh.status == "weak"
        gh_evidence = gh.evidence if gh else []

        claim_sources: list[str] = []
        if skill in linkedin.skill_claims:
            claim_sources.append("linkedin")
        if skill in resume_skill_claims:
            claim_sources.append("resume")

        has_claim = bool(claim_sources)

        if gh_demonstrated and has_claim:
            conf = min(reliability("github") * 0.7 + reliability(claim_sources[0]) * 0.3, 0.98)
            results[skill] = VerifiedSkill(
                skill=skill,
                status="verified",
                verified=True,
                confidence=conf,
                github_evidence=gh_evidence,
                claim_sources=claim_sources,
                explanation=f"{skill} claimed on {', '.join(claim_sources)} and verified by GitHub evidence.",
            )
        elif gh_demonstrated:
            results[skill] = VerifiedSkill(
                skill=skill,
                status="demonstrated",
                verified=True,
                confidence=reliability("github") * (gh.confidence if gh else 0.8),
                github_evidence=gh_evidence,
                claim_sources=[],
                explanation=f"{skill} demonstrated in GitHub code with no conflicting claims.",
            )
        elif gh_weak and has_claim:
            results[skill] = VerifiedSkill(
                skill=skill,
                status="claimed",
                verified=False,
                confidence=reliability(claim_sources[0]) * 0.5,
                github_evidence=gh_evidence,
                claim_sources=claim_sources,
                explanation=f"{skill} claimed on {', '.join(claim_sources)} but only weak GitHub evidence.",
            )
        elif has_claim:
            results[skill] = VerifiedSkill(
                skill=skill,
                status="claimed",
                verified=False,
                confidence=reliability(claim_sources[0]) * 0.35,
                github_evidence=[],
                claim_sources=claim_sources,
                explanation=f"{skill} claimed on {', '.join(claim_sources)} — not verified in GitHub analysis.",
            )
        elif gh_weak:
            results[skill] = VerifiedSkill(
                skill=skill,
                status="weak",
                verified=False,
                confidence=0.25,
                github_evidence=gh_evidence,
                claim_sources=[],
                explanation=f"Weak {skill} signals in GitHub only.",
            )
        else:
            results[skill] = VerifiedSkill(
                skill=skill,
                status="unknown",
                verified=False,
                confidence=0.0,
                github_evidence=[],
                claim_sources=[],
                explanation=f"No evidence or claims found for {skill}.",
            )

    return results
