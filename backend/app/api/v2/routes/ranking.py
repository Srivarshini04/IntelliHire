"""POST /v2/ranking/rank — RankingEngine two-stage funnel (stub)."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.v2.schemas import ERROR_RESPONSES, RankCandidatesRequest
from app.shared.models import RankedList

router = APIRouter(prefix="/ranking", tags=["v2: ranking"])


@router.post(
    "/rank",
    response_model=RankedList,
    status_code=status.HTTP_200_OK,
    responses=ERROR_RESPONSES,
    summary="Rank candidates (retrieval or rerank)",
    description=(
        "Two-stage ranker. RETRIEVAL scores the raw candidate pool against RoleDNA "
        "(cheap, deterministic). RERANK orders the shortlist from HiringDecisions "
        "(the submitted rows). The server assigns ranked_list_id and per-row "
        "ranking_ids. STUB: returns a minimal valid RankedList with no items."
    ),
)
async def rank_candidates(payload: RankCandidatesRequest) -> RankedList:
    # Stub: RankingEngine not wired yet. Server assigns ranked_list_id.
    return RankedList(
        ranked_list_id=f"rankedlist:{payload.job_id}:{payload.stage.value}",
        job_id=payload.job_id,
        stage=payload.stage,
        items=[],
        metadata={"stub": True},
    )
