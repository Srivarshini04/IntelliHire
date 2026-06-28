"""POST /v2/graph/build — GraphBuilder stage (stub)."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.v2.schemas import ERROR_RESPONSES, BuildGraphRequest
from app.shared.models import CandidateGraph

router = APIRouter(prefix="/graph", tags=["v2: graph"])


@router.post(
    "/build",
    response_model=CandidateGraph,
    status_code=status.HTTP_200_OK,
    responses=ERROR_RESPONSES,
    summary="Build a CandidateGraph from Evidence",
    description=(
        "Assemble a candidate's Evidence into the unified CandidateGraph "
        "(nodes, edges, evidence ledger). The server assigns the graph_id. "
        "STUB: returns a minimal valid graph with a server-assigned id and an "
        "empty topology."
    ),
)
async def build_graph(payload: BuildGraphRequest) -> CandidateGraph:
    # Stub: GraphBuilder not wired yet. Server assigns the graph_id.
    graph_id = f"graph:{payload.candidate_id}"
    if payload.job_id:
        graph_id = f"{graph_id}:{payload.job_id}"
    return CandidateGraph(
        graph_id=graph_id,
        candidate_id=payload.candidate_id,
        job_id=payload.job_id,
        nodes=[],
        edges=[],
        evidence_ledger=[],
        metadata={"stub": True, "evidence_count": len(payload.evidence)},
    )
