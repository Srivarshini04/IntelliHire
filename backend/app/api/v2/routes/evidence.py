"""POST /v2/evidence/extract — EvidenceProvider stage (stub)."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.v2.schemas import (
    ERROR_RESPONSES,
    ExtractEvidenceRequest,
    ExtractEvidenceResponse,
)

router = APIRouter(prefix="/evidence", tags=["v2: evidence"])


@router.post(
    "/extract",
    response_model=ExtractEvidenceResponse,
    status_code=status.HTTP_200_OK,
    responses=ERROR_RESPONSES,
    summary="Extract atomic Evidence from a raw source",
    description=(
        "Run an EvidenceProvider over one raw source payload and return the "
        "atomic Evidence it observes. Providers emit observed facts only — never "
        "absence and never role weighting (DECISIONS B & C). STUB: returns an "
        "empty evidence list echoing the request inputs."
    ),
)
async def extract_evidence(payload: ExtractEvidenceRequest) -> ExtractEvidenceResponse:
    # Stub: no provider wired yet. Shape is valid and OpenAPI-complete.
    return ExtractEvidenceResponse(
        candidate_id=payload.candidate_id,
        source=payload.source,
        evidence=[],
    )
