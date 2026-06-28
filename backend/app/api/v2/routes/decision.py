"""POST /v2/decision/generate — DecisionEngine stage (stub)."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.v2.schemas import ERROR_RESPONSES, GenerateDecisionRequest
from app.shared.enums import RecommendationLevel
from app.shared.models import HiringDecision

router = APIRouter(prefix="/decision", tags=["v2: decision"])


@router.post(
    "/generate",
    response_model=HiringDecision,
    status_code=status.HTTP_200_OK,
    responses=ERROR_RESPONSES,
    summary="Generate a HiringDecision from reasoning",
    description=(
        "Project a CandidateReasoning into a recruiter-facing HiringDecision "
        "(recommendation, reasons, reservations, interview focus, derived score). "
        "The server assigns the decision_id. STUB: returns a minimal valid "
        "decision flagged INSUFFICIENT_EVIDENCE."
    ),
)
async def generate_decision(payload: GenerateDecisionRequest) -> HiringDecision:
    # Stub: DecisionEngine not wired yet. Server assigns the decision_id.
    return HiringDecision(
        decision_id=f"decision:{payload.candidate_id}:{payload.job_id}",
        candidate_id=payload.candidate_id,
        job_id=payload.job_id,
        recommendation=RecommendationLevel.INSUFFICIENT_EVIDENCE,
        confidence=0.0,
        derived_score=0.0,
        summary="(stub) Decision not yet computed.",
        metadata={"stub": True, "reasoning_id": payload.reasoning_id, "role_dna_id": payload.role_dna_id},
    )
