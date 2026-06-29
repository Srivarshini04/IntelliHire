"""Analysis pipeline orchestrator."""

import logging
import uuid
from pathlib import Path

import aiofiles
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.documents.service import build_document
from app.intelligence.resume.profile_extractor import extract_profile
from app.models import Candidate, Evidence, Job
from app.models.scoring import (
    CapabilityProfile,
    HiddenTalentProfile,
    Ranking,
    RiskProfile,
)
from app.services.capability.capability_engine import compute_capability
from app.services.confidence.confidence_engine import compute_confidence
from app.services.evidence.github_parser import parse_github
from app.services.evidence.leetcode_service import analyze_leetcode_evidence
from app.services.evidence.linkedin_service import analyze_linkedin_evidence
from app.services.evidence.portfolio_service import analyze_portfolio_evidence
from app.services.evidence.relevance_engine import (
    filter_evidence,
    github_artifacts,
    resume_artifacts,
)
from app.services.evidence.resume_parser import parse_resume
from app.services.hti.hti_engine import compute_hti
from app.services.ranking.explainability_engine import generate_explanation
from app.services.ranking.ranking_engine import compute_fit_score
from app.services.risk.risk_engine import compute_risk
from app.skills.matching import is_covered

logger = logging.getLogger(__name__)


async def _extract_resume_profile(resume_path: str) -> tuple[dict, dict, str | None]:
    """Run the document-intelligence layer on a resume file.

    Returns (resume_evidence, url_fields, resume_text). On any failure, falls
    back to the legacy stub parser so analysis still completes.
    """
    try:
        async with aiofiles.open(resume_path, "rb") as f:
            content = await f.read()
        document = build_document(Path(resume_path).name, content)
        # db=None: extract only, don't persist a second PROFILE_DRAFT here.
        profile = await extract_profile(document, db=None)
        return profile.model_dump(mode="json"), profile.url_fields(), document.cleaned_text
    except Exception as exc:  # noqa: BLE001
        logger.warning("Resume intelligence extraction failed (%s); using stub parser", exc)
        return await parse_resume(resume_path), {}, None


def _resume_skill_names(resume: dict) -> list[str]:
    """Flatten the extracted skill records into plain skill names."""
    names: list[str] = []
    for skill in resume.get("skills") or []:
        if isinstance(skill, dict):
            value = skill.get("canonical_name") or skill.get("normalized_name") or skill.get("name")
            if value:
                names.append(str(value))
        elif skill:
            names.append(str(skill))
    return list(dict.fromkeys(names))


def _build_resume_evidence(resume: dict, resume_text: str | None, role_blueprint: dict) -> dict:
    """Enrich the raw resume profile with a JD skill-match so it can be scored.

    This is what lets two different resumes produce different scores even when
    no GitHub/LinkedIn evidence is available.
    """
    skill_names = _resume_skill_names(resume)

    required = [str(s) for s in (role_blueprint.get("skills") or []) if str(s).strip()]
    matched: list[str] = []
    for req in required:
        if is_covered(req, skills=skill_names, text=resume_text or ""):
            matched.append(req)

    coverage = (len(matched) / len(required) * 100.0) if required else min(len(skill_names) * 6.0, 60.0)

    return {
        "profile": resume,
        "skills": skill_names,
        "jd_match": {
            "required": required,
            "matched": matched,
            "coverage": round(coverage, 1),
        },
        "text_length": len(resume_text or ""),
    }


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


