"""EvaluationService — the application service behind the primary v2 business API.

It owns orchestration: given business inputs (candidate/job + raw sources) it drives
the runtime (RoleDNA -> Evidence -> Graph -> Reasoning -> Decision -> Ranking) and shapes
the result into business DTOs. Routes stay thin (call a method, return the DTO); the
runtime stays pipeline-shaped; the frontend never sees a pipeline object.

This presentation mapping (HiringDecision -> EvaluationResponse) is an application-layer
concern, distinct from the anti-corruption layer in app/runtime/adapters (which bridges
developer implementations to the shared contracts).
"""

from __future__ import annotations

import asyncio
import logging

from app.api.v2.evaluation_schemas import (
    CandidateRef,
    EvaluationRequest,
    EvaluationResponse,
    InterviewArea,
    RankedCandidate,
    RankingRequest,
    RankingResponse,
)
from app.runtime import deps
from app.runtime.candidate_evaluation_pipeline import CandidateEvaluationPipeline
from app.shared.constants import SUBMISSION_SIZE
from app.shared.context import PipelineContext
from app.shared.enums import RecommendationLevel
from app.shared.interfaces import RankingEngine, RoleDNAProvider
from app.shared.models import HiringDecision, RoleDNA

logger = logging.getLogger(__name__)


def _to_evaluation_response(ctx: PipelineContext) -> EvaluationResponse:
    decision: HiringDecision | None = ctx.decision
    graph_meta = (ctx.graph.metadata if ctx.graph else {}) or {}
    reasoning_meta = (ctx.reasoning.metadata if ctx.reasoning else {}) or {}
    meta = {
        "graph_enabled": not graph_meta.get("graph_disabled", False),
        "reasoning_mode": reasoning_meta.get("reasoning_mode", "graph"),
        "total_ms": ctx.telemetry.get("total_ms"),
        "stages": {k: v.get("status") for k, v in ctx.telemetry.get("stages", {}).items()},
    }
    if decision is None:
        return EvaluationResponse(
            evaluation_id=f"eval:{ctx.candidate_id}:{ctx.job_id}",
            candidate_id=ctx.candidate_id,
            job_id=ctx.job_id,
            recommendation=RecommendationLevel.INSUFFICIENT_EVIDENCE,
            score=0.0,
            confidence=0.0,
            summary="Evaluation did not produce a decision.",
            status="failed",
            meta=meta,
        )
    return EvaluationResponse(
        evaluation_id=f"eval:{ctx.candidate_id}:{ctx.job_id}",
        candidate_id=ctx.candidate_id,
        job_id=ctx.job_id,
        recommendation=decision.recommendation,
        score=decision.derived_score,
        confidence=decision.confidence,
        summary=decision.summary,
        reasons=list(decision.reasons),
        reservations=list(decision.reservations),
        interview_focus=[
            InterviewArea(
                topic=focus.topic,
                rationale=focus.rationale,
                suggested_questions=list(focus.suggested_questions),
            )
            for focus in decision.interview_focus
        ],
        status="completed",
        meta=meta,
    )


class EvaluationService:
    """Drive the runtime for the business API and return business DTOs."""

    def __init__(
        self,
        *,
        role_dna_provider: RoleDNAProvider,
        pipeline: CandidateEvaluationPipeline,
        ranking_engine: RankingEngine,
    ) -> None:
        self._role = role_dna_provider
        self._pipeline = pipeline
        self._ranking = ranking_engine

    async def _role_dna(self, job_id: str, jd_text: str | None, blueprint: dict | None) -> RoleDNA:
        return await self._role.build(job_id, jd_text=jd_text, blueprint=blueprint)

    async def evaluate(self, request: EvaluationRequest) -> EvaluationResponse:
        role = await self._role_dna(request.job_id, request.jd_text, request.role_blueprint)
        ctx = await self._pipeline.evaluate_to_context(
            candidate_id=request.candidate_id,
            job_id=request.job_id,
            role_dna=role,
            raw_sources=request.sources,
        )
        return _to_evaluation_response(ctx)

    async def rank(self, request: RankingRequest) -> RankingResponse:
        role = await self._role_dna(request.job_id, request.jd_text, request.role_blueprint)

        async def _evaluate(candidate: CandidateRef) -> HiringDecision | None:
            try:
                return await self._pipeline.evaluate(
                    candidate_id=candidate.candidate_id,
                    job_id=request.job_id,
                    role_dna=role,
                    raw_sources=candidate.sources,
                )
            except Exception:  # noqa: BLE001 — one bad candidate must not fail the batch
                logger.exception("evaluation failed for candidate %s", candidate.candidate_id)
                return None

        results = await asyncio.gather(*[_evaluate(c) for c in request.candidates])
        decisions = [d for d in results if d is not None]
        ranked_list = await self._ranking.rerank(
            request.job_id, decisions, request.limit or SUBMISSION_SIZE
        )
        by_id = {d.candidate_id: d for d in decisions}
        ranked = [
            RankedCandidate(
                rank=item.rank,
                candidate_id=item.candidate_id,
                score=item.score,
                recommendation=(
                    by_id[item.candidate_id].recommendation
                    if item.candidate_id in by_id
                    else RecommendationLevel.INSUFFICIENT_EVIDENCE
                ),
                summary=(
                    by_id[item.candidate_id].summary
                    if item.candidate_id in by_id
                    else item.reasoning
                ),
            )
            for item in ranked_list.items
        ]
        return RankingResponse(
            job_id=request.job_id,
            count=len(ranked),
            ranked=ranked,
            meta={"requested": len(request.candidates), "evaluated": len(decisions)},
        )


def get_evaluation_service() -> EvaluationService:
    """DI provider for the application service (composes runtime DI providers)."""
    return EvaluationService(
        role_dna_provider=deps.get_role_dna_provider(),
        pipeline=deps.get_candidate_evaluation_pipeline(),
        ranking_engine=deps.get_ranking_engine(),
    )
