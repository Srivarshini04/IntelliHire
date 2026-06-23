"""Explainability Engine — generates strengths, risks, and reasoning."""


async def generate_explanation(
    candidate_name: str,
    capability: dict,
    risk: dict,
    hti: dict,
) -> dict:
    return {
        "strengths": [],
        "risks": [],
        "reason": f"Analysis pending for {candidate_name}.",
    }
