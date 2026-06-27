"""Risk Engine — evidence gaps and credibility signals."""

from app.skills.matching import canonical, matches_skill_list


async def compute_risk(evidence: dict, capability: dict, role_blueprint: dict) -> dict:
    github = evidence.get("github") or {}
    deep = github.get("deep") or {}
    basic = github.get("basic") or {}
    linkedin = evidence.get("linkedin") or {}
    resume = evidence.get("resume") or {}
    verified = deep.get("verified_skills") or {}
    repos_analyzed = len(github.get("repositories_analyzed") or [])

    linkedin_features = linkedin.get("features") or []

    missing_sources = 0
    if not basic.get("repos"):
        missing_sources += 1
    if not deep.get("candidate_features"):
        missing_sources += 1
    # LinkedIn / resume corroboration each count as an independent evidence source.
    if linkedin_features:
        missing_sources = max(0, missing_sources - 1)
    if resume.get("skills"):
        missing_sources = max(0, missing_sources - 1)

    evidence_risk = min(missing_sources * 25 + max(0, 3 - repos_analyzed) * 10, 100)

    # Skills a candidate can claim from LinkedIn (skill claims + features built).
    linkedin_claims = list((linkedin.get("skills") or {}).get("skills", [])) + list(linkedin_features)
    # Required skills found in the resume (matched against JD in the pipeline).
    resume_matched = list((resume.get("jd_match") or {}).get("matched", []))

    required_skills = [str(s) for s in (role_blueprint.get("skills") or []) if str(s).strip()]
    # Canonicalize GitHub-verified skills (score >= 40) for variant-aware matching.
    skill_scores = deep.get("skill_scores") or {}
    github_canon = {canonical(name) for name, score in skill_scores.items() if score is not None and score >= 40}
    gaps = 0
    for skill in required_skills:
        github_covered = canonical(skill) in github_canon
        linkedin_covered = matches_skill_list(skill, linkedin_claims)
        resume_covered = matches_skill_list(skill, resume_matched)
        if not (github_covered or linkedin_covered or resume_covered):
            gaps += 1
    role_gap_risk = min((gaps / max(len(required_skills), 1)) * 100, 100) if required_skills else 20.0

    unverified = sum(1 for v in verified.values() if isinstance(v, dict) and not v.get("verified"))
    credibility_risk = min(unverified * 15, 100)

    risk_score = round(0.4 * evidence_risk + 0.35 * role_gap_risk + 0.25 * credibility_risk, 1)

    return {
        "evidence_risk": round(evidence_risk, 1),
        "role_gap_risk": round(role_gap_risk, 1),
        "credibility_risk": round(credibility_risk, 1),
        "risk_score": risk_score,
    }
