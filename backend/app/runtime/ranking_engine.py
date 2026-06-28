"""BaselineRankingEngine — minimal deterministic RankingEngine (runtime infrastructure).

Decision 2: deterministic ONLY. No LLM, no AI ranking, no heuristics, no learning,
no optimization. It exists solely to satisfy the frozen ``RankingEngine`` interface
and enable end-to-end runtime; a real scoring/rerank engine can replace it later
without any change upstream.

  rerank():  HiringDecision -> sort by derived_score -> CandidateRanking -> RankedList
  retrieve(): order-preserving shortlist (top_k). It does NOT score candidate
              quality — real retrieval scoring is out of scope for this baseline.
"""

from __future__ import annotations

from typing import Any

from app.shared.constants import DEFAULT_RETRIEVAL_TOP_K, SUBMISSION_SIZE
from app.shared.enums import RankingStage
from app.shared.models import CandidateRanking, HiringDecision, RankedList, RoleDNA


def _candidate_id(candidate: dict[str, Any], index: int) -> str:
    return str(candidate.get("candidate_id") or candidate.get("id") or f"cand_{index}")


class BaselineRankingEngine:
    """Deterministic two-stage ranker. Implements the frozen RankingEngine protocol."""

    async def retrieve(
        self,
        job_id: str,
        role: RoleDNA,
        candidates: list[dict[str, Any]],
        top_k: int = DEFAULT_RETRIEVAL_TOP_K,
    ) -> list[CandidateRanking]:
        """Order-preserving shortlist of the first ``top_k`` candidates (no quality scoring)."""
        shortlist = list(candidates)[: max(0, top_k)]
        n = len(shortlist) or 1
        return [
            CandidateRanking(
                ranking_id=f"ranking:{job_id}:{_candidate_id(c, i)}",
                job_id=job_id,
                candidate_id=_candidate_id(c, i),
                rank=i + 1,
                score=round((n - i) / n, 6),  # positional placeholder, NOT a quality score
                stage=RankingStage.RETRIEVAL,
                reasoning="shortlisted (baseline deterministic pass-through; not quality-scored)",
            )
            for i, c in enumerate(shortlist)
        ]

    async def rerank(
        self,
        job_id: str,
        decisions: list[HiringDecision],
        limit: int = SUBMISSION_SIZE,
    ) -> RankedList:
        """Sort decisions by derived_score (desc), tie-break by candidate_id (deterministic)."""
        ordered = sorted(decisions, key=lambda d: (-d.derived_score, d.candidate_id))[: max(0, limit)]
        items = [
            CandidateRanking(
                ranking_id=f"ranking:{job_id}:{d.candidate_id}",
                job_id=job_id,
                candidate_id=d.candidate_id,
                rank=i + 1,
                score=d.derived_score,
                stage=RankingStage.RERANK,
                reasoning=d.summary or (d.reasons[0] if d.reasons else d.recommendation.value),
                decision_ref=d.decision_id,
            )
            for i, d in enumerate(ordered)
        ]
        return RankedList(
            ranked_list_id=f"rankedlist:{job_id}:rerank",
            job_id=job_id,
            stage=RankingStage.RERANK,
            items=items,
        )
