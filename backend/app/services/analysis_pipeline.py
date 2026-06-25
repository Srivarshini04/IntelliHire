"""Analysis pipeline orchestrator."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Candidate, Evidence, Job
from app.models.scoring import (
    CapabilityProfile,
    HiddenTalentProfile,
    Ranking,
    RiskProfile,
)
from app.services.capability.capability_engine import compute_capability
from app.services.evidence.github_parser import parse_github
from app.services.evidence.linkedin_parser import parse_linkedin
from app.services.evidence.relevance_engine import filter_evidence
from app.services.evidence.resume_parser import parse_resume
from app.services.hti.hti_engine import compute_hti
from app.services.ranking.explainability_engine import generate_explanation
from app.services.ranking.ranking_engine import compute_fit_score
from app.services.risk.risk_engine import compute_risk


async def _store_evidence(
    db: AsyncSession,
    candidate_id: uuid.UUID,
    source_type: str,
    processed: dict,
    relevance: float | None = None,
) -> None:
    db.add(
        Evidence(
            candidate_id=candidate_id,
            source_type=source_type,
            processed_content=processed,
            relevance_score=relevance,
        )
    )


async def analyze_candidate(db: AsyncSession, candidate_id: uuid.UUID) -> str:
    """Run full analysis pipeline for a candidate. Returns status."""
    result = await db.execute(
        select(Candidate)
        .where(Candidate.id == candidate_id)
        .options(
            selectinload(Candidate.job),
            selectinload(Candidate.evidence),
        )
    )
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise ValueError(f"Candidate {candidate_id} not found")

    job = candidate.job
    role_blueprint = job.role_blueprint or {}

    evidence_data: dict = {}
    resume_text: str | None = None

    if candidate.resume_path:
        resume_data = await parse_resume(candidate.resume_path)
        evidence_data["resume"] = resume_data
        resume_text = resume_data.get("raw_text")

    if candidate.github_url:
        github_evidence = await parse_github(
            candidate.github_url,
            role_blueprint=role_blueprint,
            linkedin_url=candidate.linkedin_url,
            resume_text=resume_text,
        )
        evidence_data["github"] = github_evidence
        await _store_evidence(db, candidate.id, "github", github_evidence, relevance=90.0)

    if candidate.linkedin_url:
        linkedin_data = await parse_linkedin(candidate.linkedin_url)
        evidence_data["linkedin"] = linkedin_data
        await _store_evidence(db, candidate.id, "linkedin", linkedin_data, relevance=75.0)

    if candidate.resume_path and "resume" in evidence_data:
        await _store_evidence(db, candidate.id, "resume", evidence_data["resume"], relevance=80.0)

    feature_names = (evidence_data.get("github") or {}).get("features") or []
    if feature_names:
        await filter_evidence(job.title, feature_names)

    capability = await compute_capability(evidence_data, role_blueprint)
    risk = await compute_risk(evidence_data, capability, role_blueprint)
    hti = await compute_hti(capability["capability_score"], evidence_data)

    deep = (evidence_data.get("github") or {}).get("deep") or {}
    jd_fit = (deep.get("jd_match") or {}).get("overall_fit")
    confidence = float(jd_fit) if jd_fit is not None else min(
        55.0 + len((evidence_data.get("github") or {}).get("repositories_analyzed") or []) * 5,
        95.0,
    )

    fit_score = compute_fit_score(
        capability["capability_score"],
        hti["hti_score"],
        confidence,
        risk["risk_score"],
    )

    cap_profile = CapabilityProfile(candidate_id=candidate.id, **capability)
    risk_profile = RiskProfile(candidate_id=candidate.id, **risk)
    hti_profile = HiddenTalentProfile(candidate_id=candidate.id, **hti)
    ranking = Ranking(
        job_id=job.id,
        candidate_id=candidate.id,
        fit_score=fit_score,
        confidence=confidence,
        recommendation="Interview" if fit_score >= 70 else "Review",
    )

    db.add_all([cap_profile, risk_profile, hti_profile, ranking])
    await db.commit()

    recruiter = (evidence_data.get("github") or {}).get("recruiter_assessment") or {}
    await generate_explanation(
        candidate.name,
        capability,
        risk,
        hti,
        recruiter_assessment=recruiter,
    )
    return "completed"
