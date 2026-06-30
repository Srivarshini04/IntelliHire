"""POST /v2/evidence/extract — EvidenceProvider stage (stub)."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.v2.schemas import (
    ERROR_RESPONSES,
    ExtractEvidenceRequest,
    ExtractEvidenceResponse,
)
from app.runtime.deps import get_evidence_provider

# INTERNAL/DEBUG: single-stage endpoint, not the frontend API. Use POST /v2/evaluations.
router = APIRouter(prefix="/evidence", tags=["v2: internal/debug"])


@router.post(
    "/extract",
    response_model=ExtractEvidenceResponse,
    status_code=status.HTTP_200_OK,
    responses=ERROR_RESPONSES,
    summary="[debug] Extract atomic Evidence from a raw source",
    description=(
        "INTERNAL/DEBUG. Run one EvidenceProvider over a raw source payload and return "
        "the atomic Evidence it observes (observed facts only — DECISIONS B & C). The "
        "frontend should use POST /v2/evaluations instead."
    ),
)
async def extract_evidence(payload: ExtractEvidenceRequest) -> ExtractEvidenceResponse:
    provider = get_evidence_provider(payload.source)
    evidence = await provider.collect(payload.candidate_id, payload.raw)
    return ExtractEvidenceResponse(
        candidate_id=payload.candidate_id,
        source=payload.source,
        evidence=evidence,
    )
