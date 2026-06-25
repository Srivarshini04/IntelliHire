"""Risk Engine — evidence gaps and credibility signals."""


async def compute_risk(evidence: dict, capability: dict, role_blueprint: dict) -> dict:
    github = evidence.get("github") or {}
    deep = github.get("deep") or {}
    basic = github.get("basic") or {}
    verified = deep.get("verified_skills") or {}
    repos_analyzed = len(github.get("repositories_analyzed") or [])

    missing_sources = 0
    if not basic.get("repos"):
        missing_sources += 1
    if not deep.get("candidate_features"):
        missing_sources += 1

    evidence_risk = min(missing_sources * 25 + max(0, 3 - repos_analyzed) * 10, 100)

    required_skills = [s.lower() for s in (role_blueprint.get("skills") or [])]
    skill_scores = deep.get("skill_scores") or {}
    gaps = 0
    for skill in required_skills:
        score = skill_scores.get(skill) or skill_scores.get(skill.title())
        if score is None or score < 40:
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
