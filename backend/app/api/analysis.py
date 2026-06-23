import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.ranking import AnalyzeResponse
from app.services.analysis_pipeline import analyze_candidate

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/jobs/{job_id}/run", response_model=dict)
async def run_job_analysis(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Analyze all candidates for a job. TODO: move to Celery worker."""
    from sqlalchemy import select

    from app.models import Candidate

    result = await db.execute(select(Candidate).where(Candidate.job_id == job_id))
    candidates = result.scalars().all()
    if not candidates:
        raise HTTPException(status_code=404, detail="No candidates found for job")

    statuses = []
    for candidate in candidates:
        status = await analyze_candidate(db, candidate.id)
        statuses.append({"candidate_id": str(candidate.id), "status": status})

    return {"job_id": str(job_id), "results": statuses}
