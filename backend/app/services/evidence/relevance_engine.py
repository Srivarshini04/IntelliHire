"""Relevance Filter — rate evidence artifacts 0-100, keep relevance > 60."""


async def filter_evidence(role: str, evidence: list[str]) -> list[dict]:
    """TODO: integrate Gemini for relevance scoring."""
    return [{"artifact": item, "relevance": 80.0} for item in evidence]
