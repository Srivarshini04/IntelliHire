from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class JobDescription(BaseModel):
    required_skills: list[str] = Field(default_factory=list)
    required_capabilities: list[str] = Field(default_factory=list)


class AnalyzeRequest(BaseModel):
    github_url: str
    linkedin_url: str | None = None
    linkedin_profile: str | None = None
    resume_text: str | None = None
    jd: JobDescription = Field(default_factory=JobDescription)


class LinkedInAnalyzeRequest(BaseModel):
    linkedin_url: str | None = None
    linkedin_profile: str | None = None
    jd: JobDescription = Field(default_factory=JobDescription)


class CompareRequest(BaseModel):
    candidates: list[str] = Field(..., min_length=2)
    jd: JobDescription = Field(default_factory=JobDescription)


class SkillEvidence(BaseModel):
    skill: str
    score: int
    status: str = "unknown"
    presence: int = 0
    depth: float = 0.0
    confidence: float = 0.0
    evidence: list[str] = Field(default_factory=list)
    patterns_detected: list[str] = Field(default_factory=list)


class VerifiedSkill(BaseModel):
    skill: str
    status: str
    verified: bool
    confidence: float
    github_evidence: list[str] = Field(default_factory=list)
    claim_sources: list[str] = Field(default_factory=list)
    explanation: str = ""


class EvidenceStrengthSchema(BaseModel):
    repository_count: int = 0
    independent_projects: int = 0
    months_observed: float = 0.0
    maintenance_score: float = 0.0
    consistency_index: float = 0.0


class FeatureEvidence(BaseModel):
    feature: str
    score: int
    depth: float = 0.0
    confidence: float = 0.0
    evidence: list[str] = Field(default_factory=list)
    repositories: list[str] = Field(default_factory=list)
    evidence_count: int = 0
    cross_project_strength: float = 0.0
    evidence_strength: EvidenceStrengthSchema | None = None
    sources: list[str] = Field(default_factory=list)
    evidence_by_source: dict[str, list[str]] = Field(default_factory=dict)
    sub_features: dict[str, bool] = Field(default_factory=dict)
    complexity: dict[str, bool] = Field(default_factory=dict)
    evidence_channels: dict[str, bool] = Field(default_factory=dict)


class EvidenceItem(BaseModel):
    repository: str = ""
    skill: str | None = None
    capability: str | None = None
    feature: str | None = None
    signal: str
    weight: float = 1.0
    source: str = "github"
    reliability: float = 0.95


class HiddenGemResult(BaseModel):
    hidden_gem: bool
    reason: str
    production_feature_count: int = 0
    engineering_maturity: float = 0.0


class AnalyzeResponse(BaseModel):
    github_url: str
    github_username: str
    claims: dict[str, Any] = Field(default_factory=dict)
    candidate_capabilities: dict[str, int]
    skill_scores: dict[str, int | None]
    skill_assessments: dict[str, dict[str, Any]] = Field(default_factory=dict)
    verified_skills: dict[str, Any] = Field(default_factory=dict)
    candidate_features: list[str] = Field(default_factory=list)
    feature_evidence: dict[str, FeatureEvidence] = Field(default_factory=dict)
    evidence_graph: dict[str, Any] = Field(default_factory=dict)
    evidence: list[EvidenceItem]
    skill_evidence: dict[str, SkillEvidence] = Field(default_factory=dict)
    repositories_analyzed: list[str] = Field(default_factory=list)
    project_impact: dict[str, Any] = Field(default_factory=dict)
    engineering_maturity: float = 0.0
    engineering_maturity_breakdown: dict[str, int] = Field(default_factory=dict)
    hidden_gem: HiddenGemResult | None = None
    recruiter_assessment: dict[str, Any] = Field(default_factory=dict)
    jd_match: dict[str, Any] = Field(default_factory=dict)
    linkedin_extraction: dict[str, Any] | None = None
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LinkedInAnalyzeResponse(BaseModel):
    linkedin_url: str | None = None
    scrape_result: dict[str, Any] = Field(default_factory=dict)
    extraction_prompt: str = ""
    parsed_preview: dict[str, Any] = Field(default_factory=dict)
    schema_note: str = "LinkedIn URL scraped → claims extracted → verify via /analyze with github_url."


class ComparisonVerdict(BaseModel):
    github_username: str
    overall_score: int
    top_capabilities: list[str]
    capability_gaps: list[str]
    detected_features: list[str]
    maintenance_score: float
    summary: str


class CompareResponse(BaseModel):
    winner: str
    capability_winners: dict[str, str]
    skill_winners: dict[str, str]
    verdicts: list[ComparisonVerdict]
    candidates: list[AnalyzeResponse]
