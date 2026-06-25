"""Unified analysis — evidence graph v5 with strength + LLM LinkedIn."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.github_intel.models import GitHubRepoAnalysis
from app.github_intel.seed import seed_capability_graph
from app.pipeline.aggregation import RepoAnalysisBundle, aggregate_candidate_profile
from app.pipeline.capability_engine import infer_capabilities_from_profile
from app.pipeline.claims import extract_claims
from app.pipeline.dependencies_v2 import extract_dependencies_from_context
from app.pipeline.discovery import discover_repositories, persist_repositories
from app.pipeline.evidence_graph import EvidenceGraph
from app.pipeline.engineering_maturity import compute_maturity_breakdown
from app.pipeline.explainability import (
    build_candidate_feature_evidence,
    build_feature_evidence_items,
    build_skill_evidence,
)
from app.pipeline.features import detect_features
from app.pipeline.git_api import fetch_git_history
from app.pipeline.hidden_gem import detect_hidden_gem
from app.pipeline.impact import aggregate_impact
from app.pipeline.jd_matching import (
    build_evidence_skill_scores,
    match_jd_capabilities,
    match_jd_skills,
    overall_jd_fit,
)
from app.pipeline.linkedin_llm import extract_linkedin, linkedin_features_for_graph
from app.pipeline.linkedin_resolve import resolve_linkedin_text
from app.pipeline.linkedin_parser import LinkedInExtraction, parse_linkedin_profile
from app.pipeline.ranking import rank_repositories
from app.pipeline.recruiter import build_recruiter_assessment
from app.pipeline.skill_assessment import assess_skills
from app.pipeline.structure_v2 import analyze_structure_from_context
from app.pipeline.tree_fetcher import fetch_repository_context
from app.pipeline.verification import verify_skills
from app.pipeline.schemas import AnalyzeResponse, EvidenceItem, HiddenGemResult

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def _run_github_pipeline(
    db: Session,
    github_url: str,
    jd_skills: list[str],
) -> tuple[str, list, list[RepoAnalysisBundle], list[EvidenceItem], list[str], list]:
    settings = get_settings()
    username, discovered = discover_repositories(github_url)
    candidate = persist_repositories(db, github_url, username, discovered)
    top_repos = rank_repositories(db, candidate, jd_skills, settings.top_n_repos)

    bundles: list[RepoAnalysisBundle] = []
    all_evidence: list[EvidenceItem] = []
    analyzed_names: list[str] = []
    impact_data: list[tuple[str, int, int, int]] = []

    for idx, repo in enumerate(top_repos):
        logger.info("Analyzing repo %d/%d: %s", idx + 1, len(top_repos), repo.full_name)
        ctx = fetch_repository_context(repo.full_name, repo.default_branch)
        structure = analyze_structure_from_context(ctx)
        dependencies = extract_dependencies_from_context(ctx)
        features = detect_features(ctx, dependencies)
        use_light_git = not settings.fetch_git_history_for_all and idx > 0
        git_metrics = fetch_git_history(
            repo.full_name, username,
            light=use_light_git, updated_at=repo.updated_at, size_kb=repo.size_kb,
        )

        analyzed_names.append(repo.full_name)
        impact_data.append((repo.full_name, repo.stars, repo.forks, repo.size_kb))
        bundles.append(RepoAnalysisBundle(
            repo_name=repo.full_name,
            features=features,
            maintenance_score=git_metrics.maintenance_score,
            complexity=structure.to_dict(),
            dependencies=dependencies,
            git_metrics=git_metrics.to_dict(),
            stars=repo.stars, forks=repo.forks, size_kb=repo.size_kb,
        ))
        all_evidence.extend(
            build_feature_evidence_items(repo.full_name, features, git_metrics.to_dict(), git_metrics.maintenance_score)
        )

        analysis = repo.analysis or GitHubRepoAnalysis(repository_id=repo.id)
        if not repo.analysis:
            db.add(analysis)
        analysis.features_json = json.dumps({k: v.to_dict() for k, v in features.items()})
        repo.analyzed = True

    db.commit()
    return username, discovered, bundles, all_evidence, analyzed_names, impact_data


def run_analysis(
    db: Session,
    github_url: str,
    jd_skills: list[str],
    jd_capabilities: list[str] | None = None,
    linkedin_profile: str | None = None,
    linkedin_url: str | None = None,
    resume_text: str | None = None,
) -> AnalyzeResponse:
    started = time.perf_counter()
    seed_capability_graph(db)
    jd_capabilities = jd_capabilities or []

    username, discovered, bundles, all_evidence, analyzed_names, impact_data = _run_github_pipeline(
        db, github_url, jd_skills,
    )

    profile = aggregate_candidate_profile(bundles)
    impact = aggregate_impact(impact_data)

    graph = EvidenceGraph()
    graph.build_from_github_profile(profile)

    linkedin_data: LinkedInExtraction | None = None
    linkedin_source = None
    scrape_meta = None
    profile_text, scrape_meta = resolve_linkedin_text(linkedin_url, linkedin_profile)
    if profile_text:
        linkedin_data, linkedin_source = extract_linkedin(
            profile_text, jd_skills, jd_capabilities,
        )
        org_map, li_evidence = linkedin_features_for_graph(linkedin_data)
        graph.merge_linkedin_features(org_map, li_evidence)
        for skill in linkedin_data.skill_claims:
            graph.add_claim("linkedin", f"Claims experience with {skill}", skill=skill)
        for exp in linkedin_data.experiences[:5]:
            snippet = exp.get("evidence", [exp.get("snippet", "")])[0] if exp.get("evidence") else exp.get("snippet", "")
            if snippet:
                graph.add_claim("linkedin", str(snippet)[:150], organization=exp.get("organization", "LinkedIn"))

    resume_claims: list[str] = []
    resume_extraction: LinkedInExtraction | None = None
    if resume_text and resume_text.strip():
        resume_extraction, _ = extract_linkedin(resume_text, jd_skills, jd_capabilities)
        resume_claims = resume_extraction.skill_claims
        org_map, li_evidence = linkedin_features_for_graph(resume_extraction)
        graph.merge_linkedin_features(org_map, li_evidence)
        for skill in resume_claims:
            graph.add_claim("resume", f"Resume claims {skill}", skill=skill)

    claims = extract_claims(linkedin_data, resume_text)

    skill_assessments = assess_skills(profile, jd_skills)
    verified = verify_skills(skill_assessments, linkedin_data, resume_claims)
    skill_scores = build_evidence_skill_scores(jd_skills, skill_assessments, verified)

    jd_skill_match = match_jd_skills(jd_skills, skill_scores, verified)
    jd_capability_match = match_jd_capabilities(jd_capabilities, {})  # filled after capabilities
    capabilities = infer_capabilities_from_profile(db, profile, impact.impact_score, graph)
    jd_capability_match = match_jd_capabilities(jd_capabilities, capabilities)
    jd_fit = overall_jd_fit(jd_skill_match, jd_capability_match)

    maturity = compute_maturity_breakdown(profile)
    feature_evidence = build_candidate_feature_evidence(profile, graph)
    skill_evidence = build_skill_evidence(skill_assessments, verified)
    gem = detect_hidden_gem(profile, impact, capabilities, maturity)
    recruiter = build_recruiter_assessment(
        profile, skill_assessments, verified, jd_skills, jd_capabilities,
        graph=graph,
        jd_match={"skills": jd_skill_match, "capabilities": jd_capability_match},
        maturity=maturity,
    )
    recruiter["cross_project_evidence"] = graph.recruiter_lines()
    recruiter["verification"] = {s: v.to_dict() for s, v in verified.items()}

    elapsed = time.perf_counter() - started
    sources_used = ["github"]
    if linkedin_data:
        src = f"linkedin:{linkedin_source or 'heuristic'}"
        if scrape_meta:
            src += f"+scrape:{scrape_meta.scrape_source}"
        sources_used.append(src)

    if resume_extraction:
        sources_used.append("resume")

    return AnalyzeResponse(
        github_url=github_url,
        github_username=username,
        claims=claims.to_dict(),
        candidate_capabilities=capabilities,
        skill_scores=skill_scores,
        skill_assessments={s: a.to_dict() for s, a in skill_assessments.items()},
        verified_skills={s: v.to_dict() for s, v in verified.items() if s in jd_skills},
        candidate_features=[f.label for f in profile.features.values() if f.detected],
        feature_evidence=feature_evidence,
        evidence_graph=graph.to_dict(),
        evidence=all_evidence,
        skill_evidence=skill_evidence,
        repositories_analyzed=analyzed_names,
        project_impact=impact.to_dict(),
        engineering_maturity=maturity.get("overall", profile.engineering_maturity),
        engineering_maturity_breakdown=maturity,
        hidden_gem=HiddenGemResult(**gem.to_dict()),
        recruiter_assessment=recruiter,
        jd_match={
            "skills": jd_skill_match,
            "capabilities": jd_capability_match,
            "overall_fit": jd_fit,
        },
        linkedin_extraction=linkedin_data.to_dict() if linkedin_data else None,
        metadata={
            "repos_discovered": len(discovered),
            "repos_analyzed": len(analyzed_names),
            "maintenance_score": profile.maintenance_score,
            "sources_used": sources_used,
            "linkedin_scrape": scrape_meta.to_dict() if scrape_meta else None,
            "analysis_mode": "evidence_intelligence_v6",
            "elapsed_seconds": round(elapsed, 1),
        },
        analyzed_at=datetime.utcnow(),
    )
