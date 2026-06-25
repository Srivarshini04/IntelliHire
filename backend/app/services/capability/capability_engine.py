"""Capability Engine — maps GitHub evidence to HLD capability dimensions."""


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


async def compute_capability(evidence: dict, role_blueprint: dict) -> dict:
    github = evidence.get("github") or {}
    deep = github.get("deep") or {}
    caps = deep.get("candidate_capabilities") or {}
    leetcode = github.get("leetcode") or {}

    backend = float(caps.get("backend_engineering", 0))
    deployment = float(caps.get("deployment_engineering", 0))
    database = float(caps.get("database_engineering", 0))
    ml = float(caps.get("ml_engineering", 0))
    maturity = float(github.get("engineering_maturity") or deep.get("engineering_maturity") or 0)
    maintenance = float(github.get("maintenance_score") or 0)
    coding_skill = float(leetcode.get("coding_skill") or 0) if leetcode else 0.0

    technical = _avg([backend, database, ml, coding_skill * 0.6]) or backend
    execution = _avg([deployment, maturity, maintenance])
    ownership = min(maintenance * 1.1, 100.0)
    learning = min(maturity * 0.7 + coding_skill * 0.3, 100.0)
    problem_solving = _avg([coding_skill, technical * 0.8])
    domain = _avg([backend, database, ml])

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
