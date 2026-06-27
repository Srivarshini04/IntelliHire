"""Capability Engine — maps GitHub + LinkedIn evidence to HLD capability dimensions."""


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


# LinkedIn ownership claim → ownership signal (0-100).
_OWNERSHIP_SCORE = {"team lead": 85.0, "individual": 70.0, "contributor": 45.0}


def _linkedin_signals(linkedin: dict) -> dict:
    """Derive capability signals from a LinkedIn evidence package."""
    if not linkedin:
        return {}
    features = linkedin.get("features") or []
    scale = linkedin.get("scale") or {}
    users = _num(scale.get("users"))

    feature_breadth = min(len(features) * 12.0, 100.0)
    ownership = _OWNERSHIP_SCORE.get(str(linkedin.get("ownership", "")).lower(), 0.0)
    scale_signal = min(users / 1000.0, 60.0)  # 60k+ users saturates
    execution = min((50.0 if linkedin.get("production") else 0.0) + scale_signal, 100.0)

    return {
        "feature_breadth": feature_breadth,
        "ownership": ownership,
        "execution": execution,
    }


async def compute_capability(evidence: dict, role_blueprint: dict) -> dict:
    github = evidence.get("github") or {}
    deep = github.get("deep") or {}
    caps = deep.get("candidate_capabilities") or {}
    leetcode = github.get("leetcode") or {}
    li = _linkedin_signals(evidence.get("linkedin") or {})

    resume = evidence.get("resume") or {}
    resume_coverage = _num((resume.get("jd_match") or {}).get("coverage"))
    resume_breadth = min(len(resume.get("skills") or []) * 5.0, 80.0)

    backend = float(caps.get("backend_engineering", 0))
    deployment = float(caps.get("deployment_engineering", 0))
    database = float(caps.get("database_engineering", 0))
    ml = float(caps.get("ml_engineering", 0))
    maturity = float(github.get("engineering_maturity") or deep.get("engineering_maturity") or 0)
    maintenance = float(github.get("maintenance_score") or 0)
    coding_skill = float(leetcode.get("coding_skill") or 0) if leetcode else 0.0

    # GitHub base dimensions (unchanged from the original formulas).
    gh_technical = _avg([backend, database, ml, coding_skill * 0.6]) or backend
    gh_execution = _avg([deployment, maturity, maintenance])
    gh_domain = _avg([backend, database, ml])

    li_feature = li.get("feature_breadth", 0.0)
    li_execution = li.get("execution", 0.0)
    li_ownership = li.get("ownership", 0.0)

    # Each dimension takes the strongest available evidence source, so an empty
    # source never drags a candidate down (GitHub-only scores are unchanged).
    # Resume skill breadth adds a small differentiating bump on top.
    technical = min(
        max(gh_technical, resume_coverage, li_feature) + 0.1 * resume_breadth, 100.0
    )
    execution = max(gh_execution, li_execution)
    ownership = min(max(maintenance * 1.1, li_ownership), 100.0)
    learning = min(maturity * 0.7 + coding_skill * 0.3, 100.0)
    problem_solving = _avg([coding_skill, technical * 0.8])
    domain = max(gh_domain, resume_coverage)

    capability_score = (
        0.30 * technical
        + 0.30 * execution
        + 0.20 * ownership
        + 0.20 * learning
    )

    return {
        "technical": round(technical, 1),
        "execution": round(execution, 1),
        "ownership": round(ownership, 1),
        "learning_velocity": round(learning, 1),
        "problem_solving": round(problem_solving, 1),
        "domain_expertise": round(domain, 1),
        "capability_score": round(capability_score, 1),
    }
