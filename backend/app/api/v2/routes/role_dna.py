"""POST /v2/role-dna/generate — RoleDNAProvider stage."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.v2.schemas import ERROR_RESPONSES, GenerateRoleDNARequest
from app.runtime.deps import get_role_dna_provider
from app.shared.interfaces import RoleDNAProvider
from app.shared.models import RoleDNA

# INTERNAL/DEBUG: single-stage endpoint, not the frontend API. Use POST /v2/evaluations.
router = APIRouter(prefix="/role-dna", tags=["v2: internal/debug"])


@router.post(
    "/generate",
    response_model=RoleDNA,
    status_code=status.HTTP_200_OK,
    responses=ERROR_RESPONSES,
    summary="Generate RoleDNA from a JD / blueprint",
    description=(
        "Derive rich hiring intent (explicit + latent requirements) for one role "
        "from its JD text and/or RoleBlueprint via the deterministic "
        "BlueprintRoleDNAProvider. The server assigns the role_dna_id."
    ),
)
async def generate_role_dna(
    payload: GenerateRoleDNARequest,
    provider: RoleDNAProvider = Depends(get_role_dna_provider),
) -> RoleDNA:
    # Deterministic enrichment of the blueprint (or minimal JD-text fallback).
    # The request validator guarantees jd_text or blueprint is present.
    return await provider.build(
        payload.job_id, jd_text=payload.jd_text, blueprint=payload.blueprint
    )
