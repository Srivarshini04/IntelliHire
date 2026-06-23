"""Analysis pipeline orchestrator."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Candidate, Job
from app.services.capability.capability_engine import compute_capability
from app.services.evidence.github_parser import parse_github
from app.services.evidence.linkedin_parser import parse_linkedin
from app.services.evidence.relevance_engine import filter_evidence
from app.services.evidence.resume_parser import parse_resume
from app.services.hti.hti_engine import compute_hti
from app.services.ranking.explainability_engine import generate_explanation
from app.services.ranking.ranking_engine import compute_fit_score
from app.services.risk.risk_engine import compute_risk
from app.models.scoring import (
    CapabilityProfile,
    HiddenTalentProfile,
    Ranking,
    RiskProfile,
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
    if candidate.resume_path:
        evidence_data["resume"] = await parse_resume(candidate.resume_path)
    if candidate.github_url:
        evidence_data["github"] = await parse_github(candidate.github_url)
    if candidate.linkedin_url:
        evidence_data["linkedin"] = await parse_linkedin(candidate.linkedin_url)

    artifacts = list(evidence_data.keys())
    await filter_evidence(job.title, artifacts)

    capability = await compute_capability(evidence_data, role_blueprint)
    risk = await compute_risk(evidence_data, capability, role_blueprint)
    hti = await compute_hti(capability["capability_score"], {})
    confidence = 75.0
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

    await generate_explanation(candidate.name, capability, risk, hti)
    return "completed"
