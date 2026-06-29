"""RankingOrchestrator — batch orchestration (Decision 4).

For each (shortlisted) candidate: run the CandidateEvaluationPipeline to produce a
HiringDecision, then hand all decisions to the RankingEngine to produce the final
RankedList. Pure coordination — no evaluation, ranking, or extraction logic.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.runtime.candidate_evaluation_pipeline import CandidateEvaluationPipeline
from app.shared.constants import DEFAULT_RETRIEVAL_TOP_K, SUBMISSION_SIZE
from app.shared.interfaces import RankingEngine
from app.shared.models import HiringDecision, RankedList, RoleDNA

logger = logging.getLogger(__name__)


def _candidate_id(candidate: dict[str, Any], index: int) -> str:
    return str(candidate.get("candidate_id") or candidate.get("id") or f"cand_{index}")


class RankingOrchestrator:
    """Coordinate per-candidate evaluation + batch ranking for one job."""

    def __init__(
        self,
        *,
        evaluation_pipeline: CandidateEvaluationPipeline,
        ranking_engine: RankingEngine,
        max_concurrency: int | None = None,
    ) -> None:
        self._pipeline = evaluation_pipeline
        self._ranking = ranking_engine
        self._sem = asyncio.Semaphore(max_concurrency) if max_concurrency else None

    async def _evaluate_one(
        self, job_id: str, role_dna: RoleDNA, candidate: dict[str, Any], index: int
    ) -> HiringDecision | None:
        cid = _candidate_id(candidate, index)
        raw = candidate.get("raw_sources") or {}

        async def _do() -> HiringDecision | None:
            try:
                return await self._pipeline.evaluate(
                    candidate_id=cid, job_id=job_id, role_dna=role_dna, raw_sources=raw
                )
            except Exception:  # noqa: BLE001 — one bad candidate must not fail the batch
                logger.exception("evaluation failed for candidate %s (job %s)", cid, job_id)
                return None

        if self._sem is not None:
            async with self._sem:
                return await _do()
        return await _do()

    async def rank(
        self,
        *,
        job_id: str,
        role_dna: RoleDNA,
        candidates: list[dict[str, Any]],
        limit: int = SUBMISSION_SIZE,
    ) -> RankedList:
        """Evaluate every candidate (concurrently) then rerank the decisions."""
        results = await asyncio.gather(
            *[self._evaluate_one(job_id, role_dna, c, i) for i, c in enumerate(candidates)]
        )
        decisions = [d for d in results if d is not None]
        logger.info(
            "job %s: %d/%d candidates evaluated; reranking", job_id, len(decisions), len(candidates)
        )
        return await self._ranking.rerank(job_id, decisions, limit)

    async def run_two_stage(
        self,
        *,
        job_id: str,
        role_dna: RoleDNA,
        candidates: list[dict[str, Any]],
        top_k: int = DEFAULT_RETRIEVAL_TOP_K,
        limit: int = SUBMISSION_SIZE,
    ) -> RankedList:
        """Full funnel: retrieve a shortlist, evaluate only those, then rerank."""
        shortlist_rows = await self._ranking.retrieve(job_id, role_dna, candidates, top_k)
        keep = {row.candidate_id for row in shortlist_rows}
        shortlisted = [
            c for i, c in enumerate(candidates) if _candidate_id(c, i) in keep
        ]
        return await self.rank(job_id=job_id, role_dna=role_dna, candidates=shortlisted, limit=limit)
