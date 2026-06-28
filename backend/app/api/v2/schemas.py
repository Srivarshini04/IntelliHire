"""Request + error schemas for the DELULU v2 API.

These are NEW input contracts — they MUST NOT carry server-generated ids
(graph_id, role_dna_id, reasoning_id, decision_id, ranking_id ...). The server
assigns those. Response models are the frozen shared domain models, imported
directly by the routers (never duplicated here).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.shared.enums import EvidenceSource, RankingStage
from app.shared.models import Evidence, HiringDecision


# --------------------------------------------------------------------------- #
# Error envelope
# --------------------------------------------------------------------------- #
class ErrorResponse(BaseModel):
    """Standard error envelope returned for 4xx/5xx responses."""

    code: str = Field(..., description="Machine-readable error code, e.g. 'not_found'.")
    message: str = Field(..., description="Human-readable error description.")
    details: list[Any] | dict[str, Any] | None = Field(
        default=None, description="Optional structured context (field errors, ids, ...)."
    )


# Reusable `responses=` map for the standard error codes on every route.
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse, "description": "Bad request / invalid input."},
    404: {"model": ErrorResponse, "description": "Referenced resource not found."},
    422: {"model": ErrorResponse, "description": "Validation error."},
    500: {"model": ErrorResponse, "description": "Internal server error."},
}


# --------------------------------------------------------------------------- #
# 1. Evidence extraction
# --------------------------------------------------------------------------- #
class ExtractEvidenceRequest(BaseModel):
    """Ask an EvidenceProvider to turn one raw source payload into Evidence."""

    candidate_id: str = Field(..., min_length=1, description="Candidate the evidence is about.")
    source: EvidenceSource = Field(..., description="Which source the raw payload comes from.")
    raw: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw, source-specific payload (resume JSON, GitHub dump, ...).",
    )


class ExtractEvidenceResponse(BaseModel):
    """Evidence emitted for one (candidate, source)."""

    candidate_id: str
    source: EvidenceSource
    evidence: list[Evidence] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# 2. Graph build
# --------------------------------------------------------------------------- #
class BuildGraphRequest(BaseModel):
    """Assemble fused Evidence into a CandidateGraph. Server assigns graph_id."""

    candidate_id: str = Field(..., min_length=1)
    evidence: list[Evidence] = Field(
        ..., min_length=1, description="Evidence (any sources) for this candidate."
    )
    job_id: str | None = Field(
        default=None, description="Set when the graph is scoped to a specific role."
    )


# --------------------------------------------------------------------------- #
# 3. Role DNA
# --------------------------------------------------------------------------- #
class GenerateRoleDNARequest(BaseModel):
    """Derive RoleDNA from a JD and/or RoleBlueprint. Server assigns role_dna_id."""

    job_id: str = Field(..., min_length=1)
    jd_text: str | None = Field(default=None, description="Raw job-description text.")
    blueprint: dict[str, Any] | None = Field(
        default=None, description="Optional RoleBlueprint dict to derive from."
    )

    @model_validator(mode="after")
    def _require_one_source(self) -> "GenerateRoleDNARequest":
        if not self.jd_text and not self.blueprint:
            raise ValueError("At least one of 'jd_text' or 'blueprint' must be provided.")
        return self


# --------------------------------------------------------------------------- #
# 4. Reasoning
# --------------------------------------------------------------------------- #
class RunReasoningRequest(BaseModel):
    """Reason over a CandidateGraph against RoleDNA. Server assigns reasoning_id."""

    candidate_id: str = Field(..., min_length=1)
    job_id: str = Field(..., min_length=1)
    graph_id: str = Field(..., min_length=1, description="CandidateGraph to reason over.")
    role_dna_id: str = Field(..., min_length=1, description="RoleDNA defining the role.")


# --------------------------------------------------------------------------- #
# 5. Decision
# --------------------------------------------------------------------------- #
class GenerateDecisionRequest(BaseModel):
    """Turn reasoning into a HiringDecision. Server assigns decision_id."""

    candidate_id: str = Field(..., min_length=1)
    job_id: str = Field(..., min_length=1)
    reasoning_id: str = Field(..., min_length=1, description="CandidateReasoning to project.")
    role_dna_id: str = Field(..., min_length=1, description="RoleDNA defining the role.")


# --------------------------------------------------------------------------- #
# 6. Ranking (two-stage funnel)
# --------------------------------------------------------------------------- #
class RankCandidatesRequest(BaseModel):
    """Rank candidates for one job.

    ``stage == RETRIEVAL`` -> supply ``candidates`` (raw dicts) + ``role_dna_id``.
    ``stage == RERANK``    -> supply ``decisions`` (HiringDecisions).
    The server assigns ranked_list_id / per-row ranking_ids.
    """

    job_id: str = Field(..., min_length=1)
    stage: RankingStage = Field(..., description="RETRIEVAL (stage 1) or RERANK (stage 2).")

    # stage 1 inputs
    role_dna_id: str | None = Field(
        default=None, description="Required for RETRIEVAL: the role to score against."
    )
    candidates: list[dict[str, Any]] | None = Field(
        default=None, description="Required for RETRIEVAL: raw candidate dicts over the pool."
    )
    top_k: int | None = Field(
        default=None, ge=1, description="RETRIEVAL shortlist size (defaults applied server-side)."
    )

    # stage 2 inputs
    decisions: list[HiringDecision] | None = Field(
        default=None, description="Required for RERANK: HiringDecisions to rerank."
    )
    limit: int | None = Field(
        default=None, ge=1, description="RERANK output size (defaults to submission size)."
    )

    @model_validator(mode="after")
    def _require_stage_inputs(self) -> "RankCandidatesRequest":
        if self.stage == RankingStage.RETRIEVAL:
            if not self.candidates:
                raise ValueError("RETRIEVAL stage requires 'candidates'.")
            if not self.role_dna_id:
                raise ValueError("RETRIEVAL stage requires 'role_dna_id'.")
        elif self.stage == RankingStage.RERANK:
            if not self.decisions:
                raise ValueError("RERANK stage requires 'decisions'.")
        return self


__all__ = [
    "ErrorResponse",
    "ERROR_RESPONSES",
    "ExtractEvidenceRequest",
    "ExtractEvidenceResponse",
    "BuildGraphRequest",
    "GenerateRoleDNARequest",
    "RunReasoningRequest",
    "GenerateDecisionRequest",
    "RankCandidatesRequest",
]
