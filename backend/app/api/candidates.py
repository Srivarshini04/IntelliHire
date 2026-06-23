import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.models import Candidate, Evidence, Job
from app.models.scoring import CapabilityProfile, HiddenTalentProfile, RiskProfile
from app.schemas.candidate import (
    CandidateDetailResponse,
    CandidateResponse,
    CapabilityProfileSchema,
    EvidenceSchema,
    ExplanationSchema,
    HTIProfileSchema,
    RiskProfileSchema,
)
from app.schemas.ranking import AnalyzeResponse
from app.services.analysis_pipeline import analyze_candidate
from app.services.ranking.explainability_engine import generate_explanation

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.post("", response_model=CandidateResponse)
async def upload_candidate(
    job_id: uuid.UUID = Form(...),
    name: str = Form(...),
    email: str | None = Form(None),
    github_url: str | None = Form(None),
    linkedin_url: str | None = Form(None),
    resume: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    resume_path = None
    if resume and resume.filename:
        upload_dir = Path(settings.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)
        resume_path = str(upload_dir / f"{uuid.uuid4()}_{resume.filename}")
        async with aiofiles.open(resume_path, "wb") as f:
            await f.write(await resume.read())

    candidate = Candidate(
        job_id=job_id,
        name=name,
        email=email,
        github_url=github_url,
        linkedin_url=linkedin_url,
        resume_path=resume_path,
    )
    db.add(candidate)
    await db.commit()
    await db.refresh(candidate)

    return CandidateResponse(
        candidate_id=candidate.id,
        job_id=candidate.job_id,
        name=candidate.name,
        email=candidate.email,
        github_url=candidate.github_url,
        linkedin_url=candidate.linkedin_url,
    )


@router.post("/{candidate_id}/analyze", response_model=AnalyzeResponse)
async def analyze(candidate_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    try:
        status = await analyze_candidate(db, candidate_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return AnalyzeResponse(status=status, candidate_id=candidate_id)


@router.get("/{candidate_id}", response_model=CandidateDetailResponse)
async def get_candidate_detail(candidate_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Candidate)
        .where(Candidate.id == candidate_id)
        .options(
            selectinload(Candidate.evidence),
            selectinload(Candidate.capability_profile),
            selectinload(Candidate.risk_profile),
            selectinload(Candidate.hidden_talent_profile),
        )
    )
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    explanation = None
    if candidate.capability_profile and candidate.risk_profile and candidate.hidden_talent_profile:
        explanation_data = await generate_explanation(
            candidate.name,
            {"capability_score": candidate.capability_profile.capability_score},
            {"risk_score": candidate.risk_profile.risk_score},
            {"hti_score": candidate.hidden_talent_profile.hti_score},
        )
        explanation = ExplanationSchema(**explanation_data)

    return CandidateDetailResponse(
        candidate_id=candidate.id,
        name=candidate.name,
        capability=(
            CapabilityProfileSchema.model_validate(candidate.capability_profile)
            if candidate.capability_profile
            else None
        ),
        risk=RiskProfileSchema.model_validate(candidate.risk_profile) if candidate.risk_profile else None,
        hti=HTIProfileSchema.model_validate(candidate.hidden_talent_profile)
        if candidate.hidden_talent_profile
        else None,
        evidence=[
            EvidenceSchema(
                source_type=e.source_type,
                source_url=e.source_url,
                relevance_score=e.relevance_score,
                processed_content=e.processed_content,
            )
            for e in candidate.evidence
        ],
        explanation=explanation,
    )
