"""POST /v2/role-dna/generate — RoleDNAProvider stage (stub)."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.v2.schemas import ERROR_RESPONSES, GenerateRoleDNARequest
from app.shared.models import RoleDNA

router = APIRouter(prefix="/role-dna", tags=["v2: role-dna"])


@router.post(
    "/generate",
    response_model=RoleDNA,
    status_code=status.HTTP_200_OK,
    responses=ERROR_RESPONSES,
    summary="Generate RoleDNA from a JD / blueprint",
    description=(
        "Derive rich hiring intent (explicit + latent requirements) for one role "
        "from its JD text and/or RoleBlueprint. The server assigns the "
        "role_dna_id. STUB: returns a minimal valid RoleDNA with a server-assigned "
        "id and a placeholder summary."
    ),
)
async def generate_role_dna(payload: GenerateRoleDNARequest) -> RoleDNA:
    # Stub: RoleDNAProvider not wired yet. Server assigns the role_dna_id.
    return RoleDNA(
        role_dna_id=f"roledna:{payload.job_id}",
        job_id=payload.job_id,
        role_summary="(stub) RoleDNA not yet derived.",
        metadata={"stub": True, "has_jd_text": bool(payload.jd_text), "has_blueprint": bool(payload.blueprint)},
    )
