"""Full CandidateProfile schema with confidence + explainability."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.document import Document
from app.schemas.fields import (
    EducationEntry,
    ExperienceEntry,
    ExtractedField,
    ProjectEntry,
    SkillField,
    VersioningMeta,
)


class CandidateProfile(BaseModel):
    name: ExtractedField[str]
    email: ExtractedField[str] | None = None
    phone: ExtractedField[str] | None = None
    skills: list[SkillField] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    certifications: list[ExtractedField[str]] = Field(default_factory=list)
    github_url: ExtractedField[str] | None = None
    linkedin_url: ExtractedField[str] | None = None
    leetcode_url: ExtractedField[str] | None = None
    portfolio_url: ExtractedField[str] | None = None
    versioning: VersioningMeta = Field(default_factory=VersioningMeta)

    def url_fields(self) -> dict[str, str | None]:
        return {
            "github_url": self.github_url.value if self.github_url else None,
            "linkedin_url": self.linkedin_url.value if self.linkedin_url else None,
            "leetcode_url": self.leetcode_url.value if self.leetcode_url else None,
            "portfolio_url": self.portfolio_url.value if self.portfolio_url else None,
        }


class ResumeUploadResponse(BaseModel):
    document_id: UUID
    document: Document
    profile: CandidateProfile
    status: str = "draft"
    warnings: list[str] = Field(default_factory=list)
    message: str = "Profile extracted. Review before saving candidate."


class CandidateApproveRequest(BaseModel):
    job_id: UUID
    profile: CandidateProfile
    document_id: UUID | None = None


class CandidateCreate(BaseModel):
    job_id: UUID
    name: str
    email: str | None = None
    github_url: str | None = None
    linkedin_url: str | None = None


class CandidateResponse(BaseModel):
    candidate_id: UUID
    job_id: UUID
    name: str
    email: str | None = None
    github_url: str | None = None
    linkedin_url: str | None = None

    model_config = {"from_attributes": True}


class CapabilityProfileSchema(BaseModel):
    technical: float = 0.0
    execution: float = 0.0
    ownership: float = 0.0
    learning_velocity: float = 0.0
    problem_solving: float = 0.0
    domain_expertise: float = 0.0
    capability_score: float = 0.0


class RiskProfileSchema(BaseModel):
    evidence_risk: float = 0.0
    role_gap_risk: float = 0.0
    credibility_risk: float = 0.0
    risk_score: float = 0.0


class HTIProfileSchema(BaseModel):
    visibility_score: float = 0.0
    hti_score: float = 0.0


class EvidenceSchema(BaseModel):
    source_type: str
    source_url: str | None = None
    relevance_score: float | None = None
    processed_content: dict | None = None


class ExplanationSchema(BaseModel):
    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    reason: str = ""


class CandidateDetailResponse(BaseModel):
    candidate_id: UUID
    name: str
    capability: CapabilityProfileSchema | None = None
    risk: RiskProfileSchema | None = None
    hti: HTIProfileSchema | None = None
    evidence: list[EvidenceSchema] = Field(default_factory=list)
    explanation: ExplanationSchema | None = None