async def _clear_previous_analysis(db: AsyncSession, candidate_id: uuid.UUID) -> None:
    """Remove prior analysis artifacts so the run is idempotent (re-runnable)."""
    for model in (CapabilityProfile, RiskProfile, HiddenTalentProfile, Ranking, Evidence):
        await db.execute(delete(model).where(model.candidate_id == candidate_id))


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

    await _clear_previous_analysis(db, candidate.id)

    job = candidate.job
    role_blueprint = job.role_blueprint or {}

    evidence_data: dict = {}
    resume_text: str | None = None
    url_fields: dict = {}

    if candidate.resume_path:
        resume_data, url_fields, resume_text = await _extract_resume_profile(candidate.resume_path)
        evidence_data["resume"] = _build_resume_evidence(resume_data, resume_text, role_blueprint)
        # Resume is the source of truth for identity — refresh a missing/placeholder name.
        extracted_name = (resume_data.get("name") or {}).get("value") if isinstance(resume_data.get("name"), dict) else None
        if extracted_name and (not candidate.name or candidate.name.strip().rstrip(":").lower() in {"links", "unnamed candidate", ""}):
            candidate.name = extracted_name
        extracted_email = (resume_data.get("email") or {}).get("value") if isinstance(resume_data.get("email"), dict) else None
        if extracted_email and not candidate.email:
            candidate.email = extracted_email

    # GitHub/LinkedIn URLs come from the intelligence layer first, then fall
    # back to any URL supplied manually on the candidate record.
    github_url = url_fields.get("github_url") or candidate.github_url
    linkedin_url = url_fields.get("linkedin_url") or candidate.linkedin_url
    leetcode_url = url_fields.get("leetcode_url")
    portfolio_url = url_fields.get("portfolio_url")

    # Persist newly discovered URLs back onto the candidate so the UI reflects them.
    if github_url and github_url != candidate.github_url:
        candidate.github_url = github_url
    if linkedin_url and linkedin_url != candidate.linkedin_url:
        candidate.linkedin_url = linkedin_url

    if github_url:
        # NOTE: linkedin_url is intentionally NOT passed — the GitHub deep pipeline
        # would invoke the legacy LinkedIn scraper (requires LINKDAPI key) and crash.
        # LinkedIn is handled by our dedicated Apify engine below.
        github_evidence = await parse_github(
            github_url,
            role_blueprint=role_blueprint,
            resume_text=resume_text,
            leetcode_url=leetcode_url,
        )
        evidence_data["github"] = github_evidence
        await _store_evidence(db, candidate.id, "github", github_evidence, relevance=90.0)

    if linkedin_url:
        linkedin_data = await analyze_linkedin_evidence(
            linkedin_url,
            role_blueprint=role_blueprint,
            resume_text=resume_text,
        )
        evidence_data["linkedin"] = linkedin_data
        await _store_evidence(db, candidate.id, "linkedin", linkedin_data, relevance=75.0)

    # LeetCode is a first-class verified source. The GitHub deep pipeline already
    # evaluates it when a leetcode_url is present (capability scoring reads it from
    # there), so reuse that result to avoid a second network round-trip; only call
    # the standalone provider when GitHub didn't run.
    if leetcode_url:
        leetcode_data = (evidence_data.get("github") or {}).get("leetcode")
        if not leetcode_data:
            leetcode_data = await analyze_leetcode_evidence(leetcode_url, role_blueprint=role_blueprint)
        if leetcode_data and not leetcode_data.get("error"):
            leetcode_data.setdefault("source_url", leetcode_url)
            evidence_data["leetcode"] = leetcode_data
            await _store_evidence(db, candidate.id, "leetcode", leetcode_data, relevance=85.0)

    # Portfolio is self-reported (low reliability) — it complements GitHub/LeetCode.
    if portfolio_url:
        portfolio_data = await analyze_portfolio_evidence(portfolio_url, role_blueprint=role_blueprint)
        if portfolio_data and not portfolio_data.get("error"):
            evidence_data["portfolio"] = portfolio_data
            await _store_evidence(db, candidate.id, "portfolio", portfolio_data, relevance=55.0)

    if candidate.resume_path and "resume" in evidence_data:
        await _store_evidence(db, candidate.id, "resume", evidence_data["resume"], relevance=80.0)

    # Relevance Filter (HLD #3): drop role-irrelevant artifacts (repos/projects).
    jd_skills = [str(s) for s in (role_blueprint.get("skills") or [])]
    artifacts = github_artifacts(evidence_data.get("github") or {}) + resume_artifacts(
        evidence_data.get("resume") or {}
    )
    if artifacts:
        relevance = await filter_evidence(job.title, artifacts, jd_skills)
        evidence_data["relevance"] = relevance
        await _store_evidence(db, candidate.id, "relevance", relevance, relevance=None)

    capability = await compute_capability(evidence_data, role_blueprint)
    risk = await compute_risk(evidence_data, capability, role_blueprint)

    # Role-fit blend: capability measures raw ability (radar dimensions stay as-is),
    # but the headline score is scaled toward role relevance so a candidate who
    # matches the JD outranks an equally-skilled candidate who doesn't. A perfect
    # fit keeps full capability; a zero-fit candidate retains 60%.
    role_fit = 1.0 - (risk["role_gap_risk"] / 100.0)
    capability["capability_score"] = round(
        capability["capability_score"] * (0.6 + 0.4 * role_fit), 1
    )

    hti = await compute_hti(capability["capability_score"], evidence_data)

    # Confidence Engine (HLD #6): trustworthiness from evidence quantity,
    # quality (relevance-weighted) and cross-source agreement.
    confidence_profile = await compute_confidence(evidence_data, capability, role_blueprint)
    confidence = confidence_profile["confidence_score"]

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


async def analyze_candidate_in_background(candidate_id: uuid.UUID) -> None:
    """Run analysis for one candidate in its own DB session (for BackgroundTasks)."""
    from app.core.database import async_session

    async with async_session() as db:
        try:
            await analyze_candidate(db, candidate_id)
        except Exception:
            logger.exception("Background analysis failed for candidate %s", candidate_id)
