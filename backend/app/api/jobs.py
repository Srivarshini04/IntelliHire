import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models import Candidate, Job
from app.schemas.candidate import CandidateResponse
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
        role_blueprint=role_blueprint.model_dump(mode="json"),
        document_id=job.document_id,
        created_at=job.created_at,
    )


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
        document_id=job.document_id,
        created_at=job.created_at,
    )
