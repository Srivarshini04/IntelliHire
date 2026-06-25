"""Explainability Engine — generates strengths, risks, and reasoning."""


async def generate_explanation(
    candidate_name: str,
    capability: dict,
    risk: dict,
    hti: dict,
    recruiter_assessment: dict | None = None,
) -> dict:
    recruiter = recruiter_assessment or {}
    strengths = list(recruiter.get("strengths") or [])
    risks = list(recruiter.get("risks") or recruiter.get("concerns") or [])
    reason = recruiter.get("summary") or recruiter.get("verdict") or ""

    if not strengths:
        if capability.get("capability_score", 0) >= 70:
            strengths.append("Strong overall capability score from GitHub evidence")
        if capability.get("execution", 0) >= 65:
            strengths.append("Demonstrated execution through maintained projects")
        if hti.get("hti_score", 0) >= 60:
            strengths.append("High hidden talent index — strong capability relative to visibility")

    if not risks and risk.get("risk_score", 0) >= 30:
        risks.append("Elevated risk score — review evidence gaps before interviewing")

    if not reason:
        reason = (
            f"{candidate_name} shows capability score {capability.get('capability_score', 0):.0f} "
            f"with HTI {hti.get('hti_score', 0):.0f} based on cross-repo GitHub evidence analysis."
        )

    cross_project = recruiter.get("cross_project_evidence") or []
    if cross_project:
        reason += " " + cross_project[0]

    return {
        "strengths": strengths[:5],
        "risks": risks[:5],
        "reason": reason.strip(),
    }
