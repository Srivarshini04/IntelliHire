"""Ranking domain models.

A CandidateRanking row is what gets submitted. ``reasoning`` is the required
free-text column from the challenge submission spec; ``stage`` records whether it
came from cheap retrieval (stage 1) or full reasoning-based rerank (stage 2).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.shared.enums import RankingStage


class CandidateRanking(BaseModel):
    """One ranked candidate for one job."""

    ranking_id: str = Field(..., description="Stable id, e.g. 'ranking:j1:c1'.")
    job_id: str
    candidate_id: str
    rank: int = Field(..., ge=1, description="1-based position.")
    score: float = Field(ge=0.0, le=1.0, description="Submission score (0..1).")
    stage: RankingStage
    reasoning: str = Field("", description="Required submission column; for rerank rows this is evidence-derived.")
    decision_ref: str | None = Field(default=None, description="HiringDecision id, when stage == RERANK.")
    metadata: dict[str, Any] = Field(default_factory=dict)


class RankedList(BaseModel):
    """An ordered set of CandidateRanking rows for one job (e.g. the top 100)."""

    ranked_list_id: str = Field(..., description="Stable id, e.g. 'rankedlist:j1:rerank'.")
    job_id: str
    stage: RankingStage
    items: list[CandidateRanking] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)
