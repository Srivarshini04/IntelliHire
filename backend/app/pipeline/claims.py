"""Step 1 — Extract claims from LinkedIn and resume (not evidence)."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.pipeline.linkedin_parser import LinkedInExtraction, parse_linkedin_profile


@dataclass
class Claim:
    claim: str
    category: str  # skill | technology | responsibility | leadership | scale | deployment
    source: str  # linkedin | resume
    evidence_snippet: str = ""

    def to_dict(self) -> dict:
        return {
            "claim": self.claim,
            "category": self.category,
            "source": self.source,
            "evidence_snippet": self.evidence_snippet,
        }


@dataclass
class CandidateClaims:
    skills: list[Claim] = field(default_factory=list)
    technologies: list[Claim] = field(default_factory=list)
    responsibilities: list[Claim] = field(default_factory=list)
    leadership: list[Claim] = field(default_factory=list)
    scale: list[Claim] = field(default_factory=list)
    deployment: list[Claim] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "skills": [c.to_dict() for c in self.skills],
            "technologies": [c.to_dict() for c in self.technologies],
            "responsibilities": [c.to_dict() for c in self.responsibilities],
            "leadership": [c.to_dict() for c in self.leadership],
            "scale": [c.to_dict() for c in self.scale],
            "deployment": [c.to_dict() for c in self.deployment],
            "total": (
                len(self.skills) + len(self.technologies) + len(self.responsibilities)
                + len(self.leadership) + len(self.scale) + len(self.deployment)
            ),
        }

    def all_skill_names(self) -> list[str]:
        names: list[str] = []
        for c in self.skills:
            if c.claim not in names:
                names.append(c.claim)
        return names


def _from_linkedin(extraction: LinkedInExtraction, claims: CandidateClaims) -> None:
    for skill in extraction.skill_claims:
        claims.skills.append(Claim(
            claim=f"Expert in {skill}" if "expert" not in skill.lower() else skill,
            category="skill",
            source="linkedin",
            evidence_snippet=f"LinkedIn lists {skill}",
        ))

    for feat in extraction.features:
        claims.technologies.append(Claim(
            claim=f"Experience with {feat}",
            category="technology",
            source="linkedin",
            evidence_snippet="; ".join(extraction.feature_evidence.get(feat, [])[:2]),
        ))

    for exp in extraction.experiences[:8]:
        role = exp.get("project_or_role") or exp.get("snippet", "")[:120]
        org = exp.get("organization", "")
        if role:
            snippet = f"{role} at {org}".strip(" at ")
            claims.responsibilities.append(Claim(
                claim=snippet,
                category="responsibility",
                source="linkedin",
                evidence_snippet="; ".join(exp.get("evidence", [])[:2]) if exp.get("evidence") else snippet,
            ))
        for feat in exp.get("features", []):
            claims.responsibilities.append(Claim(
                claim=f"Built {feat} systems",
                category="responsibility",
                source="linkedin",
                evidence_snippet=snippet or feat,
            ))

    if extraction.ownership and extraction.ownership != "Unknown":
        claims.leadership.append(Claim(
            claim=f"{extraction.ownership} ownership level",
            category="leadership",
            source="linkedin",
            evidence_snippet="Derived from role language on LinkedIn",
        ))

    for key, val in extraction.scale.items():
        claims.scale.append(Claim(
            claim=f"Scale: {key} = {val}",
            category="scale",
            source="linkedin",
            evidence_snippet=str(val),
        ))

    if extraction.production:
        claims.deployment.append(Claim(
            claim="Production deployment experience",
            category="deployment",
            source="linkedin",
            evidence_snippet="Profile mentions production/live systems",
        ))


def _from_resume_text(text: str, claims: CandidateClaims) -> None:
    parsed = parse_linkedin_profile(text)
    for skill in parsed.skill_claims:
        if not any(c.claim.endswith(skill) or skill in c.claim for c in claims.skills):
            claims.skills.append(Claim(
                claim=f"Resume claims {skill}",
                category="skill",
                source="resume",
                evidence_snippet=f"Resume mentions {skill}",
            ))
    for feat in parsed.features:
        claims.technologies.append(Claim(
            claim=f"Resume: {feat}",
            category="technology",
            source="resume",
            evidence_snippet="; ".join(parsed.feature_evidence.get(feat, [])[:1]),
        ))
    if parsed.production:
        claims.deployment.append(Claim(
            claim="Resume: production systems",
            category="deployment",
            source="resume",
            evidence_snippet="Resume mentions production deployment",
        ))


def extract_claims(
    linkedin: LinkedInExtraction | None = None,
    resume_text: str | None = None,
) -> CandidateClaims:
    claims = CandidateClaims()
    if linkedin:
        _from_linkedin(linkedin, claims)
    if resume_text and resume_text.strip():
        _from_resume_text(resume_text, claims)
    return claims
