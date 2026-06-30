"""Business-entity schemas for the primary v2 frontend API.

The frontend speaks ONLY business entities — Job / Candidate / Evaluation / Ranking.
It never constructs or receives pipeline objects (CandidateGraph, CandidateReasoning,
RoleDNA, Evidence, fusion objects). These DTOs are that business surface; the runtime
keeps every pipeline detail encapsulated behind them.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.shared.enums import RecommendationLevel


# --------------------------------------------------------------------------- #
# Inputs (business)
# --------------------------------------------------------------------------- #
class EvaluationRequest(BaseModel):
    """Evaluate ONE candidate for ONE job.

    Carries business context only: the candidate id, the job id + its description /
    blueprint, and the candidate's raw source payloads. The runtime derives RoleDNA,
    Evidence, reasoning and the decision internally.
    """

    candidate_id: str = Field(..., min_length=1)
    job_id: str = Field(..., min_length=1)
    jd_text: str | None = Field(default=None, description="Job description text.")
    role_blueprint: dict[str, Any] | None = Field(
        default=None, description="Structured role blueprint (if already extracted)."
    )
    sources: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw per-source candidate payloads keyed by source name "
        "(e.g. {'github': {...}, 'resume': {...}}).",
    )

    @model_validator(mode="after")
    def _require_role_context(self) -> "EvaluationRequest":
        if not self.jd_text and not self.role_blueprint:
            raise ValueError("Provide at least one of 'jd_text' or 'role_blueprint'.")
        return self


class CandidateRef(BaseModel):
    """One candidate in a ranking request: id + its raw source payloads."""

    candidate_id: str = Field(..., min_length=1)
    sources: dict[str, Any] = Field(default_factory=dict)


class RankingRequest(BaseModel):
    """Rank a set of candidates for ONE job."""

    job_id: str = Field(..., min_length=1)
    jd_text: str | None = None
    role_blueprint: dict[str, Any] | None = None
    candidates: list[CandidateRef] = Field(..., min_length=1)
    limit: int | None = Field(default=None, ge=1, description="Max ranked rows to return.")

    @model_validator(mode="after")
    def _require_role_context(self) -> "RankingRequest":
        if not self.jd_text and not self.role_blueprint:
            raise ValueError("Provide at least one of 'jd_text' or 'role_blueprint'.")
        return self


# --------------------------------------------------------------------------- #
# Outputs (business)
# --------------------------------------------------------------------------- #
class InterviewArea(BaseModel):
    """A focused area to probe in interview."""

    topic: str
    rationale: str
    suggested_questions: list[str] = Field(default_factory=list)


class EvaluationResponse(BaseModel):
    """The business result of evaluating a candidate for a job."""

    evaluation_id: str
    candidate_id: str
    job_id: str
    recommendation: RecommendationLevel
    score: float = Field(ge=0.0, le=1.0, description="Headline fit score (0..1).")
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str = ""
    reasons: list[str] = Field(default_factory=list)
    reservations: list[str] = Field(default_factory=list)
    interview_focus: list[InterviewArea] = Field(default_factory=list)
    status: Literal["completed", "failed"] = "completed"
    meta: dict[str, Any] = Field(
        default_factory=dict,
        description="Diagnostics only (graph_enabled, reasoning_mode, timings). "
        "No pipeline objects.",
    )


class RankedCandidate(BaseModel):
    """One row of a ranking result."""

    rank: int = Field(ge=1)
    candidate_id: str
    score: float = Field(ge=0.0, le=1.0)
    recommendation: RecommendationLevel
    summary: str = ""


class RankingResponse(BaseModel):
    """An ordered ranking of candidates for a job."""

    job_id: str
    count: int
    ranked: list[RankedCandidate] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)
