"""Primary v2 business API — evaluation & ranking.

This is the integration point the frontend uses. It speaks business entities only
(Candidate / Job / Evaluation / Ranking); the pipeline (RoleDNA, Evidence, Graph,
Reasoning, Decision) is fully encapsulated behind the EvaluationService. Routes are
thin: validate input, call the injected service, return the business DTO.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.v2.evaluation_schemas import (
    EvaluationRequest,
    EvaluationResponse,
    RankingRequest,
    RankingResponse,
)
from app.api.v2.evaluation_service import EvaluationService, get_evaluation_service
from app.api.v2.schemas import ERROR_RESPONSES

router = APIRouter(tags=["v2: evaluations"])


@router.post(
    "/evaluations",
    response_model=EvaluationResponse,
    status_code=status.HTTP_200_OK,
    responses=ERROR_RESPONSES,
    summary="Evaluate a candidate for a job",
    description=(
        "Run the full hiring-evaluation pipeline for one candidate against one job and "
        "return a business Evaluation (recommendation, score, reasons, reservations, "
        "interview focus). The runtime derives RoleDNA, Evidence, reasoning and the "
        "decision internally — no pipeline objects are exposed."
    ),
)
async def create_evaluation(
    payload: EvaluationRequest,
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationResponse:
    return await service.evaluate(payload)


@router.post(
    "/rankings",
    response_model=RankingResponse,
    status_code=status.HTTP_200_OK,
    responses=ERROR_RESPONSES,
    summary="Rank candidates for a job",
    description=(
        "Evaluate every supplied candidate for one job and return them ranked by fit. "
        "Each candidate is evaluated through the full pipeline; one bad candidate never "
        "fails the batch."
    ),
)
async def create_ranking(
    payload: RankingRequest,
    service: EvaluationService = Depends(get_evaluation_service),
) -> RankingResponse:
    return await service.rank(payload)
