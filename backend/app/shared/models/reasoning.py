"""Reasoning + decision domain models.

The ReasoningEngine consumes (CandidateGraph + RoleDNA) and produces
CandidateReasoning. The DecisionEngine turns that into a HiringDecision whose
numeric ``derived_score`` is a *projection* of the reasoning — not its source.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.shared.enums import (
    GapSeverity,
    Intensity,
    RecommendationAction,
    RecommendationLevel,
)


class ReasoningClaim(BaseModel):
    """One judgment the engine makes about the candidate, with its evidence."""

    claim_id: str
    statement: str = Field(..., description="e.g. 'Strong production backend engineer'.")
    entity_refs: list[str] = Field(default_factory=list, description="Graph node ids the claim concerns.")
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    counter_evidence_ids: list[str] = Field(
        default_factory=list, description="DECISION A: contradicting evidence surfaces here."
    )
    confidence: float = Field(ge=0.0, le=1.0, description="How sure we are of the claim itself.")
    materiality: Intensity = Field(
        default=Intensity.MEDIUM,
        description="DECISION B: role-relative importance, derived from RoleDNA at reason time.",
    )
    conclusion: str = Field(..., description="The reasoned takeaway for recruiters.")


class CandidateGap(BaseModel):
    """A required-but-absent signal (DECISION C — computed, never emitted by providers)."""

    requirement: str = Field(..., description="What RoleDNA expected (e.g. 'Kubernetes in production').")
    entity_ref: str | None = None
    severity: GapSeverity = GapSeverity.MODERATE
    note: str = ""


class CandidateReasoning(BaseModel):
    """Structured output of the ReasoningEngine for one (candidate, job)."""

    schema_version: Literal["1.0"] = "1.0"
    reasoning_id: str = Field(..., description="Stable id, e.g. 'reasoning:c1:j1'.")
    candidate_id: str
    job_id: str
    claims: list[ReasoningClaim] = Field(default_factory=list)
    gaps: list[CandidateGap] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    overall_confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class InterviewFocus(BaseModel):
    """A targeted area to probe in interview — usually a gap or uncertainty."""

    topic: str
    rationale: str = Field(..., description="Why this matters (the gap/uncertainty it addresses).")
    suggested_questions: list[str] = Field(default_factory=list)


class Recommendation(BaseModel):
    """A discrete recruiter-facing recommendation/action."""

    action: RecommendationAction
    rationale: str
    priority: int = Field(default=1, ge=1, description="1 = highest priority.")


class HiringDecision(BaseModel):
    """Recruiter-facing decision derived from CandidateReasoning."""

    schema_version: Literal["1.0"] = "1.0"
    decision_id: str = Field(..., description="Stable id, e.g. 'decision:c1:j1'.")
    candidate_id: str
    job_id: str
    recommendation: RecommendationLevel
    confidence: float = Field(ge=0.0, le=1.0)
    derived_score: float = Field(
        ge=0.0, le=1.0, description="Projection of the reasoning into a scalar; feeds the Reranker."
    )
    reasons: list[str] = Field(default_factory=list)
    reservations: list[str] = Field(default_factory=list)
    interview_focus: list[InterviewFocus] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    summary: str = Field("", description="Short recruiter-readable rationale; basis for the `reasoning` column.")
    decided_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)
