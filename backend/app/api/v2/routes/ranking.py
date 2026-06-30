"""POST /v2/ranking/rank — RankingEngine two-stage funnel."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.v2.schemas import ERROR_RESPONSES, RankCandidatesRequest
from app.runtime.deps import get_ranking_engine
from app.shared.constants import DEFAULT_RETRIEVAL_TOP_K, SUBMISSION_SIZE
from app.shared.enums import RankingStage
from app.shared.interfaces import RankingEngine
from app.shared.models import RankedList, RoleDNA

# INTERNAL/DEBUG: single-stage endpoint, not the frontend API. Use POST /v2/rankings.
router = APIRouter(prefix="/ranking", tags=["v2: internal/debug"])


@router.post(
    "/rank",
    response_model=RankedList,
    status_code=status.HTTP_200_OK,
    responses=ERROR_RESPONSES,
    summary="Rank candidates (retrieval or rerank)",
    description=(
        "Two-stage ranker backed by the DeterministicRankingEngine (temporary "
        "ranking infrastructure; see docs/ranking-roadmap.md). "
        "RETRIEVAL returns an order-preserving shortlist of the candidate pool; "
        "RERANK orders the shortlist from HiringDecisions (the submitted rows). "
        "The server assigns ranked_list_id and per-row ranking_ids."
    ),
)
async def rank_candidates(
    payload: RankCandidatesRequest,
    engine: RankingEngine = Depends(get_ranking_engine),
) -> RankedList:
    # The request validator guarantees the per-stage inputs are present.
    if payload.stage == RankingStage.RETRIEVAL:
        # RoleDNA is generated on demand (Decision 3); the baseline retrieve is a
        # non-semantic pass-through, so a minimal shell keyed by role_dna_id suffices.
        role = RoleDNA(
            role_dna_id=payload.role_dna_id or f"roledna:{payload.job_id}",
            job_id=payload.job_id,
            role_summary="(retrieval: role content unused by the baseline ranker)",
        )
        items = await engine.retrieve(
            payload.job_id, role, payload.candidates or [], payload.top_k or DEFAULT_RETRIEVAL_TOP_K
        )
        return RankedList(
            ranked_list_id=f"rankedlist:{payload.job_id}:retrieval",
            job_id=payload.job_id,
            stage=RankingStage.RETRIEVAL,
            items=items,
        )
    return await engine.rerank(
        payload.job_id, payload.decisions or [], payload.limit or SUBMISSION_SIZE
    )
