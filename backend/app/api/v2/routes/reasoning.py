"""POST /v2/reasoning/run — ReasoningEngine stage (stub)."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.v2.schemas import ERROR_RESPONSES, RunReasoningRequest
from app.shared.models import CandidateReasoning

router = APIRouter(prefix="/reasoning", tags=["v2: reasoning"])


@router.post(
    "/run",
    response_model=CandidateReasoning,
    status_code=status.HTTP_200_OK,
    responses=ERROR_RESPONSES,
    summary="Run reasoning over a CandidateGraph + RoleDNA",
    description=(
        "Reason over (CandidateGraph, RoleDNA): resolve contradictions, compute "
        "role-relative materiality, and detect absent-but-required signals. The "
        "server assigns the reasoning_id. STUB: returns a minimal valid "
        "CandidateReasoning with no claims/gaps."
    ),
)
async def run_reasoning(payload: RunReasoningRequest) -> CandidateReasoning:
    # Stub: ReasoningEngine not wired yet. Server assigns the reasoning_id.
    return CandidateReasoning(
        reasoning_id=f"reasoning:{payload.candidate_id}:{payload.job_id}",
        candidate_id=payload.candidate_id,
        job_id=payload.job_id,
        claims=[],
        gaps=[],
        uncertainties=[],
        overall_confidence=0.0,
        summary="(stub) Reasoning not yet computed.",
        metadata={"stub": True, "graph_id": payload.graph_id, "role_dna_id": payload.role_dna_id},
    )
