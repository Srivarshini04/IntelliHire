import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.documents.service import build_document
from app.intelligence.resume.profile_extractor import extract_profile
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
from app.services.analysis_pipeline import analyze_candidate, analyze_candidate_in_background
from app.services.evidence.normalizer import normalize
from app.services.ranking.explainability_engine import generate_explanation
from app.services.summary.summary_engine import build_candidate_summary

router = APIRouter(prefix="/candidates", tags=["candidates"])


def _clean_url(value: str | None) -> str | None:
    """Treat blank/whitespace-only form values as 'not provided'."""
    value = (value or "").strip()
    return value or None


@router.post("", response_model=CandidateResponse)
async def upload_candidate(
    background_tasks: BackgroundTasks,
    job_id: uuid.UUID = Form(...),
    name: str | None = Form(None),
    email: str | None = Form(None),
    github_url: str | None = Form(None),
    linkedin_url: str | None = Form(None),
    leetcode_url: str | None = Form(None),
    portfolio_url: str | None = Form(None),
    resume: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Manual links are a *fallback*: resume-extracted URLs take priority during
    # analysis. Normalize blank submissions to None so they don't shadow them.
    github_url = _clean_url(github_url)
    linkedin_url = _clean_url(linkedin_url)
    leetcode_url = _clean_url(leetcode_url)
    portfolio_url = _clean_url(portfolio_url)

    resume_path = None
    resume_bytes: bytes | None = None
    if resume and resume.filename:
        resume_bytes = await resume.read()
        upload_dir = Path(settings.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)
        resume_path = str(upload_dir / f"{uuid.uuid4()}_{resume.filename}")
        async with aiofiles.open(resume_path, "wb") as f:
            await f.write(resume_bytes)

    # Everything is in the resume: auto-fill any identity field not provided in the form.
    # Resume-extracted URLs win; the manual form values only fill the gaps.
    if resume_bytes and not (name and github_url and linkedin_url and leetcode_url and portfolio_url):
        try:
            document = build_document(resume.filename, resume_bytes)
            profile = await extract_profile(document, db=None)
            urls = profile.url_fields()
            name = name or (profile.name.value if profile.name else None)
            email = email or (profile.email.value if profile.email and profile.email.value else None)
            github_url = urls.get("github_url") or github_url
            linkedin_url = urls.get("linkedin_url") or linkedin_url
            leetcode_url = urls.get("leetcode_url") or leetcode_url
            portfolio_url = urls.get("portfolio_url") or portfolio_url
        except Exception:
            pass

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Could not determine candidate name — provide a name or a readable resume.",
        )

    candidate = Candidate(
        job_id=job_id,
        name=name,
        email=email,
        github_url=github_url,
        linkedin_url=linkedin_url,
        leetcode_url=leetcode_url,
        portfolio_url=portfolio_url,
        resume_path=resume_path,
    )
    db.add(candidate)
    await db.commit()
    await db.refresh(candidate)

    # Auto-analyze the new candidate in the background — no manual trigger needed.
    background_tasks.add_task(analyze_candidate_in_background, candidate.id)

    return CandidateResponse(
        candidate_id=candidate.id,
        job_id=candidate.job_id,
        name=candidate.name,
        email=candidate.email,
        github_url=candidate.github_url,
        linkedin_url=candidate.linkedin_url,
        leetcode_url=candidate.leetcode_url,
        portfolio_url=candidate.portfolio_url,
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
            selectinload(Candidate.job),
        )
    )
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    capability_dict = (
        CapabilityProfileSchema.model_validate(candidate.capability_profile).model_dump()
        if candidate.capability_profile
        else None
    )
    risk_dict = (
        RiskProfileSchema.model_validate(candidate.risk_profile).model_dump()
        if candidate.risk_profile
        else None
    )
    hti_dict = (
        HTIProfileSchema.model_validate(candidate.hidden_talent_profile).model_dump()
        if candidate.hidden_talent_profile
        else None
    )

    explanation = None
    if candidate.capability_profile and candidate.risk_profile and candidate.hidden_talent_profile:
        explanation_data = await generate_explanation(
            candidate.name,
            {"capability_score": candidate.capability_profile.capability_score},
            {"risk_score": candidate.risk_profile.risk_score},
            {"hti_score": candidate.hidden_talent_profile.hti_score},
        )
        explanation = ExplanationSchema(**explanation_data)

    # Holistic brief: per-source remarks + role-fit verdict from stored evidence.
    evidence_by_source = {
        e.source_type: (e.processed_content or {}) for e in candidate.evidence
    }
    required_skills = []
    if candidate.job and candidate.job.role_blueprint:
        required_skills = [str(s) for s in (candidate.job.role_blueprint.get("skills") or [])]
    summary = None
    if evidence_by_source:
        summary = build_candidate_summary(
            candidate.name,
            evidence_by_source,
            capability=capability_dict,
            risk=risk_dict,
            hti=hti_dict,
            required_skills=required_skills,
        )

    return CandidateDetailResponse(
        candidate_id=candidate.id,
        name=candidate.name,
        capability=CapabilityProfileSchema(**capability_dict) if capability_dict else None,
        risk=RiskProfileSchema(**risk_dict) if risk_dict else None,
        hti=HTIProfileSchema(**hti_dict) if hti_dict else None,
        evidence=[
            EvidenceSchema(
                source_type=e.source_type,
                source_url=e.source_url,
                relevance_score=e.relevance_score,
                processed_content=e.processed_content,
            )
            for e in candidate.evidence
        ],
        standardized_evidence=[
            normalize(e.source_type, e.processed_content or {}) for e in candidate.evidence
        ],
        explanation=explanation,
        summary=summary,
    )
