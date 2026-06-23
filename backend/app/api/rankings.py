import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models import Candidate, Job, Ranking
from app.models.scoring import HiddenTalentProfile, RiskProfile
from app.schemas.ranking import RankingItem
from app.services.ranking.ranking_engine import rank_candidates

router = APIRouter(prefix="/jobs", tags=["rankings"])


@router.get("/{job_id}/rankings", response_model=list[RankingItem])
async def get_rankings(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    result = await db.execute(
        select(Ranking)
        .where(Ranking.job_id == job_id)
        .options(selectinload(Ranking.candidate))
    )
    rankings = result.scalars().all()

    items = []
    for r in rankings:
        risk_result = await db.execute(
            select(RiskProfile).where(RiskProfile.candidate_id == r.candidate_id)
        )
        hti_result = await db.execute(
            select(HiddenTalentProfile).where(HiddenTalentProfile.candidate_id == r.candidate_id)
        )
        risk = risk_result.scalar_one_or_none()
        hti = hti_result.scalar_one_or_none()

        items.append(
            {
                "candidate_id": r.candidate_id,
                "candidate": r.candidate.name,
                "fit_score": r.fit_score,
                "risk": risk.risk_score if risk else 0.0,
                "hti": hti.hti_score if hti else 0.0,
                "confidence": r.confidence,
                "rank": r.rank or 0,
                "recommendation": r.recommendation,
            }
        )

    ranked = await rank_candidates(items)
    return [RankingItem(**item) for item in ranked]
