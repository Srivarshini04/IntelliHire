"""Risk Engine — evidence gaps and credibility signals."""


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
    linkedin_claims = {
        c.lower() for c in (linkedin.get("skills") or {}).get("skills", [])
    } | {f.lower() for f in linkedin_features}
    # Required skills found in the resume (matched against JD in the pipeline).
    resume_matched = {m.lower() for m in (resume.get("jd_match") or {}).get("matched", [])}

    required_skills = [s.lower() for s in (role_blueprint.get("skills") or [])]
    skill_scores = deep.get("skill_scores") or {}
    gaps = 0
    for skill in required_skills:
        score = skill_scores.get(skill) or skill_scores.get(skill.title())
        github_covered = score is not None and score >= 40
        linkedin_covered = any(skill in claim or claim in skill for claim in linkedin_claims)
        resume_covered = any(skill in m or m in skill for m in resume_matched)
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
