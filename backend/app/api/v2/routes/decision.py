"""POST /v2/decision/generate — DecisionEngine stage (stub)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.v2.internal_schemas import GenerateDecisionDebugRequest
from app.api.v2.schemas import ERROR_RESPONSES
from app.runtime.deps import get_decision_engine
from app.shared.interfaces import DecisionEngine
from app.shared.models import HiringDecision

# INTERNAL/DEBUG: single-stage endpoint, not the frontend API. Use POST /v2/evaluations.
router = APIRouter(prefix="/decision", tags=["v2: internal/debug"])


@router.post(
    "/generate",
    response_model=HiringDecision,
    status_code=status.HTTP_200_OK,
    responses=ERROR_RESPONSES,
    summary="[debug] Generate a HiringDecision from reasoning",
    description=(
        "INTERNAL/DEBUG. Project an explicit (CandidateReasoning, RoleDNA) into a "
        "HiringDecision via the injected DecisionEngine. The frontend should use "
        "POST /v2/evaluations."
    ),
)
async def generate_decision(
    payload: GenerateDecisionDebugRequest,
    engine: DecisionEngine = Depends(get_decision_engine),
) -> HiringDecision:
    return await engine.decide(payload.reasoning, payload.role)
