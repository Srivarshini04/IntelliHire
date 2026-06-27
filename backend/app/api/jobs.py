import os
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import (
    Candidate,
    CapabilityProfile,
    Evidence,
    HiddenTalentProfile,
    Job,
    Ranking,
    RiskProfile,
)
from app.schemas.candidate import CandidateListItem
from app.schemas.job import JobCreate, JobResponse
from app.services.jd.jd_parser import parse_job_description

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse)
async def create_job(payload: JobCreate, db: AsyncSession = Depends(get_db)):
    role_blueprint = await parse_job_description(payload.title, payload.description)
    job = Job(
        title=payload.title,
        description=payload.description,
        role_blueprint=role_blueprint,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return JobResponse(
        job_id=job.id,
        title=job.title,
        description=job.description,
        role_blueprint=role_blueprint,
        created_at=job.created_at,
    )


@router.get("", response_model=list[JobResponse])
async def list_jobs(db: AsyncSession = Depends(get_db)):
    """List all jobs, newest first, with candidate counts."""
    result = await db.execute(select(Job).order_by(Job.created_at.desc()))
    jobs = result.scalars().all()

    count_rows = await db.execute(
        select(Candidate.job_id, func.count(Candidate.id)).group_by(Candidate.job_id)
    )
    counts = dict(count_rows.all())

    return [
        JobResponse(
            job_id=job.id,
            title=job.title,
            description=job.description,
            role_blueprint=job.role_blueprint,
            created_at=job.created_at,
            candidate_count=counts.get(job.id, 0),
        )
        for job in jobs
    ]


@router.get("/{job_id}/candidates", response_model=list[CandidateListItem])
async def list_job_candidates(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """List candidates (uploaded applications) for a job, newest first."""
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    result = await db.execute(
        select(Candidate)
        .where(Candidate.job_id == job_id)
        .order_by(Candidate.created_at.desc())
    )
    analyzed_ids = set(
        (await db.execute(select(Ranking.candidate_id).where(Ranking.job_id == job_id))).scalars().all()
    )
    return [
        CandidateListItem(
            candidate_id=c.id,
            name=c.name,
            email=c.email,
            github_url=c.github_url,
            linkedin_url=c.linkedin_url,
            has_resume=bool(c.resume_path),
            analyzed=c.id in analyzed_ids,
            created_at=c.created_at,
        )
        for c in result.scalars().all()
    ]


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse(
        job_id=job.id,
        title=job.title,
        description=job.description,
        role_blueprint=job.role_blueprint,
        created_at=job.created_at,
    )


@router.delete("/{job_id}")
async def delete_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete a job and all of its candidates and their analysis data."""
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    rows = await db.execute(
        select(Candidate.id, Candidate.resume_path).where(Candidate.job_id == job_id)
    )
    candidates = rows.all()
    candidate_ids = [c.id for c in candidates]

    # FKs have no ON DELETE CASCADE, so remove dependents explicitly, children first.
    if candidate_ids:
        for model in (CapabilityProfile, RiskProfile, HiddenTalentProfile, Ranking, Evidence):
            await db.execute(delete(model).where(model.candidate_id.in_(candidate_ids)))
    await db.execute(delete(Ranking).where(Ranking.job_id == job_id))
    await db.execute(delete(Candidate).where(Candidate.job_id == job_id))
    await db.delete(job)
    await db.commit()

    # Best-effort cleanup of stored resume files.
    for _candidate_id, resume_path in candidates:
        if resume_path and os.path.exists(resume_path):
            try:
                os.remove(resume_path)
            except OSError:
                pass

    return {"deleted": True, "job_id": str(job_id), "candidates_removed": len(candidate_ids)}
