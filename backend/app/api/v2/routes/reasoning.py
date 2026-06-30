"""POST /v2/reasoning/run — ReasoningEngine stage (stub)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.v2.internal_schemas import RunReasoningDebugRequest
from app.api.v2.schemas import ERROR_RESPONSES
from app.runtime.deps import get_reasoning_engine
from app.shared.interfaces import ReasoningEngine
from app.shared.models import CandidateReasoning

# INTERNAL/DEBUG: single-stage endpoint, not the frontend API. Use POST /v2/evaluations.
router = APIRouter(prefix="/reasoning", tags=["v2: internal/debug"])


@router.post(
    "/run",
    response_model=CandidateReasoning,
    status_code=status.HTTP_200_OK,
    responses=ERROR_RESPONSES,
    summary="[debug] Run reasoning over a CandidateGraph + RoleDNA",
    description=(
        "INTERNAL/DEBUG. Reason over an explicit (CandidateGraph, RoleDNA) via the "
        "injected ReasoningEngine. When the graph is graph-disabled (NoOpGraphAdapter), "
        "reasoning is derived from the evidence the graph carries. The frontend should "
        "use POST /v2/evaluations."
    ),
)
async def run_reasoning(
    payload: RunReasoningDebugRequest,
    engine: ReasoningEngine = Depends(get_reasoning_engine),
) -> CandidateReasoning:
    return await engine.reason(payload.graph, payload.role)
