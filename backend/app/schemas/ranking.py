from uuid import UUID

from pydantic import BaseModel


class RankingItem(BaseModel):
    candidate_id: UUID
    candidate: str
    fit_score: float
    risk: float
    hti: float
    confidence: float
    rank: int
    recommendation: str | None = None


class AnalyzeResponse(BaseModel):
    status: str
    candidate_id: UUID
