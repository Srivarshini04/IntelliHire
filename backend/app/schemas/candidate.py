from uuid import UUID

from pydantic import BaseModel, Field


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
